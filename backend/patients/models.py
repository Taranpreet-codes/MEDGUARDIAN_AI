from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

# ─────────────────────────────────────────────────────────────────────────────
# Core Patient Models (Stage 1)
# ─────────────────────────────────────────────────────────────────────────────

class PatientProfile(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    age = models.PositiveIntegerField(default=30)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='O')
    pregnancy_status = models.BooleanField(default=False)

    # Store conditions and allergies as JSON lists
    chronic_diseases = models.JSONField(default=list, blank=True)
    allergies = models.JSONField(default=list, blank=True)

    # Lab metrics (Kidney/Liver function, etc.)
    creatinine = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # mg/dL
    egfr = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # mL/min/1.73m²

    def clean(self):
        if self.creatinine is not None and self.creatinine < 0:
            raise ValidationError({'creatinine': 'Creatinine must be a non-negative value.'})
        if self.egfr is not None and self.egfr < 0:
            raise ValidationError({'egfr': 'eGFR must be a non-negative value.'})

        # Validation: pregnancy is only allowed for Female or Other genders
        if self.pregnancy_status and self.gender == 'M':
            raise ValidationError({
                'pregnancy_status': "Pregnancy status cannot be set to true for patients with gender Male."
            })
        if self.age > 125:
            raise ValidationError({
                'age': "Age must be less than or equal to 125."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class MedicationCabinet(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='medications')
    name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.dosage}) for {self.patient.user.username}"


class InteractionLog(models.Model):
    """Stage 1 legacy log — kept for backward compatibility alongside SafetyAssessmentHistory."""
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='interaction_logs')
    risk_score = models.CharField(max_length=50)  # 'Severe', 'Moderate', 'Low', 'Safe'
    details = models.JSONField(default=dict)  # {interactions: [...], evidence_references: [...], clinician_notes: "..."}
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Safety Log for {self.patient.user.username} - {self.risk_score} ({self.created_at.strftime('%Y-%m-%d')})"


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 Models: Proactive Monitoring History & Alerts
# ─────────────────────────────────────────────────────────────────────────────

RISK_ORDER = {'Safe': 0, 'Low': 1, 'Moderate': 2, 'Severe': 3}


class SafetyAssessmentHistory(models.Model):
    """Timestamped record of every proactive safety evaluation run by Celery."""

    TRIGGER_CHOICES = [
        ('lab_update', 'Lab Metric Updated'),
        ('medication_change', 'Medication Cabinet Modified'),
        ('prescription_parsed', 'Prescription Parsing Completed'),
        ('manual', 'Manual Safety Check'),
    ]

    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name='safety_history'
    )
    risk_score = models.CharField(max_length=50)  # Severe / Moderate / Low / Safe
    details = models.JSONField(default=dict)       # Full evaluation payload incl. evidence_references
    triggered_by = models.CharField(max_length=50, choices=TRIGGER_CHOICES, default='manual')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def risk_level(self) -> int:
        """Numeric rank of the risk score for comparison (higher = worse)."""
        return RISK_ORDER.get(self.risk_score, 0)

    def __str__(self):
        return (
            f"Assessment for {self.patient.user.username} — "
            f"{self.risk_score} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
        )


class ProactiveAlert(models.Model):
    """An alert generated when the risk level worsens between two consecutive evaluations."""

    SEVERITY_CHOICES = [
        ('Severe', 'Severe'),
        ('Moderate', 'Moderate'),
        ('Low', 'Low'),
    ]

    patient = models.ForeignKey(
        PatientProfile, on_delete=models.CASCADE, related_name='proactive_alerts'
    )
    assessment = models.ForeignKey(
        SafetyAssessmentHistory, on_delete=models.CASCADE, related_name='alerts'
    )
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    message = models.TextField()
    acknowledged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = 'ACK' if self.acknowledged else 'UNREAD'
        return (
            f"[{status}] {self.severity} Alert for "
            f"{self.patient.user.username} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 Signals: Trigger Celery re-evaluation on data changes
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=PatientProfile)
def on_patient_profile_saved(sender, instance, created, **kwargs):
    """
    Fire a background safety re-evaluation whenever the patient's lab metrics
    or clinical attributes (pregnancy, allergies, eGFR etc.) are updated.
    Skip on initial creation since there are no medications yet.
    """
    if not created:
        from django.core.cache import cache
        from patients.tasks import re_evaluate_patient_safety_task, DIRTY_FLAG_TTL
        try:
            cache.set(f'patient_safety_dirty_{instance.pk}', 1, timeout=DIRTY_FLAG_TTL)
        except Exception:
            pass
        re_evaluate_patient_safety_task.delay(instance.pk, triggered_by='lab_update')


@receiver(post_save, sender=MedicationCabinet)
def on_medication_cabinet_saved(sender, instance, **kwargs):
    """
    Fire a background safety re-evaluation whenever a medication is added,
    edited, or deactivated in the patient's cabinet.
    """
    patient_id = getattr(instance, 'patient_id', None) or (instance.patient.pk if instance.patient else None)
    if patient_id:
        from django.core.cache import cache
        from patients.tasks import re_evaluate_patient_safety_task, DIRTY_FLAG_TTL
        try:
            cache.set(f'patient_safety_dirty_{patient_id}', 1, timeout=DIRTY_FLAG_TTL)
        except Exception:
            pass
        re_evaluate_patient_safety_task.delay(
            patient_id, triggered_by='medication_change'
        )


@receiver(post_delete, sender=MedicationCabinet)
def on_medication_cabinet_deleted(sender, instance, **kwargs):
    """
    Fire a background safety re-evaluation whenever a medication is deleted
    from the patient's cabinet.
    """
    patient_id = getattr(instance, 'patient_id', None) or (instance.patient.pk if instance.patient else None)
    if patient_id:
        from django.core.cache import cache
        from patients.tasks import re_evaluate_patient_safety_task, DIRTY_FLAG_TTL
        try:
            cache.set(f'patient_safety_dirty_{patient_id}', 1, timeout=DIRTY_FLAG_TTL)
        except Exception:
            pass
        re_evaluate_patient_safety_task.delay(
            patient_id, triggered_by='medication_change'
        )
