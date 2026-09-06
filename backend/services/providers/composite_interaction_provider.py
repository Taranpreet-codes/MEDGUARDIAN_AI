"""
services/providers/composite_interaction_provider.py — Multi-Tier Interaction Provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Combines:
- Tier 1: CuratedDDIProvider (structured severity, mechanism, clinical management)
- Tier 2: OpenFDALabelProvider (official FDA package insert drug_interactions excerpts)

Ensures zero dependency on discontinued NLM RxNav DDI APIs.
"""
import logging
from typing import List
from .base import BaseInteractionProvider
from .models import NormalizedDrug, InteractionAlert
from .curated_ddi_provider import CuratedDDIProvider
from .openfda_provider import OpenFDALabelProvider

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {
    "Contraindicated": 4,
    "Severe": 3,
    "Moderate": 2,
    "Minor": 1,
    "Safe": 0,
    "Unknown": 0
}


class CompositeInteractionProvider(BaseInteractionProvider):
    """
    Tiered Composite Provider evaluating drug-drug interactions across
    curated clinical datasets and live openFDA package insert labeling.
    """

    def __init__(self, curated_provider: CuratedDDIProvider = None, openfda_provider: OpenFDALabelProvider = None):
        self.curated_provider = curated_provider or CuratedDDIProvider()
        self.openfda_provider = openfda_provider or OpenFDALabelProvider()

    def check_interactions(self, meds: List[NormalizedDrug]) -> List[InteractionAlert]:
        alerts: List[InteractionAlert] = []
        n = len(meds)
        if n < 2:
            return alerts

        seen_pairs = set()

        for i in range(n):
            for j in range(i + 1, n):
                drug_a = (meds[i].generic_name or meds[i].input_name).lower()
                drug_b = (meds[j].generic_name or meds[j].input_name).lower()

                pair_key = (min(drug_a, drug_b), max(drug_a, drug_b))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Tier 1: Curated DDI database
                curated_alert = self.curated_provider.check_pair(drug_a, drug_b)

                # Tier 2: openFDA package insert cross-reference
                fda_excerpt = self.openfda_provider.search_label_interaction(drug_a, drug_b)
                if not fda_excerpt:
                    fda_excerpt = self.openfda_provider.search_label_interaction(drug_b, drug_a)

                if curated_alert:
                    if fda_excerpt:
                        curated_alert.fda_label_excerpt = fda_excerpt
                        curated_alert.source += " + openFDA SPL"
                    alerts.append(curated_alert)
                elif fda_excerpt:
                    # Found in official FDA label but not yet in curated database
                    alerts.append(InteractionAlert(
                        drug_a=drug_a,
                        drug_b=drug_b,
                        severity="Moderate",
                        description=f"FDA Label Warning: {fda_excerpt}",
                        mechanism="Documented in official FDA package insert drug interactions section.",
                        clinical_management="Review clinical status and consider dosage adjustment or increased monitoring.",
                        source="openFDA Drug Label (SPL)",
                        fda_label_excerpt=fda_excerpt
                    ))

        # Sort by severity descending
        alerts.sort(key=lambda a: SEVERITY_ORDER.get(a.severity, 0), reverse=True)
        return alerts
