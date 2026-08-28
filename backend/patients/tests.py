from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from patients.models import PatientProfile, MedicationCabinet, InteractionLog
import datetime
import os
from unittest.mock import patch

class PatientProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testpatient', password='password123')

    def test_profile_creation_defaults(self):
        profile = PatientProfile.objects.create(user=self.user)
        self.assertEqual(profile.age, 30)
        self.assertEqual(profile.gender, 'O')
        self.assertFalse(profile.pregnancy_status)

    def test_male_cannot_be_pregnant(self):
        profile = PatientProfile(user=self.user, gender='M', pregnancy_status=True)
        with self.assertRaises(ValidationError) as ctx:
            profile.save()
        self.assertIn('pregnancy_status', ctx.exception.message_dict)

    def test_female_can_be_pregnant(self):
        profile = PatientProfile(user=self.user, gender='F', pregnancy_status=True)
        try:
            profile.save()
        except ValidationError:
            self.fail("ValidationError raised unexpectedly for pregnant female patient.")

    def test_other_can_be_pregnant(self):
        profile = PatientProfile(user=self.user, gender='O', pregnancy_status=True)
        try:
            profile.save()
        except ValidationError:
            self.fail("ValidationError raised unexpectedly for pregnant other patient.")

    def test_age_boundary(self):
        profile = PatientProfile(user=self.user, age=130)
        with self.assertRaises(ValidationError) as ctx:
            profile.save()
        self.assertIn('age', ctx.exception.message_dict)


class MedicationCabinetModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testpatient', password='password123')
        self.profile = PatientProfile.objects.create(user=self.user)

    def test_medication_cabinet_creation(self):
        med = MedicationCabinet.objects.create(
            patient=self.profile,
            name="Metformin",
            dosage="500mg",
            frequency="once daily",
            start_date=datetime.date.today(),
            is_active=True
        )
        self.assertEqual(med.name, "Metformin")
        self.assertTrue(med.is_active)
        self.assertEqual(str(med), "Metformin (500mg) for testpatient")


class RiskEngineTest(TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(os.environ, {"GEMINI_API_KEY": ""})
        self.env_patcher.start()
        self.user = User.objects.create_user(username='testpatient', password='password123')
        self.profile = PatientProfile.objects.create(user=self.user, age=32, gender='F', pregnancy_status=False)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        self.env_patcher.stop()

    def test_pregnant_lisinopril_severe_risk(self):
        # 1. Add Lisinopril
        MedicationCabinet.objects.create(
            patient=self.profile,
            name="Lisinopril",
            dosage="10mg",
            frequency="once daily",
            start_date=datetime.date.today()
        )
        
        # 2. Mark patient pregnant
        self.profile.pregnancy_status = True
        self.profile.save()

        # 3. Evaluate safety check
        url = reverse('patient-profile') + 'safety-check/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["overall_risk_score"], "Severe")
        self.assertTrue(len(response.data["interactions"]) > 0)
        desc = response.data["interactions"][0]["description"].lower()
        self.assertTrue("contraindicated" in desc and ("pregnancy" in desc or "pregnant" in desc))

    def test_spironolactone_lisinopril_severe_interaction(self):
        # Add Lisinopril and Spironolactone
        MedicationCabinet.objects.create(
            patient=self.profile,
            name="Lisinopril",
            dosage="10mg",
            frequency="once daily",
            start_date=datetime.date.today()
        )
        MedicationCabinet.objects.create(
            patient=self.profile,
            name="Spironolactone",
            dosage="25mg",
            frequency="once daily",
            start_date=datetime.date.today()
        )

        url = reverse('patient-profile') + 'safety-check/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["overall_risk_score"], "Severe")
        # Check interaction alert details
        descriptions = [i["description"].lower() for i in response.data["interactions"]]
        self.assertTrue(any("hyperkalemia" in desc for desc in descriptions))

    def test_allergy_warning(self):
        # Add Penicillin allergy
        self.profile.allergies = ["penicillin"]
        self.profile.save()

        # Add Amoxicillin med
        MedicationCabinet.objects.create(
            patient=self.profile,
            name="Amoxicillin",
            dosage="500mg",
            frequency="twice daily",
            start_date=datetime.date.today()
        )

        url = reverse('patient-profile') + 'safety-check/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["overall_risk_score"], "Severe")
        descriptions = [i["description"].lower() for i in response.data["interactions"]]
        self.assertTrue(any("allerg" in desc or "allergy" in desc or "hypersensitivity" in desc for desc in descriptions))


class ChatAndReportsTest(TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(os.environ, {"GEMINI_API_KEY": ""})
        self.env_patcher.start()
        self.user = User.objects.create_user(username='testpatient', password='password123')
        self.profile = PatientProfile.objects.create(user=self.user, age=30, gender='F')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        self.env_patcher.stop()

    def test_grounded_chat_success(self):
        url = reverse('patient-profile') + 'chat-ask/'
        response = self.client.post(url, {"query": "What are the pregnancy guidelines for Lisinopril?"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("response", response.data)
        response_text = response.data["response"].lower()
        self.assertIn("lisinopril", response_text)
        self.assertIn("contraindicated", response_text)
        self.assertTrue("pregnancy" in response_text or "pregnant" in response_text)
        self.assertTrue(len(response.data["citations"]) > 0)

    def test_ungrounded_chat_fallback(self):
        url = reverse('patient-profile') + 'chat-ask/'
        response = self.client.post(url, {"query": "How do I bake a chocolate cake?"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["response"], "I cannot find enough clinical evidence to safely answer this question.")

    def test_patient_pdf_report(self):
        url = reverse('patient-profile') + 'report-patient/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)

    def test_clinician_pdf_report(self):
        url = reverse('patient-profile') + 'report-clinician/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)


class PDFGenerationRobustnessTest(TestCase):
    """
    BUG FIX Verification Test Suite:
    Guarantees robust PDF report generation when clinical data, medication names,
    patient profile attributes, AI explanations, and RAG citations contain special
    markup characters (<, >, &, quotes, unclosed tags) and supported Unicode characters.
    """

    def setUp(self):
        self.env_patcher = patch.dict(os.environ, {"GEMINI_API_KEY": ""})
        self.env_patcher.start()

        # Disconnect stage 2 celery signals to isolate PDF test assertions
        from django.db.models.signals import post_save, post_delete
        from patients.models import on_patient_profile_saved, on_medication_cabinet_saved, on_medication_cabinet_deleted
        post_save.disconnect(on_patient_profile_saved, sender=PatientProfile)
        post_save.disconnect(on_medication_cabinet_saved, sender=MedicationCabinet)
        post_delete.disconnect(on_medication_cabinet_deleted, sender=MedicationCabinet)

        from decimal import Decimal
        self.user = User.objects.create_user(username='synth_pdf_patient', password='password123')
        self.profile = PatientProfile.objects.create(
            user=self.user,
            age=45,
            gender='M',
            pregnancy_status=False,
            egfr=Decimal('45.00'),
            creatinine=Decimal('1.80'),
            allergies=['Penicillin <G>', 'Sulfa & Trimethoprim'],
            chronic_diseases=['Hypertension & CKD <Stage 3>']
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        self.env_patcher.stop()
        from django.db.models.signals import post_save, post_delete
        from patients.models import on_patient_profile_saved, on_medication_cabinet_saved, on_medication_cabinet_deleted
        post_save.connect(on_patient_profile_saved, sender=PatientProfile)
        post_save.connect(on_medication_cabinet_saved, sender=MedicationCabinet)
        post_delete.connect(on_medication_cabinet_deleted, sender=MedicationCabinet)

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        """Helper to extract all text from PDF bytes via pypdf."""
        import io
        import re
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        extracted = []
        for page in reader.pages:
            extracted.append(page.extract_text() or "")
        raw = " ".join(extracted)
        # Normalize consecutive whitespace/newlines to single space for robust substring assertions
        return re.sub(r'\s+', ' ', raw)

    # ── Test 1: Normal PDF Generation ────────────────────────────────────────
    def test_patient_pdf_normal_data(self):
        """Standard patient data generates a valid non-empty PDF with %PDF- header."""
        from datetime import date
        MedicationCabinet.objects.create(
            patient=self.profile,
            name='Metformin',
            dosage='500mg',
            frequency='twice daily',
            start_date=date.today(),
            is_active=True
        )
        url = reverse('patient-profile') + 'report-patient/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))
        
        text = self._extract_pdf_text(response.content)
        self.assertIn("MedGuardian AI", text)
        self.assertIn("Metformin", text)

    # ── Test 2: Special Character '<' in Clinical Text ───────────────────────
    def test_patient_pdf_special_char_less_than(self):
        """Clinical text containing '<' (e.g. 'Blood pressure < 120 mmHg') is preserved."""
        InteractionLog.objects.create(
            patient=self.profile,
            risk_score='Moderate',
            details={
                'interactions': [
                    {
                        'drug_involved': 'Lisinopril',
                        'severity': 'Moderate',
                        'description': 'Target systolic blood pressure < 120 mmHg for optimal renal protection.'
                    }
                ]
            }
        )
        url = reverse('patient-profile') + 'report-patient/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        text = self._extract_pdf_text(response.content)
        self.assertIn("< 120", text)
        self.assertIn("Lisinopril", text)

    # ── Test 3: Special Character '>' in Clinical Text ───────────────────────
    def test_patient_pdf_special_char_greater_than(self):
        """Clinical text containing '>' (e.g. 'Medication > recommended dose') is preserved."""
        InteractionLog.objects.create(
            patient=self.profile,
            risk_score='Severe',
            details={
                'interactions': [
                    {
                        'drug_involved': 'Simvastatin',
                        'severity': 'Severe',
                        'description': 'Administered dose > recommended maximum 40mg/day when combined with amlodipine.'
                    }
                ]
            }
        )
        url = reverse('patient-profile') + 'report-patient/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        text = self._extract_pdf_text(response.content)
        self.assertIn("> recommended", text)

    # ── Test 4: Special Character '&' in Clinical Text ───────────────────────
    def test_patient_pdf_special_char_ampersand(self):
        """Clinical text containing '&' (e.g. 'Patient has mild & moderate symptoms') is preserved."""
        InteractionLog.objects.create(
            patient=self.profile,
            risk_score='Low',
            details={
                'interactions': [
                    {
                        'drug_involved': 'Amoxicillin & Clavulanate',
                        'severity': 'Low',
                        'description': 'Patient has mild & moderate symptoms with food & drink.'
                    }
                ]
            }
        )
        url = reverse('patient-profile') + 'report-patient/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        text = self._extract_pdf_text(response.content)
        self.assertIn("Amoxicillin & Clavulanate", text)
        self.assertIn("mild & moderate", text)

    # ── Test 5: Combined Special Characters (<, >, &) ────────────────────────
    def test_patient_pdf_combined_special_chars(self):
        """Combined expression 'Blood pressure < 120 & pulse > 100' is rendered without errors."""
        InteractionLog.objects.create(
            patient=self.profile,
            risk_score='Moderate',
            details={
                'interactions': [
                    {
                        'drug_involved': 'Metoprolol & Hydrochlorothiazide',
                        'severity': 'Moderate',
                        'description': 'Blood pressure < 120 & pulse > 100 with eGFR < 60 mL/min.'
                    }
                ]
            }
        )
        url = reverse('patient-profile') + 'report-patient/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        text = self._extract_pdf_text(response.content)
        self.assertIn("< 120 & pulse > 100", text)
        self.assertIn("< 60", text)

    # ── Test 6: Medication Names and Fields with Special Characters ──────────
    def test_patient_pdf_medication_special_chars(self):
        """Medication fields with bracketed notation (e.g. <Augmentin>, <unclosed) do not crash and preserve text."""
        from datetime import date
        MedicationCabinet.objects.create(
            patient=self.profile,
            name='Amoxicillin & Clavulanate <Augmentin>',
            dosage='500mg < 1000mg',
            frequency='BID & PRN <severe>',
            start_date=date.today(),
            is_active=True
        )
        MedicationCabinet.objects.create(
            patient=self.profile,
            name='Drug <unclosed',
            dosage='10mg',
            frequency='daily',
            start_date=date.today(),
            is_active=True
        )
        url = reverse('patient-profile') + 'report-patient/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        text = self._extract_pdf_text(response.content)
        self.assertIn("Amoxicillin & Clavulanate <Augmentin>", text)
        self.assertIn("500mg < 1000mg", text)
        self.assertIn("BID & PRN <severe>", text)
        self.assertIn("Drug <unclosed", text)

    # ── Test 7: AI-Generated Explanations with Special Characters ────────────
    def test_patient_pdf_ai_generated_explanation(self):
        """AI explanations containing quotes, apostrophes, and nested math symbols render safely."""
        InteractionLog.objects.create(
            patient=self.profile,
            risk_score='Severe',
            details={
                'interactions': [
                    {
                        'drug_involved': 'Warfarin <Coumadin> & Aspirin',
                        'severity': 'Severe',
                        'description': 'AI Assessment: Concomitant use increases INR > 3.5 & bleeding risk by > 2.5x. Patient\'s eGFR is < 30 mL/min.'
                    }
                ]
            }
        )
        url = reverse('patient-profile') + 'report-patient/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        text = self._extract_pdf_text(response.content)
        self.assertIn("Warfarin <Coumadin> & Aspirin", text)
        self.assertIn("INR > 3.5 & bleeding risk by > 2.5x", text)
        self.assertIn("< 30 mL/min", text)

    # ── Test 8: Supported Unicode and Medical Characters ──────────────────────
    def test_patient_pdf_unicode_characters(self):
        """Supported Unicode accents, scientific units (°C, m², µg), and dashes render cleanly."""
        self.profile.allergies = ['Penicilina sódica', 'Sulfa & Café']
        self.profile.chronic_diseases = ['Insuficiencia renal crónica — Estadio 3']
        self.profile.save()

        from datetime import date
        MedicationCabinet.objects.create(
            patient=self.profile,
            name='Levothyroxine 50 µg',
            dosage='50µg',
            frequency='once daily in morning',
            start_date=date.today(),
            is_active=True
        )
        InteractionLog.objects.create(
            patient=self.profile,
            risk_score='Safe',
            details={
                'interactions': [
                    {
                        'drug_involved': 'Levothyroxine',
                        'severity': 'Safe',
                        'description': 'Body temperature 37.5°C with eGFR 45 mL/min/1.73m² and “verified” tolerance ± 5%.'
                    }
                ]
            }
        )
        url = reverse('patient-profile') + 'report-patient/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        text = self._extract_pdf_text(response.content)
        self.assertIn("Penicilina", text)
        self.assertIn("37.5", text)
        self.assertIn("50", text)

    # ── Test 9: Clinician Dossier Report with All Special Characters ─────────
    def test_clinician_pdf_all_special_chars(self):
        """Clinician safety dossier correctly escapes all lab data, notes, and RAG references."""
        from datetime import date
        MedicationCabinet.objects.create(
            patient=self.profile,
            name='Lisinopril & HCTZ <10/12.5>',
            dosage='10mg < 20mg',
            frequency='daily & PRN',
            start_date=date.today(),
            is_active=True
        )
        InteractionLog.objects.create(
            patient=self.profile,
            risk_score='Severe',
            details={
                'interactions': [
                    {
                        'drug_involved': 'Lisinopril <ACEi> & Potassium',
                        'severity': 'Severe',
                        'description': 'Serum K+ > 5.5 mEq/L & Creatinine > 2.0 mg/dL with eGFR < 30.'
                    }
                ],
                'clinician_notes': 'Clinical audit: Blood pressure < 120 mmHg & pulse > 100 bpm. Dose > recommended.',
                'evidence_references': ['FDA Black Box Warning <2023> & PubMed: 98765432', 'KDIGO Guideline: eGFR < 45']
            }
        )
        url = reverse('patient-profile') + 'report-clinician/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        text = self._extract_pdf_text(response.content)
        self.assertIn("Lisinopril & HCTZ <10/12.5>", text)
        self.assertIn("Lisinopril <ACEi> & Potassium", text)
        self.assertIn("Serum K+ > 5.5", text)
        self.assertIn("Blood pressure < 120 mmHg & pulse > 100 bpm", text)
        self.assertIn("FDA Black Box Warning <2023> & PubMed: 98765432", text)
        self.assertIn("KDIGO Guideline: eGFR < 45", text)

    # ── Test 10: Input Markup Safety (Literal Rendering) ─────────────────────
    def test_pdf_markup_safety_literal_rendering(self):
        """HTML-like strings such as '<script>alert(1)</script>' are rendered literally without crashing."""
        from datetime import date
        MedicationCabinet.objects.create(
            patient=self.profile,
            name='<script>alert(1)</script>',
            dosage='10mg <tag>',
            frequency='BID',
            start_date=date.today(),
            is_active=True
        )
        InteractionLog.objects.create(
            patient=self.profile,
            risk_score='Low',
            details={
                'interactions': [
                    {
                        'drug_involved': '<b>FakeBold</b>',
                        'severity': 'Low',
                        'description': '<invalid attr="test">Text inside tag</invalid> & <unclosed'
                    }
                ]
            }
        )
        url = reverse('patient-profile') + 'report-patient/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        text = self._extract_pdf_text(response.content)
        self.assertIn("<script>alert(1)</script>", text)
        self.assertIn("<b>FakeBold</b>", text)
        self.assertIn("<invalid attr=\"test\">Text inside tag</invalid>", text)
        self.assertIn("<unclosed", text)

    # ── Test 11: Defensive Error Handling in Views ───────────────────────────
    def test_pdf_view_defensive_error_handling(self):
        """If ReportService encounters an unhandled error, API returns clean 500 JSON without leaking PHI."""
        from services.reports import ReportService
        with patch.object(ReportService, 'generate_patient_report', side_effect=RuntimeError("Simulated ReportLab Engine Error")):
            url = reverse('patient-profile') + 'report-patient/'
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertIn("error", response.data)
            self.assertEqual(response.data["error"], "Failed to generate patient safety report. Please try again later.")

        with patch.object(ReportService, 'generate_clinician_report', side_effect=RuntimeError("Simulated ReportLab Engine Error")):
            url = reverse('patient-profile') + 'report-clinician/'
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertIn("error", response.data)
            self.assertEqual(response.data["error"], "Failed to generate clinician safety dossier. Please try again later.")

    # ── Test 12: PDF Binary Validity ─────────────────────────────────────────
    def test_pdf_binary_validity(self):
        """Verifies both generated PDFs are structurally valid PDFs parseable by pypdf."""
        from services.reports import ReportService
        patient_pdf = ReportService.generate_patient_report(self.profile)
        clinician_pdf = ReportService.generate_clinician_report(self.profile)

        import io
        import pypdf
        r_patient = pypdf.PdfReader(io.BytesIO(patient_pdf))
        self.assertGreater(len(r_patient.pages), 0)
        self.assertFalse(r_patient.is_encrypted)

        r_clinician = pypdf.PdfReader(io.BytesIO(clinician_pdf))
        self.assertGreater(len(r_clinician.pages), 0)
        self.assertFalse(r_clinician.is_encrypted)



