"""
services/providers/curated_ddi_provider.py — Curated Clinical Drug-Drug Interaction Provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
High-quality, versioned structured DDI dataset derived from validated clinical
sources (DDInter 2.0 / ONCHigh / FDA Package Inserts).

Provides deterministic, zero-latency, offline-capable interaction screening
with standardized severity tiers:
- Contraindicated
- Severe
- Moderate
- Minor
"""
import os
import json
import logging
from typing import List, Dict, Tuple, Optional

try:
    from django.conf import settings
except ImportError:
    settings = None

from .base import BaseInteractionProvider
from .models import NormalizedDrug, InteractionAlert

logger = logging.getLogger(__name__)


class CuratedDDIProvider(BaseInteractionProvider):
    """
    Evaluates drug pairs against a curated, validated clinical interaction database.
    """

    def __init__(self, data_path: Optional[str] = None):
        if not data_path:
            if settings and hasattr(settings, 'BASE_DIR'):
                base_dir = settings.BASE_DIR
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_path = os.path.join(base_dir, 'data', 'curated_ddi_database.json')
        self.data_path = data_path
        self._index: Dict[Tuple[str, str], dict] = {}
        self._load_database()

    def _pair_key(self, drug_a: str, drug_b: str) -> Tuple[str, str]:
        a = drug_a.lower().strip()
        b = drug_b.lower().strip()
        return (min(a, b), max(a, b))

    def _load_database(self):
        if not os.path.exists(self.data_path):
            logger.warning(f"Curated DDI database file not found at {self.data_path}. Running with empty index.")
            return

        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                records = json.load(f)

            for rec in records:
                da = rec.get("drug_a", "")
                db = rec.get("drug_b", "")
                if da and db:
                    key = self._pair_key(da, db)
                    self._index[key] = rec
            logger.info(f"Loaded {len(self._index)} curated clinical drug-drug interaction pairs.")
        except Exception as e:
            logger.error(f"Failed to load curated DDI database: {e}")

    def check_pair(self, drug_a: str, drug_b: str) -> Optional[InteractionAlert]:
        key = self._pair_key(drug_a, drug_b)
        rec = self._index.get(key)
        if rec:
            severity = rec.get("severity", "Moderate")
            # Map "High" to "Severe" if present
            if severity.lower() == "high":
                severity = "Severe"

            return InteractionAlert(
                drug_a=drug_a,
                drug_b=drug_b,
                severity=severity,
                description=rec.get("clinical_management", "") or rec.get("mechanism", "Clinical interaction detected."),
                mechanism=rec.get("mechanism"),
                clinical_management=rec.get("clinical_management"),
                source=rec.get("source", "Curated Clinical DDI DB")
            )
        return None

    def check_interactions(self, meds: List[NormalizedDrug]) -> List[InteractionAlert]:
        alerts: List[InteractionAlert] = []
        n = len(meds)
        if n < 2:
            return alerts

        # Check all unique pairs
        for i in range(n):
            for j in range(i + 1, n):
                drug_a = meds[i].generic_name or meds[i].input_name
                drug_b = meds[j].generic_name or meds[j].input_name

                alert = self.check_pair(drug_a, drug_b)
                if alert:
                    alerts.append(alert)

        return alerts
