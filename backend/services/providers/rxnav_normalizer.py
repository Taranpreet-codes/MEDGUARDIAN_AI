"""
services/providers/rxnav_normalizer.py — Active NLM RxNav Drug Normalizer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Uses official, active NLM RxNorm / RxNav APIs:
- /REST/approximateTerm.json
- /REST/rxcui.json

NOTE: The NLM RxNav Drug-Drug Interaction API was discontinued on Jan 2, 2024.
This provider is strictly scoped to Drug Name Normalization and RxCUI mapping.
"""
import logging
import requests
from typing import Optional, Dict
from .base import BaseNormalizationProvider
from .models import NormalizedDrug

logger = logging.getLogger(__name__)

# Preloaded canonical mapping for common clinical drugs and brand names
# Ensures instant, offline-capable resolution during unit tests and network outages
BUILTIN_NORMALIZATION_MAP: Dict[str, Dict[str, str]] = {
    "glucophage": {"generic": "metformin", "rxcui": "6809"},
    "metformin": {"generic": "metformin", "rxcui": "6809"},
    "prinivil": {"generic": "lisinopril", "rxcui": "29046"},
    "zestril": {"generic": "lisinopril", "rxcui": "29046"},
    "lisinopril": {"generic": "lisinopril", "rxcui": "29046"},
    "aldactone": {"generic": "spironolactone", "rxcui": "9997"},
    "spironolactone": {"generic": "spironolactone", "rxcui": "9997"},
    "advil": {"generic": "ibuprofen", "rxcui": "5640"},
    "motrin": {"generic": "ibuprofen", "rxcui": "5640"},
    "ibuprofen": {"generic": "ibuprofen", "rxcui": "5640"},
    "coumadin": {"generic": "warfarin", "rxcui": "11289"},
    "warfarin": {"generic": "warfarin", "rxcui": "11289"},
    "aspirin": {"generic": "aspirin", "rxcui": "1191"},
    "bayer": {"generic": "aspirin", "rxcui": "1191"},
    "amoxil": {"generic": "amoxicillin", "rxcui": "723"},
    "amoxicillin": {"generic": "amoxicillin", "rxcui": "723"},
    "penicillin": {"generic": "penicillin", "rxcui": "7980"},
    "zocor": {"generic": "simvastatin", "rxcui": "36567"},
    "simvastatin": {"generic": "simvastatin", "rxcui": "36567"},
    "cordarone": {"generic": "amiodarone", "rxcui": "703"},
    "amiodarone": {"generic": "amiodarone", "rxcui": "703"},
    "prozac": {"generic": "fluoxetine", "rxcui": "4493"},
    "fluoxetine": {"generic": "fluoxetine", "rxcui": "4493"},
    "plavix": {"generic": "clopidogrel", "rxcui": "32968"},
    "clopidogrel": {"generic": "clopidogrel", "rxcui": "32968"},
    "prilosec": {"generic": "omeprazole", "rxcui": "7646"},
    "omeprazole": {"generic": "omeprazole", "rxcui": "7646"},
    "lanoxin": {"generic": "digoxin", "rxcui": "3407"},
    "digoxin": {"generic": "digoxin", "rxcui": "3407"},
    "lipitor": {"generic": "atorvastatin", "rxcui": "83367"},
    "atorvastatin": {"generic": "atorvastatin", "rxcui": "83367"},
    "klor-con": {"generic": "potassium chloride", "rxcui": "8591"},
    "potassium chloride": {"generic": "potassium chloride", "rxcui": "8591"},
}


class RxNavNormalizerProvider(BaseNormalizationProvider):
    """
    Normalizes medication names using active NLM RxNorm APIs
    with local memory caching and resilient offline fallback.
    """

    def __init__(self, timeout: float = 1.5):
        self.timeout = timeout
        self._cache: Dict[str, NormalizedDrug] = {}

    def normalize(self, drug_name: str) -> NormalizedDrug:
        clean_name = drug_name.strip()
        lower_name = clean_name.lower()

        if not lower_name:
            return NormalizedDrug(input_name=clean_name, generic_name="", rxcui=None)

        # 1. Check in-memory cache
        if lower_name in self._cache:
            return self._cache[lower_name]

        # 2. Check local canonical dictionary for instant zero-latency match
        if lower_name in BUILTIN_NORMALIZATION_MAP:
            entry = BUILTIN_NORMALIZATION_MAP[lower_name]
            result = NormalizedDrug(
                input_name=clean_name,
                generic_name=entry["generic"],
                rxcui=entry["rxcui"],
                confidence_source="builtin_rxnorm"
            )
            self._cache[lower_name] = result
            return result

        # 3. Query active NLM RxNav approximateTerm API
        live_result = self._query_rxnav(clean_name)
        if live_result:
            self._cache[lower_name] = live_result
            return live_result

        # 4. Fallback: return sanitized name without RxCUI
        fallback = NormalizedDrug(
            input_name=clean_name,
            generic_name=lower_name,
            rxcui=None,
            confidence_source="raw_fallback"
        )
        self._cache[lower_name] = fallback
        return fallback

    def _query_rxnav(self, drug_name: str) -> Optional[NormalizedDrug]:
        """Queries active NLM RxNav endpoints for RxCUI and canonical generic name."""
        try:
            # Step A: Query approximateTerm endpoint
            url = f"https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term={requests.utils.quote(drug_name)}&maxEntries=1"
            res = requests.get(url, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                candidate_list = data.get("approximateGroup", {}).get("candidate", [])
                if candidate_list:
                    best = candidate_list[0]
                    rxcui = best.get("rxcui")
                    # Step B: Get canonical name for this RxCUI
                    if rxcui:
                        canonical_name = self._get_rxcui_name(rxcui) or drug_name.lower()
                        return NormalizedDrug(
                            input_name=drug_name,
                            generic_name=canonical_name.lower(),
                            rxcui=rxcui,
                            confidence_source="rxnav_live"
                        )

            # Fallback query to rxcui.json
            rxcui_url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={requests.utils.quote(drug_name)}"
            res_cui = requests.get(rxcui_url, timeout=self.timeout)
            if res_cui.status_code == 200:
                data = res_cui.json()
                rxnorm_ids = data.get("idGroup", {}).get("rxnormId", [])
                if rxnorm_ids:
                    rxcui = rxnorm_ids[0]
                    canonical_name = self._get_rxcui_name(rxcui) or drug_name.lower()
                    return NormalizedDrug(
                        input_name=drug_name,
                        generic_name=canonical_name.lower(),
                        rxcui=rxcui,
                        confidence_source="rxnav_live"
                    )

        except Exception as e:
            logger.debug(f"RxNav normalization network query skipped/failed for '{drug_name}': {e}")

        return None

    def _get_rxcui_name(self, rxcui: str) -> Optional[str]:
        """Fetches canonical name for an RxCUI."""
        try:
            url = f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/properties.json"
            res = requests.get(url, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                return data.get("properties", {}).get("name")
        except Exception:
            pass
        return None
