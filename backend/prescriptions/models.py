from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from patients.models import PatientProfile


class Prescription(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='prescriptions')
    image = models.ImageField(upload_to='prescriptions/')
    extracted_text = models.TextField(blank=True, default='')
    structured_data = models.JSONField(blank=True, default=list)  # [{name: string, dosage: string, frequency: string}]
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prescription for {self.patient.user.username} - {self.created_at.strftime('%Y-%m-%d')}"


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 Signal: Re-evaluate safety after prescription NER completes
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=Prescription)
def on_prescription_processed(sender, instance, created, **kwargs):
    """
    Fire a background safety re-evaluation only when a prescription transitions
    to processed=True (i.e., drugs have been extracted and added to the cabinet).
    Avoids triggering on initial upload (processed=False).
    """
    if instance.processed and not created:
        from django.core.cache import cache
        from patients.tasks import re_evaluate_patient_safety_task, DIRTY_FLAG_TTL
        try:
            cache.set(f'patient_safety_dirty_{instance.patient.pk}', 1, timeout=DIRTY_FLAG_TTL)
        except Exception:
            pass
        re_evaluate_patient_safety_task.delay(
            instance.patient.pk, triggered_by='prescription_parsed'
        )
