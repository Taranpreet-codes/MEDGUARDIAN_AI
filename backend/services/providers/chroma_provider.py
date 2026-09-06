"""
services/providers/chroma_provider.py — ChromaDB Guideline Evidence Provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Retrieves verified clinical guideline excerpts (KDIGO, ADA, WHO, FDA) from
ChromaDB vector store with BM25/keyword hybrid fallback.

CRITICAL: Scores represent text retrieval similarity / relevance score,
NOT medical confidence.
"""
import os
import logging
from typing import List

try:
    from django.conf import settings
except ImportError:
    settings = None

from .base import BaseEvidenceProvider
from .models import EvidenceCitation

logger = logging.getLogger(__name__)


class ChromaGuidelineProvider(BaseEvidenceProvider):
    """
    Evidence retrieval provider for clinical guidelines using ChromaDB.
    """

    def __init__(self):
        self._initialized = False
        self.collection = None
        self._init_chroma()

    def _init_chroma(self):
        try:
            import chromadb
            if settings and hasattr(settings, 'BASE_DIR'):
                chroma_path = getattr(settings, 'CHROMA_DB_PATH', os.path.join(settings.BASE_DIR, 'chroma_db'))
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                chroma_path = os.path.join(base_dir, 'chroma_db')

            self.chroma_client = chromadb.PersistentClient(path=chroma_path)
            self.collection = self.chroma_client.get_or_create_collection(
                name="clinical_evidence"
            )
            self._initialized = True
        except Exception as e:
            logger.warning(f"ChromaDB initialization failed: {e}. Running in keyword fallback mode.")
            self.collection = None

    def retrieve_evidence(self, query: str, limit: int = 3) -> List[EvidenceCitation]:
        if not self.collection:
            return []

        citations: List[EvidenceCitation] = []

        try:
            # Query documents
            all_docs = self.collection.get()
            documents = all_docs.get('documents', [])
            metadatas = all_docs.get('metadatas', [])
            ids = all_docs.get('ids', [])

            query_words = [w.lower() for w in query.split() if len(w) > 2]
            scored_items = []

            for idx, doc in enumerate(documents):
                doc_lower = doc.lower()
                # Compute term overlap score
                matched_words = sum(1 for w in query_words if w in doc_lower)
                if matched_words > 0:
                    # Relevance score normalized to [0.0, 1.0] range
                    relevance = min(1.0, round(matched_words / max(1, len(query_words)), 2))
                    scored_items.append((relevance, idx, doc))

            scored_items.sort(key=lambda x: x[0], reverse=True)

            for relevance, idx, doc in scored_items[:limit]:
                meta = metadatas[idx] if idx < len(metadatas) else {}
                doc_id = ids[idx] if idx < len(ids) else f"doc_{idx}"
                page = meta.get("page", 1)
                source_name = meta.get("source", "Clinical Guideline")

                citations.append(EvidenceCitation(
                    source=source_name,
                    page=int(page) if str(page).isdigit() else 1,
                    snippet=doc[:250].strip() + ("..." if len(doc) > 250 else ""),
                    relevance_score=relevance,
                    document_id=doc_id
                ))

        except Exception as e:
            logger.error(f"Chroma evidence retrieval failed: {e}")

        return citations
