"""
services/providers/openfda_provider.py — Official openFDA Drug Label Provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Queries the official openFDA Drug Label API for FDA Structured Product
Labeling (SPL) sections:
- boxed_warning
- contraindications
- drug_interactions
- warnings_and_precautions
- dosage_and_administration

Official Rate Limits:
- Without key: 240 requests/minute, 1,000 requests/day per IP
- With free key: 240 requests/minute, 120,000 requests/day per key
"""
import os
import logging
import requests
from typing import Optional, Dict
from .base import BaseClinicalLabelProvider
from .models import DrugLabelInfo

logger = logging.getLogger(__name__)


class OpenFDALabelProvider(BaseClinicalLabelProvider):
    """
    Retrieves official FDA-approved package insert data from openFDA.
    """

    def __init__(self, timeout: float = 2.5):
        self.timeout = timeout
        self.api_key = os.environ.get("OPENFDA_API_KEY", "").strip()
        self._cache: Dict[str, Optional[DrugLabelInfo]] = {}
        self._interaction_cache: Dict[str, Optional[str]] = {}

    def _build_url(self, query: str, limit: int = 1) -> str:
        base = f"https://api.fda.gov/drug/label.json?search={query}&limit={limit}"
        if self.api_key and "placeholder" not in self.api_key.lower():
            base += f"&api_key={self.api_key}"
        return base

    def get_label_info(self, generic_name: str) -> Optional[DrugLabelInfo]:
        clean_name = generic_name.strip().lower()
        if not clean_name:
            return None

        if clean_name in self._cache:
            return self._cache[clean_name]

        query = f"(openfda.generic_name:\"{clean_name}\"+OR+openfda.brand_name:\"{clean_name}\")"
        url = self._build_url(query, limit=1)

        try:
            res = requests.get(url, timeout=self.timeout)
            if res.status_code == 404:
                self._cache[clean_name] = None
                return None
            if res.status_code == 429:
                logger.warning("openFDA rate limit reached (HTTP 429). Falling back to local clinical knowledge.")
                return None
            if res.status_code >= 400:
                logger.warning(f"openFDA returned HTTP {res.status_code} for '{clean_name}'")
                return None

            data = res.json()
            results = data.get("results", [])
            if not results:
                self._cache[clean_name] = None
                return None

            item = results[0]

            def extract_text(field_name: str) -> Optional[str]:
                val = item.get(field_name, [])
                if isinstance(val, list) and val:
                    return " ".join(str(x) for x in val)
                elif isinstance(val, str) and val:
                    return val
                return None

            label_info = DrugLabelInfo(
                drug_name=clean_name,
                generic_name=clean_name,
                source="openFDA Drug Label (SPL)",
                boxed_warning=extract_text("boxed_warning"),
                contraindications=extract_text("contraindications"),
                warnings=extract_text("warnings_and_precautions") or extract_text("warnings"),
                drug_interactions=extract_text("drug_interactions"),
                dosage_and_administration=extract_text("dosage_and_administration")
            )
            self._cache[clean_name] = label_info
            return label_info

        except Exception as e:
            logger.debug(f"openFDA label query error for '{clean_name}': {e}")
            return None

    def search_label_interaction(self, drug_a: str, drug_b: str) -> Optional[str]:
        """
        Cross-references whether Drug B is explicitly cited in the official
        openFDA drug_interactions section of Drug A.
        """
        cache_key = f"{drug_a.lower()}__{drug_b.lower()}"
        if cache_key in self._interaction_cache:
            return self._interaction_cache[cache_key]

        # 1. First inspect cached label info if already fetched
        label = self.get_label_info(drug_a)
        if label and label.drug_interactions:
            if drug_b.lower() in label.drug_interactions.lower():
                # Extract relevant sentence or excerpt
                interactions_text = label.drug_interactions
                excerpt = self._extract_relevant_excerpt(interactions_text, drug_b)
                self._interaction_cache[cache_key] = excerpt
                return excerpt

        # 2. Targeted openFDA query
        query = f"openfda.generic_name:\"{drug_a.lower()}\"+AND+drug_interactions:\"{drug_b.lower()}\""
        url = self._build_url(query, limit=1)

        try:
            res = requests.get(url, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                results = data.get("results", [])
                if results:
                    interactions = results[0].get("drug_interactions", [])
                    raw_text = " ".join(interactions) if isinstance(interactions, list) else str(interactions)
                    excerpt = self._extract_relevant_excerpt(raw_text, drug_b)
                    self._interaction_cache[cache_key] = excerpt
                    return excerpt
        except Exception as e:
            logger.debug(f"openFDA interaction search skipped/failed for {drug_a}+{drug_b}: {e}")

        self._interaction_cache[cache_key] = None
        return None

    def _extract_relevant_excerpt(self, full_text: str, search_term: str, max_chars: int = 350) -> str:
        """Extracts the sentence or surrounding context containing the interacting drug term."""
        idx = full_text.lower().find(search_term.lower())
        if idx == -1:
            return full_text[:max_chars] + "..." if len(full_text) > max_chars else full_text
        start = max(0, idx - 100)
        end = min(len(full_text), idx + max_chars)
        excerpt = full_text[start:end].strip()
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(full_text):
            excerpt = excerpt + "..."
        return excerpt
