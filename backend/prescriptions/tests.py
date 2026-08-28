import json
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from patients.models import PatientProfile, MedicationCabinet
from prescriptions.models import Prescription
from django.core.files.uploadedfile import SimpleUploadedFile

class PrescriptionIngestionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testpatient', password='password123')
        self.profile = PatientProfile.objects.create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_upload_requires_authentication(self):
        self.client.force_authenticate(user=None)
        url = reverse('prescription-upload')
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_upload_missing_image(self):
        url = reverse('prescription-upload')
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_upload_success_and_mock_parsing(self):
        # Create a mock image file
        image_content = b"fake image data"
        image = SimpleUploadedFile("prescription.jpg", image_content, content_type="image/jpeg")

        url = reverse('prescription-upload')
        response = self.client.post(url, {'image': image}, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("extracted_text", response.data)
        self.assertIn("structured_data", response.data)
        
        # Verify Prescription object exists in DB
        prescription = Prescription.objects.get(id=response.data["id"])
        self.assertEqual(prescription.patient, self.profile)
        self.assertFalse(prescription.processed)
        # Should populate mock medications on fallback
        self.assertTrue(len(prescription.structured_data) > 0)

    def test_confirm_prescription(self):
        # Create a mock processed prescription
        prescription = Prescription.objects.create(
            patient=self.profile,
            image="prescriptions/dummy.jpg",
            extracted_text="Metformin 500mg once daily",
            structured_data=[{"name": "Metformin", "dosage": "500mg", "frequency": "once daily"}],
            processed=False
        )

        url = reverse('prescription-confirm', args=[prescription.id])
        payload = {
            "medications": [
                {"name": "Metformin", "dosage": "500mg", "frequency": "once daily"}
            ]
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check DB updates
        prescription.refresh_from_db()
        self.assertTrue(prescription.processed)

        # Check MedicationCabinet additions
        cabinet_meds = MedicationCabinet.objects.filter(patient=self.profile)
        self.assertEqual(cabinet_meds.count(), 1)
        self.assertEqual(cabinet_meds.first().name, "Metformin")
        self.assertEqual(cabinet_meds.first().dosage, "500mg")
        self.assertEqual(cabinet_meds.first().frequency, "once daily")
        self.assertTrue(cabinet_meds.first().is_active)
