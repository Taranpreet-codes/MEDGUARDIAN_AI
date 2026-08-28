import os
import json
import datetime
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from patients.models import PatientProfile, MedicationCabinet, InteractionLog
from prescriptions.models import Prescription
from services.ingestion import IngestionPipeline
from services.rag import RAGEngine
from services.risk_engine import RiskEngine

class Stage1SystemVerificationTest(TestCase):
    """
    Comprehensive Integration Test Suite to programmatically verify Stage 1 features:
    - User Authentication and Profile CRUD (including profile safety validations).
    - Prescription Ingestion (with mocked OCR/NER vision layer).
    - Interaction Engine Triggering (verifying the fallback path and evidence checks).
    """

    def setUp(self):
        self.client = APIClient()
        self.username = "auditpatient"
        self.password = "Secr3tP@ssword!"
        self.email = "audit@medguardian.ai"
        
        # Prevent tests from calling live Gemini endpoints and hitting rate limits
        self.env_patcher = patch.dict(os.environ, {"GEMINI_API_KEY": ""})
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_01_user_authentication_and_profile_crud(self):
        """1. User Registration, Authentication (JWT), and Profile CRUD validation"""
        # Step A: Register new user
        register_url = reverse('auth-register')
        reg_payload = {
            "username": self.username,
            "password": self.password,
            "email": self.email
        }
        response = self.client.post(register_url, reg_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["username"], self.username)
        
        # Capture tokens
        access_token = response.data["access"]
        refresh_token = response.data["refresh"]

        # Step B: Log in via Token Obtain Pair
        login_url = reverse('auth-token-obtain')
        login_payload = {
            "username": self.username,
            "password": self.password
        }
        response = self.client.post(login_url, login_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        access_token = response.data["access"]

        # Step C: Token Refresh
        refresh_url = reverse('auth-token-refresh')
        refresh_payload = {
            "refresh": refresh_token
        }
        response = self.client.post(refresh_url, refresh_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        access_token = response.data["access"]

        # Set Authorization header
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

        # Step D: Read Patient Profile (should exist automatically due to registration view log)
        profile_url = reverse('patient-profile')
        response = self.client.get(profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["age"], 30) # default value
        self.assertEqual(response.data["gender"], 'O') # default value

        # Step E: Update Profile (valid fields)
        update_payload = {
            "age": 45,
            "gender": "F",
            "pregnancy_status": True,
            "allergies": ["penicillin", "sulfa"],
            "chronic_diseases": ["hypertension", "diabetes"],
            "creatinine": "1.10",
            "egfr": "75.50"
        }
        response = self.client.put(profile_url, update_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["age"], 45)
        self.assertEqual(response.data["gender"], "F")
        self.assertTrue(response.data["pregnancy_status"])
        self.assertEqual(response.data["allergies"], ["penicillin", "sulfa"])

        # Step F: Verify constraints (e.g. Male cannot be pregnant)
        invalid_payload = {
            "gender": "M",
            "pregnancy_status": True
        }
        response = self.client.patch(profile_url, invalid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pregnancy_status", response.data)

        # Step G: Verify age limit boundary (age > 125)
        invalid_age_payload = {
            "age": 130
        }
        response = self.client.patch(profile_url, invalid_age_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("age", response.data)

    @patch('services.ingestion.IngestionPipeline.process_prescription')
    def test_02_prescription_ingestion_and_confirmation(self, mock_process):
        """2. Upload prescription image, mock OCR/NER, review extraction, and confirm cabinet update"""
        # Register and authenticate user
        user = User.objects.create_user(username="prescpatient", password="password123")
        profile = PatientProfile.objects.create(user=user, age=28, gender="F")
        self.client.force_authenticate(user=user)

        # Mock the vision pipeline extraction
        mock_process.return_value = {
            "raw_text": "Rx: Metformin 500mg once daily. Lisinopril 10mg once daily.",
            "medications": [
                {"name": "Metformin", "dosage": "500mg", "frequency": "once daily"},
                {"name": "Lisinopril", "dosage": "10mg", "frequency": "once daily"}
            ]
        }

        # Step A: Upload mock prescription image
        from django.core.files.uploadedfile import SimpleUploadedFile
        image_content = b"sample-bytes-representing-a-prescription-image"
        prescription_image = SimpleUploadedFile("rx_prescription.jpg", image_content, content_type="image/jpeg")

        upload_url = reverse('prescription-upload')
        response = self.client.post(upload_url, {"image": prescription_image}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["processed"], False)
        self.assertEqual(response.data["extracted_text"], mock_process.return_value["raw_text"])
        self.assertEqual(response.data["structured_data"], mock_process.return_value["medications"])

        prescription_id = response.data["id"]

        # Step B: Confirm the prescription (programmatically add to cabinet)
        confirm_url = reverse('prescription-confirm', args=[prescription_id])
        confirm_payload = {
            "medications": [
                {"name": "Metformin", "dosage": "500mg", "frequency": "once daily"},
                {"name": "Lisinopril", "dosage": "10mg", "frequency": "once daily"}
            ]
        }
        response = self.client.post(confirm_url, confirm_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify database model is marked processed
        prescription = Prescription.objects.get(id=prescription_id)
        self.assertTrue(prescription.processed)

        # Verify active cabinet contains the confirmed medications
        cabinet_meds = MedicationCabinet.objects.filter(patient=profile, is_active=True)
        self.assertEqual(cabinet_meds.count(), 2)
        med_names = {m.name for m in cabinet_meds}
        self.assertEqual(med_names, {"Metformin", "Lisinopril"})

    @patch('services.rag.RAGEngine.retrieve_evidence')
    def test_03_interaction_engine_and_safety_verification_fallback(self, mock_retrieve):
        """3. Trigger safety checks, verify pregnancy/drug alerts, and test Chat-RAG fallback paths"""
        # Register and authenticate user
        user = User.objects.create_user(username="riskpatient", password="password123")
        profile = PatientProfile.objects.create(
            user=user, 
            age=32, 
            gender="F", 
            pregnancy_status=True, # Pregnant
            allergies=["penicillin"] # Penicillin allergy
        )
        self.client.force_authenticate(user=user)

        # Add conflicting medications to cabinet
        MedicationCabinet.objects.create(
            patient=profile,
            name="Lisinopril",
            dosage="10mg",
            frequency="once daily",
            start_date=datetime.date.today(),
            is_active=True
        )
        MedicationCabinet.objects.create(
            patient=profile,
            name="Amoxicillin",
            dosage="500mg",
            frequency="three times daily",
            start_date=datetime.date.today(),
            is_active=True
        )

        # Mock RAG to return empty lists to test fallback paths safely without actual Chroma DB data
        mock_retrieve.return_value = []

        # Step A: Trigger safety check endpoint
        safety_url = reverse('patient-safety-check')
        response = self.client.get(safety_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify overall risk and alerts are generated correctly via local rules (fallback path)
        self.assertEqual(response.data["overall_risk_score"], "Severe")
        
        descriptions = [i["description"].lower() for i in response.data["interactions"]]
        
        # Check pregnancy contraindication is triggered
        self.assertTrue(any("contraindicated in pregnancy" in d or "fetal toxicity" in d for d in descriptions))
        
        # Check allergy warning is triggered
        self.assertTrue(any("allergic" in d or "allergy" in d for d in descriptions))

        # Verify InteractionLog has been created in DB
        logs = InteractionLog.objects.filter(patient=profile)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().risk_score, "Severe")

        # Step B: Hit Chat Assistant endpoint with a valid clinical pregnancy safety question
        chat_url = reverse('patient-chat-ask')
        chat_payload_pregnancy = {
            "query": "Is Lisinopril safe to take while I am pregnant?"
        }
        
        # With no valid GEMINI_API_KEY in test environment, it should hit run_mock_fallback()
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            response = self.client.post(chat_url, chat_payload_pregnancy, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("response", response.data)
            self.assertIn("Lisinopril is contraindicated during pregnancy", response.data["response"])
            self.assertTrue(len(response.data["citations"]) > 0)
            self.assertEqual(response.data["citations"][0]["source"], "WHO_guideline_hypertension.pdf")

        # Step C: Hit Chat Assistant endpoint with an unrelated question (verifying full fallback response)
        chat_payload_unrelated = {
            "query": "Can you tell me how to bake chocolate chip cookies?"
        }
        
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            response = self.client.post(chat_url, chat_payload_unrelated, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("response", response.data)
            # Must strictly return the clinical evidence warning string
            self.assertEqual(
                response.data["response"], 
                "I cannot find enough clinical evidence to safely answer this question."
            )
            self.assertEqual(len(response.data["citations"]), 0)
