import datetime
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from patients.models import PatientProfile, MedicationCabinet
from .models import Prescription
from .serializers import PrescriptionSerializer
from services.ingestion import IngestionPipeline

class PrescriptionViewSet(viewsets.ModelViewSet):
    serializer_class = PrescriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Prescription.objects.filter(patient__user=self.request.user)

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({"error": "No image file provided"}, status=status.HTTP_400_BAD_REQUEST)

        # Get patient profile
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)

        # Save model first to get file path
        prescription = Prescription.objects.create(
            patient=profile,
            image=image_file,
            processed=False
        )

        # Run OCR + NER pipeline
        pipeline = IngestionPipeline()
        extraction = pipeline.process_prescription(prescription.image.file)

        # Update model details
        prescription.extracted_text = extraction.get("raw_text", "")
        prescription.structured_data = extraction.get("medications", [])
        prescription.save()

        serializer = self.get_serializer(prescription)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm(self, request, pk=None):
        prescription = self.get_object()
        if prescription.processed:
            return Response({"error": "Prescription has already been processed"}, status=status.HTTP_400_BAD_REQUEST)

        # Double-check ownership (defence in depth against IDOR)
        if prescription.patient.user != request.user:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        medications_payload = request.data.get('medications')
        if not isinstance(medications_payload, list):
            return Response({"error": "Medications must be provided as a list"}, status=status.HTTP_400_BAD_REQUEST)

        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)

        # Insert confirmed meds into patient's cabinet
        for med in medications_payload:
            MedicationCabinet.objects.create(
                patient=profile,
                name=med.get('name', 'Unknown Drug'),
                dosage=med.get('dosage', 'Unknown Dosage'),
                frequency=med.get('frequency', 'Unknown Frequency'),
                start_date=datetime.date.today(),
                is_active=True
            )

        # Mark prescription as processed
        prescription.processed = True
        prescription.save()

        return Response({"status": "Prescription cabinet additions confirmed"}, status=status.HTTP_200_OK)
