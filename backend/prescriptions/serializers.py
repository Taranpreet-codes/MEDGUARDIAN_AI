from rest_framework import serializers
from .models import Prescription

class PrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        fields = [
            'id', 'image', 'extracted_text', 'structured_data', 'processed', 'created_at'
        ]
        read_only_fields = ['extracted_text', 'structured_data', 'processed', 'created_at']
