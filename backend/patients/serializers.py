from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import PatientProfile, MedicationCabinet, SafetyAssessmentHistory, ProactiveAlert

class PatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = [
            'id', 'age', 'gender', 'pregnancy_status', 
            'chronic_diseases', 'allergies', 'creatinine', 'egfr'
        ]

    def validate(self, data):
        # Run clean logic on a temporary model instance to raise DjangoValidationError
        # or implement directly to provide specific rest_framework errors
        gender = data.get('gender', self.instance.gender if self.instance else 'O')
        pregnancy_status = data.get('pregnancy_status', self.instance.pregnancy_status if self.instance else False)
        age = data.get('age', self.instance.age if self.instance else 30)

        if pregnancy_status and gender == 'M':
            raise serializers.ValidationError({
                "pregnancy_status": "Pregnancy status cannot be set to true for patients with gender Male."
            })

        if age > 125:
            raise serializers.ValidationError({
                "age": "Age must be less than or equal to 125."
            })

        return data


class MedicationCabinetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicationCabinet
        fields = [
            'id', 'name', 'dosage', 'frequency', 'start_date', 'end_date', 'is_active'
        ]

    def validate(self, data):
        # Check start_date is before end_date if end_date is provided
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({
                "end_date": "End date must be after the start date."
            })
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 Serializers
# ─────────────────────────────────────────────────────────────────────────────

class SafetyAssessmentHistorySerializer(serializers.ModelSerializer):
    """Serializes a single historical safety evaluation for the Risk Timeline."""
    risk_level = serializers.SerializerMethodField()

    class Meta:
        model = SafetyAssessmentHistory
        fields = [
            'id', 'risk_score', 'risk_level', 'details',
            'triggered_by', 'created_at',
        ]
        read_only_fields = fields

    def get_risk_level(self, obj) -> int:
        """Numeric risk rank (0=Safe, 1=Low, 2=Moderate, 3=Severe) for charting."""
        return obj.risk_level()


class ProactiveAlertSerializer(serializers.ModelSerializer):
    """Serializes a proactive alert for delivery to the frontend."""
    assessment_id = serializers.IntegerField(source='assessment.id', read_only=True)
    # Include evidence references so the frontend can link to clinical sources
    evidence_references = serializers.SerializerMethodField()

    class Meta:
        model = ProactiveAlert
        fields = [
            'id', 'severity', 'message', 'acknowledged',
            'created_at', 'assessment_id', 'evidence_references',
        ]
        read_only_fields = ['id', 'severity', 'message', 'created_at', 'assessment_id', 'evidence_references']

    def get_evidence_references(self, obj) -> list:
        """Pull evidence_references from the linked assessment details."""
        return obj.assessment.details.get('evidence_references', [])
