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

Caching Strategy (two-level):
- L1: per-instance dict — eliminates repeat calls within a single HTTP request
- L2: django.core.cache — persistent across requests for the process lifetime
      (LocMemCache in no-Redis dev mode; RedisCache when Redis is available)
      TTL: 24 hours for both label lookups and interaction pair checks.
      Network errors and rate-limit responses are NOT cached so the next
      request will retry them.
"""
import os
import logging
import requests
from typing import Optional, Dict
from .base import BaseClinicalLabelProvider
from .models import DrugLabelInfo

logger = logging.getLogger(__name__)

# Module-level sentinel — cheaper than a special string comparison
_MISSING = object()


class OpenFDALabelProvider(BaseClinicalLabelProvider):
    """
    Retrieves official FDA-approved package insert data from openFDA.
    """

    _FDA_LABEL_TTL    = 86400   # 24 hours — labels rarely change
    _FDA_INTERACT_TTL = 86400   # 24 hours
    _MISS_SENTINEL    = "__NONE__"   # stored in L2 to represent a confirmed miss

    def __init__(self, timeout: float = 2.5):
        self.timeout = timeout
        self.api_key = os.environ.get("OPENFDA_API_KEY", "").strip()
        # L1: request-scoped dicts — survive only for the lifetime of this instance.
        # Kept so repeated calls within a single safety evaluation never hit L2/network.
        self._cache: Dict[str, Optional[DrugLabelInfo]] = {}
        self._interaction_cache: Dict[str, Optional[str]] = {}

    # ── L2 cache helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _django_cache():
        """Lazy import so the module can be imported outside Django (tests)."""
        try:
            from django.core.cache import cache as _c
            return _c
        except Exception:
            return None

    def _l2_label_get(self, key: str):
        """Return DrugLabelInfo | None from L2, or _MISSING sentinel if absent."""
        c = self._django_cache()
        if c is None:
            return _MISSING
        raw = c.get(f"mg:fda_label:{key}")
        if raw is None:
            return _MISSING
        return None if raw == self._MISS_SENTINEL else raw

    def _l2_label_set(self, key: str, value: Optional[DrugLabelInfo]) -> None:
        c = self._django_cache()
        if c is not None:
            c.set(
                f"mg:fda_label:{key}",
                value if value is not None else self._MISS_SENTINEL,
                timeout=self._FDA_LABEL_TTL,
            )

    def _l2_interact_get(self, key: str):
        c = self._django_cache()
        if c is None:
            return _MISSING
        raw = c.get(f"mg:fda_ix:{key}")
        if raw is None:
            return _MISSING
        return None if raw == self._MISS_SENTINEL else raw

    def _l2_interact_set(self, key: str, value: Optional[str]) -> None:
        c = self._django_cache()
        if c is not None:
            c.set(
                f"mg:fda_ix:{key}",
                value if value is not None else self._MISS_SENTINEL,
                timeout=self._FDA_INTERACT_TTL,
            )

    # ── URL builder ──────────────────────────────────────────────────────────

    def _build_url(self, query: str, limit: int = 1) -> str:
        base = f"https://api.fda.gov/drug/label.json?search={query}&limit={limit}"
        if self.api_key and "placeholder" not in self.api_key.lower():
            base += f"&api_key={self.api_key}"
        return base

    # ── public API ───────────────────────────────────────────────────────────

    def get_label_info(self, generic_name: str) -> Optional[DrugLabelInfo]:
        clean_name = generic_name.strip().lower()
        if not clean_name:
            return None

        # L1 hit
        if clean_name in self._cache:
            return self._cache[clean_name]

        # L2 hit
        l2 = self._l2_label_get(clean_name)
        if l2 is not _MISSING:
            self._cache[clean_name] = l2   # promote to L1
            return l2

        # Network fetch
        query = f"(openfda.generic_name:\"{clean_name}\"+OR+openfda.brand_name:\"{clean_name}\")"
        url = self._build_url(query, limit=1)

        result: Optional[DrugLabelInfo] = None
        try:
            res = requests.get(url, timeout=self.timeout)
            if res.status_code == 404:
                pass   # confirmed miss — cache it below
            elif res.status_code == 429:
                logger.warning("openFDA rate limit reached (HTTP 429). Falling back to local clinical knowledge.")
                return None   # do NOT cache rate-limit errors
            elif res.status_code >= 400:
                logger.warning(f"openFDA returned HTTP {res.status_code} for '{clean_name}'")
            else:
                data = res.json()
                results = data.get("results", [])
                if results:
                    item = results[0]

                    def extract_text(field_name: str) -> Optional[str]:
                        val = item.get(field_name, [])
                        if isinstance(val, list) and val:
                            return " ".join(str(x) for x in val)
                        elif isinstance(val, str) and val:
                            return val
                        return None

                    result = DrugLabelInfo(
                        drug_name=clean_name,
                        generic_name=clean_name,
                        source="openFDA Drug Label (SPL)",
                        boxed_warning=extract_text("boxed_warning"),
                        contraindications=extract_text("contraindications"),
                        warnings=extract_text("warnings_and_precautions") or extract_text("warnings"),
                        drug_interactions=extract_text("drug_interactions"),
                        dosage_and_administration=extract_text("dosage_and_administration"),
                    )

        except Exception as e:
            logger.debug(f"openFDA label query error for '{clean_name}': {e}")
            return None   # do NOT cache transient network errors

        # Populate both L1 and L2 (result may be None = confirmed miss)
        self._cache[clean_name] = result
        self._l2_label_set(clean_name, result)
        return result

    def search_label_interaction(self, drug_a: str, drug_b: str) -> Optional[str]:
        """
        Cross-references whether Drug B is explicitly cited in the official
        openFDA drug_interactions section of Drug A.
        """
        cache_key = f"{drug_a.lower()}__{drug_b.lower()}"

        # L1 hit
        if cache_key in self._interaction_cache:
            return self._interaction_cache[cache_key]

        # L2 hit
        l2 = self._l2_interact_get(cache_key)
        if l2 is not _MISSING:
            self._interaction_cache[cache_key] = l2
            return l2

        result: Optional[str] = None

        # 1. First inspect cached label info if already fetched
        label = self.get_label_info(drug_a)
        if label and label.drug_interactions:
            if drug_b.lower() in label.drug_interactions.lower():
                interactions_text = label.drug_interactions
                excerpt = self._extract_relevant_excerpt(interactions_text, drug_b)
                result = excerpt

        if result is None:
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
                        result = self._extract_relevant_excerpt(raw_text, drug_b)
            except Exception as e:
                logger.debug(f"openFDA interaction search skipped/failed for {drug_a}+{drug_b}: {e}")
                return None   # do NOT cache transient network errors

        # Populate both L1 and L2
        self._interaction_cache[cache_key] = result
        self._l2_interact_set(cache_key, result)
        return result

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
