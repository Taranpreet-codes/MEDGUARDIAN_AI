from django.db import models

class EvidenceSource(models.Model):
    filename = models.CharField(max_length=255, unique=True)
    checksum = models.CharField(max_length=64)
    doc_type = models.CharField(max_length=50) # 'WHO_GUIDELINE', 'FDA_LABEL', etc.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} ({self.doc_type})"
