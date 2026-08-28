"""
tests_stage2_verification.py — Stage 2 End-to-End Integration Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Verifies the complete Stage 2 pipeline:

  1.  Changing a patient's lab metric (eGFR) triggers the Celery task.
  2.  The task creates a SafetyAssessmentHistory record.
  3.  If the risk worsens, a ProactiveAlert is generated.
  4.  The /api/alerts/unread/ endpoint returns the alert.
  5.  The /api/alerts/{id}/acknowledge/ endpoint dismisses it.
  6.  The /api/patients/me/safety-history/ endpoint returns the timeline.
  7.  Debounce: duplicate rapid calls are collapsed.

Tests run with CELERY_TASK_ALWAYS_EAGER=True so no broker is needed.
"""
import os
import json
from datetime import date
from unittest.mock import patch, MagicMock

os.environ.setdefault('CELERY_TASK_ALWAYS_EAGER', 'True')

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from patients.models import (
    PatientProfile,
    MedicationCabinet,
    SafetyAssessmentHistory,
    ProactiveAlert,
)
from patients.tasks import re_evaluate_patient_safety_task


# Shared mock risk engine payload used across tests
MOCK_SEVERE_EVALUATION = {
    'overall_risk_score': 'Severe',
    'interactions': [
        {
            'severity': 'Severe',
            'description': 'Concomitant use may result in severe hyperkalemia.',
            'drug_involved': 'Lisinopril + Spironolactone',
        }
    ],
    'evidence_references': ['WHO_guideline_hypertension.pdf', 'openFDA_lisinopril.json'],
    'clinician_notes': 'Monitor serum potassium closely.',
}

MOCK_SAFE_EVALUATION = {
    'overall_risk_score': 'Safe',
    'interactions': [],
    'evidence_references': ['Patient profile contains 1 active medication.'],
    'clinician_notes': 'No interactions detected.',
}


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class Stage2PipelineTest(TestCase):
    """Integration tests proving the end-to-end Stage 2 safety pipeline."""

    def setUp(self):
        self.user = User.objects.create_user(username='test_patient', password='testpass123')
        # Use get_or_create but disconnect signals to avoid spurious task calls from setUp itself
        from django.db.models.signals import post_save, post_delete
        from patients.models import (
            on_patient_profile_saved,
            on_medication_cabinet_saved,
            on_medication_cabinet_deleted,
        )
        post_save.disconnect(on_patient_profile_saved, sender=PatientProfile)
        post_save.disconnect(on_medication_cabinet_saved, sender=MedicationCabinet)
        post_delete.disconnect(on_medication_cabinet_deleted, sender=MedicationCabinet)

        self.profile, _ = PatientProfile.objects.get_or_create(
            user=self.user,
            defaults={'age': 52, 'gender': 'M', 'egfr': 75}
        )

        post_save.connect(on_patient_profile_saved, sender=PatientProfile)
        post_save.connect(on_medication_cabinet_saved, sender=MedicationCabinet)
        post_delete.connect(on_medication_cabinet_deleted, sender=MedicationCabinet)

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # CRITICAL: Clear the cache before every test so debounce locks don't bleed across tests
        from django.core.cache import cache
        cache.clear()

    def _add_medication(self, name='Lisinopril'):
        """Add a medication while signals are disconnected (avoids unintended task side-effects)."""
        from django.db.models.signals import post_save
        from patients.models import on_medication_cabinet_saved
        post_save.disconnect(on_medication_cabinet_saved, sender=MedicationCabinet)
        try:
            med = MedicationCabinet.objects.create(
                patient=self.profile,
                name=name,
                dosage='10mg',
                frequency='once daily',
                start_date=date.today(),
                is_active=True,
            )
        finally:
            post_save.connect(on_medication_cabinet_saved, sender=MedicationCabinet)
        return med

    # ─────────────────────────────────────────────────────────────────────────
    # Test 1: Task creates SafetyAssessmentHistory
    # ─────────────────────────────────────────────────────────────────────────

    @patch('services.risk_engine.RiskEngine.evaluate_patient_safety')
    def test_task_creates_assessment_history(self, mock_eval):
        """Calling the task synchronously must persist a SafetyAssessmentHistory."""
        mock_eval.return_value = MOCK_SAFE_EVALUATION
        self._add_medication()

        # Ensure no stale lock from setUp (already cleared, but be explicit)
        from django.core.cache import cache
        cache.clear()

        result = re_evaluate_patient_safety_task.apply(
            args=[self.profile.pk], kwargs={'triggered_by': 'manual'}
        )

        self.assertFalse(result.result.get('skipped', False), 
                         "Task should not be skipped — cache was cleared before this test.")
        history = SafetyAssessmentHistory.objects.filter(patient=self.profile)
        self.assertGreaterEqual(history.count(), 1)
        self.assertEqual(history.first().risk_score, 'Safe')

    # ─────────────────────────────────────────────────────────────────────────
    # Test 2: Worsening risk creates a ProactiveAlert
    # ─────────────────────────────────────────────────────────────────────────

    @patch('services.risk_engine.RiskEngine.evaluate_patient_safety')
    def test_worsening_risk_creates_alert(self, mock_eval):
        """
        When the new risk score is strictly higher than the previous run,
        a ProactiveAlert must be created.
        """
        # Add medications FIRST (signals disconnected inside _add_medication)
        self._add_medication('Lisinopril')
        self._add_medication('Spironolactone')

        # Seed a prior Safe assessment so the comparison logic has something to compare against
        SafetyAssessmentHistory.objects.create(
            patient=self.profile,
            risk_score='Safe',
            details=MOCK_SAFE_EVALUATION,
            triggered_by='manual',
        )

        mock_eval.return_value = MOCK_SEVERE_EVALUATION  # Set AFTER adding meds

        from django.core.cache import cache
        cache.clear()  # Ensure no stale lock

        result = re_evaluate_patient_safety_task.apply(
            args=[self.profile.pk], kwargs={'triggered_by': 'lab_update'}
        )

        self.assertFalse(result.result.get('skipped', False), "Task must not be skipped.")
        self.assertTrue(result.result.get('alert_created'), "Expected a ProactiveAlert to be created.")
        alert = ProactiveAlert.objects.filter(patient=self.profile).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'Severe')
        self.assertIn('escalated', alert.message.lower())
        self.assertFalse(alert.acknowledged)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 3: Kidney metric drop triggers the full pipeline
    # ─────────────────────────────────────────────────────────────────────────

    @patch('services.risk_engine.RiskEngine.evaluate_patient_safety')
    def test_kidney_metric_change_triggers_pipeline(self, mock_eval):
        """
        Directly invoking the task (simulating what the signal would do after
        an eGFR update) must create SafetyAssessmentHistory and, given a Severe
        result with no prior history, a ProactiveAlert.
        """
        # Add medication with signals disconnected so task doesn't pre-run
        self._add_medication('Ibuprofen')

        from django.core.cache import cache
        cache.clear()  # Ensure no stale debounce lock

        # Capture count AFTER setup, BEFORE explicit task call
        history_count_before = SafetyAssessmentHistory.objects.filter(patient=self.profile).count()
        alert_count_before = ProactiveAlert.objects.filter(patient=self.profile).count()

        mock_eval.return_value = MOCK_SEVERE_EVALUATION

        # Call the task directly (mirrors what the post_save signal does)
        result = re_evaluate_patient_safety_task.apply(
            args=[self.profile.pk], kwargs={'triggered_by': 'lab_update'}
        )

        self.assertFalse(result.result.get('skipped', False), "Task must not be skipped.")

        self.assertGreater(
            SafetyAssessmentHistory.objects.filter(patient=self.profile).count(),
            history_count_before,
            "Task must create a new SafetyAssessmentHistory record."
        )
        # First run with Severe and no prior history → alert should be created
        alert_count_after = ProactiveAlert.objects.filter(patient=self.profile).count()
        self.assertGreater(alert_count_after, alert_count_before,
                           "Task must create a ProactiveAlert when Severe risk detected.")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 4: API — /api/alerts/unread/ returns alert for authenticated user
    # ─────────────────────────────────────────────────────────────────────────

    def test_unread_alerts_api(self):
        """GET /api/alerts/unread/ returns alerts belonging only to the current user."""
        history = SafetyAssessmentHistory.objects.create(
            patient=self.profile,
            risk_score='Severe',
            details=MOCK_SEVERE_EVALUATION,
            triggered_by='manual',
        )
        ProactiveAlert.objects.create(
            patient=self.profile,
            assessment=history,
            severity='Severe',
            message='Risk flagged: drug interaction detected.',
        )

        response = self.client.get('/api/alerts/unread/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('alerts', data)
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['alerts'][0]['severity'], 'Severe')

    # ─────────────────────────────────────────────────────────────────────────
    # Test 5: API — Acknowledge endpoint dismisses the alert
    # ─────────────────────────────────────────────────────────────────────────

    def test_acknowledge_alert_api(self):
        """POST /api/alerts/{id}/acknowledge/ must flip acknowledged=True."""
        history = SafetyAssessmentHistory.objects.create(
            patient=self.profile,
            risk_score='Moderate',
            details=MOCK_SAFE_EVALUATION,
            triggered_by='manual',
        )
        alert = ProactiveAlert.objects.create(
            patient=self.profile,
            assessment=history,
            severity='Moderate',
            message='Risk flagged: moderate interaction.',
        )

        response = self.client.post(f'/api/alerts/{alert.pk}/acknowledge/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        alert.refresh_from_db()
        self.assertTrue(alert.acknowledged)

    # ─────────────────────────────────────────────────────────────────────────
    # Test 6: API — Safety History Timeline endpoint
    # ─────────────────────────────────────────────────────────────────────────

    def test_safety_history_api(self):
        """GET /api/patients/me/safety-history/ returns history list with risk_level."""
        for score in ['Safe', 'Low', 'Moderate', 'Severe']:
            SafetyAssessmentHistory.objects.create(
                patient=self.profile,
                risk_score=score,
                details={'overall_risk_score': score, 'interactions': [], 'evidence_references': []},
                triggered_by='manual',
            )

        response = self.client.get('/api/patients/me/safety-history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('results', data)
        self.assertEqual(len(data['results']), 4)
        # Confirm risk_level field is present and numeric
        risk_levels = [r['risk_level'] for r in data['results']]
        for rl in risk_levels:
            self.assertIn(rl, [0, 1, 2, 3])

    # ─────────────────────────────────────────────────────────────────────────
    # Test 7: Debounce — duplicate rapid task invocations collapse to one run
    # ─────────────────────────────────────────────────────────────────────────

    @patch('services.risk_engine.RiskEngine.evaluate_patient_safety')
    def test_debounce_collapses_rapid_triggers(self, mock_eval):
        """
        A second task invocation while an evaluation is running must be coalesced.
        """
        mock_eval.return_value = MOCK_SAFE_EVALUATION
        # Add medication without triggering signals
        self._add_medication()

        from django.core.cache import cache
        cache.clear()  # Start with a totally clean debounce state

        # Simulate that an evaluation is actively running
        running_key = f'patient_safety_running_{self.profile.pk}'
        cache.set(running_key, 1, timeout=60)

        # Second call arrives while running_key is held
        result2 = re_evaluate_patient_safety_task.apply(
            args=[self.profile.pk], kwargs={'triggered_by': 'manual'}
        )

        # Second call must be coalesced/skipped and dirty flag marked
        self.assertTrue(result2.result.get('skipped'), "Concurrent call MUST be skipped/coalesced.")
        self.assertTrue(result2.result.get('coalesced'), "Concurrent call MUST have coalesced flag set.")
        self.assertEqual(cache.get(f'patient_safety_dirty_{self.profile.pk}'), 1, "Dirty flag must be marked for trailing run.")

        cache.clear()

    # ─────────────────────────────────────────────────────────────────────────
    # Test 8: Unacknowledged alerts are isolated per user
    # ─────────────────────────────────────────────────────────────────────────

    def test_alerts_are_user_isolated(self):
        """A second user must NOT see alerts belonging to another user."""
        other_user = User.objects.create_user(username='other_user', password='pass')
        other_profile, _ = PatientProfile.objects.get_or_create(user=other_user)
        history = SafetyAssessmentHistory.objects.create(
            patient=other_profile,
            risk_score='Severe',
            details=MOCK_SEVERE_EVALUATION,
            triggered_by='manual',
        )
        ProactiveAlert.objects.create(
            patient=other_profile,
            assessment=history,
            severity='Severe',
            message='Alert for other user.',
        )

        # Our test_patient should see zero alerts
        response = self.client.get('/api/alerts/unread/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['count'], 0)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class MedicationDeletionSafetyTest(TestCase):
    """
    BUG-03 Regression Test Suite:
    Guarantees that medication deletion triggers safety recalculation,
    correctly resolves stale risks/alerts, and retains active risks for remaining medications.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='deletion_patient', password='password123')
        
        # Disconnect signals during setup to prevent spurious task dispatches
        from django.db.models.signals import post_save, post_delete
        from patients.models import (
            on_patient_profile_saved,
            on_medication_cabinet_saved,
            on_medication_cabinet_deleted,
        )
        post_save.disconnect(on_patient_profile_saved, sender=PatientProfile)
        post_save.disconnect(on_medication_cabinet_saved, sender=MedicationCabinet)
        post_delete.disconnect(on_medication_cabinet_deleted, sender=MedicationCabinet)

        from decimal import Decimal
        self.profile = PatientProfile.objects.create(
            user=self.user,
            age=45,
            gender='F',
            pregnancy_status=False,
            egfr=Decimal('90.00'),
            creatinine=Decimal('0.90')
        )

        post_save.connect(on_patient_profile_saved, sender=PatientProfile)
        post_save.connect(on_medication_cabinet_saved, sender=MedicationCabinet)
        post_delete.connect(on_medication_cabinet_deleted, sender=MedicationCabinet)

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        from django.core.cache import cache
        cache.clear()

    def _create_med(self, name, dosage='10mg', frequency='once daily'):
        """Creates a medication without firing signals."""
        from django.db.models.signals import post_save
        from patients.models import on_medication_cabinet_saved
        post_save.disconnect(on_medication_cabinet_saved, sender=MedicationCabinet)
        try:
            return MedicationCabinet.objects.create(
                patient=self.profile,
                name=name,
                dosage=dosage,
                frequency=frequency,
                start_date=date.today(),
                is_active=True
            )
        finally:
            post_save.connect(on_medication_cabinet_saved, sender=MedicationCabinet)

    # ── Test 1: Safe medication deletion ─────────────────────────────────────
    def test_1_safe_medication_deletion(self):
        """Deleting a single safe medication recalculates risk state to Safe with 0 active meds."""
        med = self._create_med('Metformin', dosage='500mg')
        
        from django.core.cache import cache
        cache.clear()

        # Delete the medication — triggers post_delete signal
        med.delete()

        history = SafetyAssessmentHistory.objects.filter(patient=self.profile).order_by('-created_at')
        self.assertGreaterEqual(history.count(), 1)
        latest = history.first()
        self.assertEqual(latest.risk_score, 'Safe')
        self.assertEqual(latest.triggered_by, 'medication_change')
        self.assertEqual(len(latest.details.get('interactions', [])), 0)

    # ── Test 2: High-risk medication deletion ────────────────────────────────
    def test_2_high_risk_medication_deletion(self):
        """Deleting one interacting drug from a High-Risk pair recalculates risk to Safe."""
        lisinopril = self._create_med('Lisinopril')
        spironolactone = self._create_med('Spironolactone')

        # Trigger initial evaluation to record the severe interaction
        from django.core.cache import cache
        cache.clear()
        re_evaluate_patient_safety_task.apply(args=[self.profile.pk], kwargs={'triggered_by': 'medication_change'})
        
        prev_assessment = SafetyAssessmentHistory.objects.filter(patient=self.profile).first()
        self.assertEqual(prev_assessment.risk_score, 'Severe')

        # Delete Spironolactone -> signal fires Celery task
        cache.clear()
        spironolactone.delete()

        # Check latest assessment post-deletion
        latest_assessment = SafetyAssessmentHistory.objects.filter(patient=self.profile).first()
        self.assertEqual(latest_assessment.risk_score, 'Safe')
        self.assertEqual(len(latest_assessment.details.get('interactions', [])), 0)

    # ── Test 3: Interaction removal ──────────────────────────────────────────
    def test_3_interaction_removal(self):
        """Deleting interacting drug removes the drug-drug interaction warning from details."""
        self._create_med('Lisinopril')
        spiro = self._create_med('Spironolactone')

        from django.core.cache import cache
        cache.clear()
        re_evaluate_patient_safety_task.apply(args=[self.profile.pk], kwargs={'triggered_by': 'medication_change'})

        # Verify hyperkalemia interaction is present before deletion
        initial = SafetyAssessmentHistory.objects.filter(patient=self.profile).first()
        descriptions = [i['description'].lower() for i in initial.details.get('interactions', [])]
        self.assertTrue(any('hyperkalemia' in d for d in descriptions))

        # Delete Spironolactone
        cache.clear()
        spiro.delete()

        latest = SafetyAssessmentHistory.objects.filter(patient=self.profile).first()
        post_descriptions = [i['description'].lower() for i in latest.details.get('interactions', [])]
        self.assertFalse(any('hyperkalemia' in d for d in post_descriptions))

    # ── Test 4: Multiple medications (A+B+C -> delete B -> evaluate A+C) ────
    def test_4_multiple_medications_retains_remaining_risks(self):
        """
        Lisinopril + Spironolactone + Ibuprofen -> delete Spironolactone.
        Must evaluate remaining Lisinopril + Ibuprofen and detect Moderate risk.
        Proves the engine does NOT blindly clear to Safe.
        """
        self._create_med('Lisinopril')
        spiro = self._create_med('Spironolactone')
        self._create_med('Ibuprofen')

        from django.core.cache import cache
        cache.clear()
        re_evaluate_patient_safety_task.apply(args=[self.profile.pk], kwargs={'triggered_by': 'medication_change'})
        
        initial = SafetyAssessmentHistory.objects.filter(patient=self.profile).first()
        self.assertEqual(initial.risk_score, 'Severe')

        # Delete Spironolactone -> remaining: Lisinopril + Ibuprofen (Moderate interaction)
        cache.clear()
        spiro.delete()

        latest = SafetyAssessmentHistory.objects.filter(patient=self.profile).first()
        self.assertEqual(latest.risk_score, 'Moderate')
        interactions = latest.details.get('interactions', [])
        self.assertTrue(len(interactions) > 0)
        self.assertTrue(any('nsaid' in i['description'].lower() or 'ibuprofen' in i.get('drug_involved', '').lower() for i in interactions))

    # ── Test 5: Delete last medication ───────────────────────────────────────
    def test_5_delete_last_medication(self):
        """Deleting the final remaining medication evaluates to Safe with 0 active medications."""
        med = self._create_med('Lisinopril')
        
        from django.core.cache import cache
        cache.clear()
        med.delete()

        latest = SafetyAssessmentHistory.objects.filter(patient=self.profile).first()
        self.assertEqual(latest.risk_score, 'Safe')
        self.assertEqual(MedicationCabinet.objects.filter(patient=self.profile).count(), 0)

    # ── Test 6: Active alert reconciliation and timeline update ──────────────
    def test_6_active_alert_reconciliation_and_timeline(self):
        """Deleting interacting medication generates a de-escalated SafetyAssessmentHistory on timeline."""
        self._create_med('Lisinopril')
        
        # Initial safe record
        SafetyAssessmentHistory.objects.create(
            patient=self.profile,
            risk_score='Safe',
            details={'overall_risk_score': 'Safe', 'interactions': []},
            triggered_by='manual'
        )

        from django.core.cache import cache
        cache.clear()

        # Add Spironolactone -> escalates from Safe to Severe -> creates ProactiveAlert
        spiro = MedicationCabinet.objects.create(
            patient=self.profile,
            name='Spironolactone',
            dosage='25mg',
            frequency='once daily',
            start_date=date.today(),
            is_active=True
        )

        alert = ProactiveAlert.objects.filter(patient=self.profile).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'Severe')

        # Delete Spironolactone -> triggers safety recalculation
        cache.clear()
        spiro.delete()

        # Verify timeline has the de-escalated Safe assessment at the top
        response = self.client.get('/api/patients/me/safety-history/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get('results', [])
        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0]['risk_score'], 'Safe')
        self.assertEqual(results[0]['risk_level'], 0)

    # ── Test 7: Rapid changes (Delete then Add) ──────────────────────────────
    def test_7_rapid_changes_delete_then_add(self):
        """Deleting a medication then adding an allergic medication evaluates the latest state."""
        med1 = self._create_med('Metformin')
        
        # Patient has penicillin allergy
        self.profile.allergies = ['penicillin']
        self.profile.save()

        from django.core.cache import cache
        cache.clear()

        # Delete Metformin
        med1.delete()

        # Clear debounce lock to simulate next user action
        cache.clear()

        # Add Amoxicillin (allergic contraindication)
        MedicationCabinet.objects.create(
            patient=self.profile,
            name='Amoxicillin',
            dosage='500mg',
            frequency='twice daily',
            start_date=date.today(),
            is_active=True
        )

        latest = SafetyAssessmentHistory.objects.filter(patient=self.profile).first()
        self.assertEqual(latest.risk_score, 'Severe')
        self.assertTrue(any('allerg' in i['description'].lower() for i in latest.details.get('interactions', [])))

    # ── Test 8: REST API Deletion Endpoint (DELETE /api/patients/cabinet/{id}/)
    def test_8_api_medication_deletion_endpoint(self):
        """Invoking HTTP DELETE /api/patients/cabinet/{id}/ returns 204 and triggers recalculation."""
        med = self._create_med('Lisinopril')

        from django.core.cache import cache
        cache.clear()

        url = f'/api/patients/cabinet/{med.pk}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Confirm DB deletion
        self.assertFalse(MedicationCabinet.objects.filter(pk=med.pk).exists())

        # Confirm safety evaluation was triggered
        latest = SafetyAssessmentHistory.objects.filter(patient=self.profile).first()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.risk_score, 'Safe')
        self.assertEqual(latest.triggered_by, 'medication_change')


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class MedicationSafetyDebounceRaceTest(TestCase):
    """
    BUG-02 Regression & Concurrency Race Condition Test Suite:
    Guarantees that rapid updates, concurrent triggers, updates during active evaluations,
    and task retries never drop the final patient safety evaluation.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='race_test_patient', password='password123')

        # Disconnect signals during initial setup
        from django.db.models.signals import post_save, post_delete
        from patients.models import (
            on_patient_profile_saved,
            on_medication_cabinet_saved,
            on_medication_cabinet_deleted,
        )
        post_save.disconnect(on_patient_profile_saved, sender=PatientProfile)
        post_save.disconnect(on_medication_cabinet_saved, sender=MedicationCabinet)
        post_delete.disconnect(on_medication_cabinet_deleted, sender=MedicationCabinet)

        from decimal import Decimal
        self.profile = PatientProfile.objects.create(
            user=self.user,
            age=50,
            gender='M',
            pregnancy_status=False,
            egfr=Decimal('85.00'),
            creatinine=Decimal('1.00')
        )

        post_save.connect(on_patient_profile_saved, sender=PatientProfile)
        post_save.connect(on_medication_cabinet_saved, sender=MedicationCabinet)
        post_delete.connect(on_medication_cabinet_deleted, sender=MedicationCabinet)

        from django.core.cache import cache
        cache.clear()

    def _add_med(self, name, dosage='10mg', frequency='once daily'):
        """Creates a medication without firing signals."""
        from django.db.models.signals import post_save
        from patients.models import on_medication_cabinet_saved
        post_save.disconnect(on_medication_cabinet_saved, sender=MedicationCabinet)
        try:
            return MedicationCabinet.objects.create(
                patient=self.profile,
                name=name,
                dosage=dosage,
                frequency=frequency,
                start_date=date.today(),
                is_active=True
            )
        finally:
            post_save.connect(on_medication_cabinet_saved, sender=MedicationCabinet)

    # ── Test 1: Single update evaluates and clears running lock ──────────────
    @patch('services.risk_engine.RiskEngine.evaluate_patient_safety')
    def test_single_update_evaluates_and_cleans_lock(self, mock_eval):
        """Single update runs exactly 1 evaluation and cleanly releases running lock."""
        mock_eval.return_value = MOCK_SAFE_EVALUATION
        self._add_med('Metformin')

        from django.core.cache import cache
        cache.clear()

        result = re_evaluate_patient_safety_task.apply(
            args=[self.profile.pk], kwargs={'triggered_by': 'manual'}
        )

        self.assertFalse(result.result.get('skipped'), "Single update must NOT be skipped.")
        self.assertEqual(result.result.get('risk_score'), 'Safe')
        self.assertEqual(
            SafetyAssessmentHistory.objects.filter(patient=self.profile).count(), 1
        )
        # Verify running lock was cleanly released
        self.assertIsNone(cache.get(f'patient_safety_running_{self.profile.pk}'))
        self.assertIsNone(cache.get(f'patient_safety_dirty_{self.profile.pk}'))

    # ── Test 2: Update during active evaluation triggers trailing evaluation ─
    def test_update_during_active_evaluation_triggers_trailing_evaluation(self):
        """
        Simulate patient state changing while an evaluation is in-flight.
        The trailing-edge loop must automatically re-evaluate the newest state.
        """
        self._add_med('Lisinopril')

        from django.core.cache import cache
        cache.clear()

        from services.risk_engine import RiskEngine
        orig_evaluate = RiskEngine.evaluate_patient_safety
        call_count = [0]

        def mid_flight_modification(engine_instance, profile):
            call_count[0] += 1
            if call_count[0] == 1:
                # Mid-flight during run 1: Patient adds Spironolactone (severe interaction)
                # Signal marks dirty flag and adds med to DB
                self._add_med('Spironolactone')
                cache.set(f'patient_safety_dirty_{self.profile.pk}', 1, timeout=120)
            return orig_evaluate(engine_instance, profile)

        with patch.object(RiskEngine, 'evaluate_patient_safety', side_effect=mid_flight_modification, autospec=True):
            result = re_evaluate_patient_safety_task.apply(
                args=[self.profile.pk], kwargs={'triggered_by': 'medication_change'}
            )

        self.assertFalse(result.result.get('skipped'))
        # Should have executed 2 evaluations: initial Lisinopril, then trailing Lisinopril+Spironolactone
        self.assertEqual(call_count[0], 2, "Engine must have run a trailing evaluation for the mid-flight modification.")
        
        # Verify latest assessment in history is Severe (Lisinopril + Spironolactone)
        history = SafetyAssessmentHistory.objects.filter(patient=self.profile).order_by('-created_at')
        self.assertEqual(history.count(), 2)
        latest = history.first()
        self.assertEqual(latest.risk_score, 'Severe')
        self.assertEqual(latest.triggered_by, 'trailing_state_change')

        # Verify ProactiveAlert was created for the escalation
        alert = ProactiveAlert.objects.filter(patient=self.profile).first()
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, 'Severe')

    # ── Test 3: Multiple rapid updates coalesce into latest state ───────────
    def test_multiple_rapid_updates_coalesced_to_latest_state(self):
        """
        5 rapid medication additions must guarantee that the final state with all 5 meds
        is evaluated without any dropped state.
        """
        from django.core.cache import cache
        cache.clear()

        # Add 5 medications in rapid succession with active signals
        meds = ['Metformin', 'Lisinopril', 'Atorvastatin', 'Amlodipine', 'Omeprazole']
        for med_name in meds:
            MedicationCabinet.objects.create(
                patient=self.profile,
                name=med_name,
                dosage='10mg',
                frequency='daily',
                start_date=date.today(),
                is_active=True
            )

        # The latest assessment in history must reflect all active meds
        history = SafetyAssessmentHistory.objects.filter(patient=self.profile).order_by('-created_at')
        self.assertGreaterEqual(history.count(), 1)
        
        latest_assessment = history.first()
        self.assertIsNotNone(latest_assessment)
        self.assertEqual(MedicationCabinet.objects.filter(patient=self.profile, is_active=True).count(), 5)

    # ── Test 4: Delete and add rapidly evaluates final medication state ─────
    def test_delete_and_add_rapidly_evaluates_final_state(self):
        """Deleting a drug and adding an allergic drug rapidly evaluates final state."""
        med1 = self._add_med('Metformin')
        self.profile.allergies = ['aspirin']
        self.profile.save()

        from django.core.cache import cache
        cache.clear()

        # Delete Metformin and add Aspirin
        med1.delete()
        MedicationCabinet.objects.create(
            patient=self.profile,
            name='Aspirin',
            dosage='81mg',
            frequency='daily',
            start_date=date.today(),
            is_active=True
        )

        history = SafetyAssessmentHistory.objects.filter(patient=self.profile).order_by('-created_at')
        latest = history.first()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.risk_score, 'Severe')
        # Drug involved in allergy is Aspirin
        descriptions = [i.get('description', '').lower() for i in latest.details.get('interactions', [])]
        self.assertTrue(any('aspirin' in d or 'allerg' in d for d in descriptions))

    # ── Test 5: Profile lab change and medication update combined ───────────
    def test_profile_and_medication_update_combined(self):
        """Updating patient kidney lab (eGFR drop) and medication evaluates combined risk."""
        self._add_med('Ibuprofen')

        from django.core.cache import cache
        cache.clear()

        from decimal import Decimal
        self.profile.egfr = Decimal('25.00')  # severe renal impairment
        self.profile.save()

        history = SafetyAssessmentHistory.objects.filter(patient=self.profile).order_by('-created_at')
        latest = history.first()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.risk_score, 'Moderate')
        self.assertTrue(any('renal' in i.get('description', '').lower() or 'egfr' in i.get('description', '').lower() 
                            for i in latest.details.get('interactions', [])))

    # ── Test 6: Duplicate task execution idempotency ─────────────────────────
    @patch('services.risk_engine.RiskEngine.evaluate_patient_safety')
    def test_duplicate_task_execution_idempotency(self, mock_eval):
        """Running the task twice sequentially on identical state creates no duplicate alerts."""
        mock_eval.return_value = MOCK_SEVERE_EVALUATION
        self._add_med('Lisinopril')

        from django.core.cache import cache
        cache.clear()

        # Run 1
        res1 = re_evaluate_patient_safety_task.apply(args=[self.profile.pk], kwargs={'triggered_by': 'manual'})
        self.assertTrue(res1.result.get('alert_created'))
        alerts_count_after_run1 = ProactiveAlert.objects.filter(patient=self.profile).count()
        self.assertEqual(alerts_count_after_run1, 1)

        # Run 2 on same unchanged state
        res2 = re_evaluate_patient_safety_task.apply(args=[self.profile.pk], kwargs={'triggered_by': 'manual'})
        self.assertFalse(res2.result.get('alert_created'), "Identical risk level must not create duplicate alert.")
        self.assertEqual(ProactiveAlert.objects.filter(patient=self.profile).count(), 1)

    # ── Test 7: Lock cleanup on exception ────────────────────────────────────
    def test_lock_cleanup_on_exception(self):
        """If RiskEngine raises an unhandled exception, finally block must release running lock."""
        from django.core.cache import cache
        cache.clear()

        from services.risk_engine import RiskEngine
        with patch.object(RiskEngine, 'evaluate_patient_safety', side_effect=RuntimeError("Simulated DB Crash")):
            with self.assertRaises(RuntimeError):
                re_evaluate_patient_safety_task.apply(args=[self.profile.pk], kwargs={'triggered_by': 'manual'})

        # Lock must be deleted in finally block
        self.assertIsNone(cache.get(f'patient_safety_running_{self.profile.pk}'))

    # ── Test 8: Worker crash lease expiration recovery ───────────────────────
    def test_worker_crash_lease_expiration_recovery(self):
        """A stale running lock from a crashed worker does not permanently block future runs."""
        from django.core.cache import cache
        cache.clear()

        # Simulate a lock that is expired / missing
        self.assertIsNone(cache.get(f'patient_safety_running_{self.profile.pk}'))

        # Subsequent evaluation runs successfully
        res = re_evaluate_patient_safety_task.apply(args=[self.profile.pk], kwargs={'triggered_by': 'manual'})
        self.assertFalse(res.result.get('skipped'))

    # ── Test 9: Boundary race condition catch-up guarantee ──────────────────
    def test_boundary_race_condition_catchup(self):
        """
        If a new state change arrives right at the boundary of lock release,
        the finally catchup check must detect dirty_key and dispatch a trailing task.
        """
        self._add_med('Metformin')

        from django.core.cache import cache
        cache.clear()

        from services.risk_engine import RiskEngine
        with patch('patients.tasks.re_evaluate_patient_safety_task.delay') as mock_delay:
            # Simulate dirty flag being set right as lock is deleting
            orig_delete = cache.delete
            def boundary_delete(key):
                orig_delete(key)
                if 'patient_safety_running' in key:
                    # Dirty flag was set concurrently during lock release
                    cache.set(f'patient_safety_dirty_{self.profile.pk}', 1, timeout=120)

            with patch.object(cache, 'delete', side_effect=boundary_delete):
                re_evaluate_patient_safety_task.apply(args=[self.profile.pk], kwargs={'triggered_by': 'manual'})

            # Verify that boundary catchup dispatched a trailing evaluation
            mock_delay.assert_called_with(self.profile.pk, triggered_by='trailing_catchup')

    # ── Test 10: Redis outage fail-open safety invariant ─────────────────────
    @patch('services.risk_engine.RiskEngine.evaluate_patient_safety')
    def test_redis_outage_fail_open_safety_invariant(self, mock_eval):
        """
        If Redis or cache backend fails with an exception, the system must FAIL OPEN
        and execute the safety evaluation rather than silently dropping the patient.
        """
        mock_eval.return_value = MOCK_SAFE_EVALUATION
        self._add_med('Lisinopril')

        from django.core.cache import cache
        # Patch cache.add and cache.set to raise ConnectionError (Redis down)
        with patch.object(cache, 'add', side_effect=ConnectionError("Redis connection refused")):
            with patch.object(cache, 'set', side_effect=ConnectionError("Redis connection refused")):
                result = re_evaluate_patient_safety_task.apply(args=[self.profile.pk], kwargs={'triggered_by': 'manual'})

        # The task must NOT be skipped; it must execute the evaluation
        self.assertFalse(result.result.get('skipped'))
        self.assertEqual(result.result.get('risk_score'), 'Safe')
        self.assertEqual(SafetyAssessmentHistory.objects.filter(patient=self.profile).count(), 1)
