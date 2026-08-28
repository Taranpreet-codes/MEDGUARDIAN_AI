"""
patients/tasks.py — Stage 2 Proactive Safety Re-Evaluation Task
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This Celery task wraps Stage 1's RiskEngine to perform background safety
assessments whenever patient data changes.  Key features:

  • 10-second idempotency debounce: rapid consecutive triggers for the same
    patient are collapsed into a single run.
  • Exponential backoff retry: if external APIs (Gemini, RxNav) time out, the
    task retries up to 3 times with increasing delays.
  • Worsening detection: compares the new risk score to the previous run and
    generates a ProactiveAlert if the risk has escalated.
"""
import logging

import requests
from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Severity ordering used for "did risk worsen?" comparison
RISK_ORDER = {'Safe': 0, 'Low': 1, 'Moderate': 2, 'Severe': 3}

# Cache TTLs
RUNNING_LOCK_TTL = 60    # Lease timeout (seconds) for running task to protect against worker crashes
DIRTY_FLAG_TTL = 120     # TTL (seconds) for patient pending modification dirty flag


@shared_task(
    bind=True,
    autoretry_for=(requests.exceptions.Timeout, requests.exceptions.ConnectionError),
    retry_backoff=True,           # 5s → 10s → 20s
    max_retries=3,
    default_retry_delay=5,
    ignore_result=False,
    name='patients.tasks.re_evaluate_patient_safety_task',
)
def re_evaluate_patient_safety_task(self, patient_id: int, triggered_by: str = 'manual'):
    """
    Background task: re-evaluate medication safety for a single patient.
    Guarantees eventual evaluation of the final patient state using an atomic
    coalescing trailing-edge debounce loop.

    Args:
        patient_id:   PK of the PatientProfile to evaluate.
        triggered_by: One of 'lab_update', 'medication_change',
                      'prescription_parsed', 'manual', 'trailing_state_change'.

    Returns:
        dict with keys: patient_id, risk_score, alert_created (bool), skipped (bool).
    """
    running_key = f'patient_safety_running_{patient_id}'
    dirty_key = f'patient_safety_dirty_{patient_id}'

    # ── 1. Mark dirty flag & Acquire running execution lock ──────────────────
    try:
        cache.set(dirty_key, 1, timeout=DIRTY_FLAG_TTL)
    except Exception as ex:
        logger.warning('[Safety Task] Failed to set dirty flag for patient %s (cache/Redis down?): %s', patient_id, ex)

    # Skip running lock check on retry attempts (self.request.retries > 0)
    if self.request.retries == 0:
        try:
            acquired = cache.add(running_key, 1, timeout=RUNNING_LOCK_TTL)
        except Exception as ex:
            # CLINICAL SAFETY INVARIANT: If Redis is unavailable, LocMemCache or cache failure
            # must NOT drop safety evaluations. Fail open to execute evaluation safely.
            logger.warning(
                '[Safety Task] Cache lock acquisition error for patient %s: %s. '
                'Failing open to preserve clinical safety (proceeding with evaluation).',
                patient_id, ex
            )
            acquired = True

        if not acquired:
            logger.info(
                '[Safety Task] Patient %s — coalesced with active evaluation (dirty flag marked).',
                patient_id
            )
            return {
                'patient_id': patient_id,
                'risk_score': None,
                'alert_created': False,
                'skipped': True,
                'coalesced': True,
            }

    latest_risk_score = None
    alert_created_any = False

    try:
        # ── 2. Coalescing Trailing-Edge Execution Loop ───────────────────────
        current_trigger = triggered_by
        while True:
            # Clear dirty flag BEFORE loading database snapshot
            try:
                cache.delete(dirty_key)
            except Exception as ex:
                logger.warning('[Safety Task] Error clearing dirty flag for patient %s: %s', patient_id, ex)

            # Load patient profile
            try:
                from patients.models import PatientProfile
                profile = PatientProfile.objects.get(pk=patient_id)
            except PatientProfile.DoesNotExist:
                logger.error('[Safety Task] PatientProfile %s not found — aborting.', patient_id)
                return {'patient_id': patient_id, 'risk_score': None, 'alert_created': False, 'skipped': False}

            logger.info(
                '[Safety Task] Starting safety evaluation for patient %s (trigger: %s).',
                patient_id, current_trigger
            )

            # Run Stage 1 risk engine
            from services.risk_engine import RiskEngine
            engine = RiskEngine()
            evaluation = engine.evaluate_patient_safety(profile)
            new_risk_score = evaluation.get('overall_risk_score', 'Safe')
            latest_risk_score = new_risk_score

            # Persist assessment history
            from patients.models import SafetyAssessmentHistory, ProactiveAlert
            assessment = SafetyAssessmentHistory.objects.create(
                patient=profile,
                risk_score=new_risk_score,
                details=evaluation,
                triggered_by=current_trigger,
            )

            logger.info(
                '[Safety Task] Patient %s — new risk score: %s (triggered by: %s).',
                patient_id, new_risk_score, current_trigger
            )

            # Compare to previous run & generate alert if risk worsened
            previous = (
                SafetyAssessmentHistory.objects
                .filter(patient=profile)
                .exclude(pk=assessment.pk)
                .order_by('-created_at')
                .first()
            )

            new_level = RISK_ORDER.get(new_risk_score, 0)
            prev_level = RISK_ORDER.get(previous.risk_score, 0) if previous else 0

            if new_level > prev_level or (previous is None and new_level >= RISK_ORDER['Moderate']):
                interactions = evaluation.get('interactions', [])
                evidence_refs = evaluation.get('evidence_references', [])

                if interactions:
                    top_interaction = interactions[0]
                    alert_message = (
                        f"Risk flagged: safety level escalated from "
                        f"{'No prior data' if previous is None else previous.risk_score} → {new_risk_score}. "
                        f"Primary concern: {top_interaction.get('description', 'See full assessment for details')} "
                        f"(drug(s): {top_interaction.get('drug_involved', 'N/A')}). "
                        f"Clinical evidence sources: {', '.join(evidence_refs[:3]) if evidence_refs else 'N/A'}."
                    )
                else:
                    alert_message = (
                        f"Risk flagged: safety level escalated from "
                        f"{'No prior data' if previous is None else previous.risk_score} → {new_risk_score}. "
                        f"Review full assessment for clinical evidence and recommendations."
                    )

                ProactiveAlert.objects.create(
                    patient=profile,
                    assessment=assessment,
                    severity=new_risk_score,
                    message=alert_message,
                )
                alert_created_any = True
                logger.warning(
                    '[Safety Task] ALERT created for patient %s — risk escalated to %s.',
                    patient_id, new_risk_score
                )

            # ── 3. Trailing Edge Check ───────────────────────────────────────
            # Did patient state change while this evaluation was in flight?
            is_dirty = False
            try:
                is_dirty = bool(cache.get(dirty_key))
            except Exception as ex:
                logger.warning('[Safety Task] Error reading dirty flag for patient %s: %s', patient_id, ex)

            if not is_dirty:
                break

            logger.info(
                '[Safety Task] Patient %s — trailing state modification detected. Re-evaluating latest state.',
                patient_id
            )
            current_trigger = 'trailing_state_change'

    finally:
        # Guarantee running execution lock is released
        try:
            cache.delete(running_key)
        except Exception as ex:
            logger.warning('[Safety Task] Error deleting running lock for patient %s: %s', patient_id, ex)

        # Boundary Catch-Up Check:
        # If a state change arrived right at the boundary of loop exit or during lock release,
        # schedule a trailing catchup task so no state transition is ever lost.
        try:
            if cache.get(dirty_key):
                logger.info(
                    '[Safety Task] Patient %s — boundary state modification detected during lock release. Dispatching catchup task.',
                    patient_id
                )
                re_evaluate_patient_safety_task.delay(patient_id, triggered_by='trailing_catchup')
        except Exception as ex:
            logger.warning('[Safety Task] Could not dispatch trailing catchup task for patient %s: %s', patient_id, ex)

    return {
        'patient_id': patient_id,
        'risk_score': latest_risk_score,
        'alert_created': alert_created_any,
        'skipped': False,
    }
