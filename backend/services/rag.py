import os
import requests
import logging
import chromadb
from django.conf import settings
from google import genai

logger = logging.getLogger(__name__)

def get_gemini_embedding(text: str) -> list[float]:
    """Generates embedding vector for input text using Gemini's gemini-embedding-001."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key or "your_gemini_api_key" in api_key.lower() or "placeholder" in api_key.lower():
        return [0.0] * 768
    try:
        from google.genai import types
        client = genai.Client(api_key=api_key)
        response = client.models.embed_content(
            model='gemini-embedding-001',
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        # Ensure we extract values correctly
        return response.embeddings[0].values
    except Exception as e:
        logger.error(f"Failed to generate Gemini embedding: {e}")
        return [0.0] * 768


class RAGEngine:
    """
    RAG Search Engine for semantically retrieving evidence from local ChromaDB
    and querying real-time warnings from openFDA API.
    """
    def __init__(self):
        chroma_path = getattr(settings, 'CHROMA_DB_PATH', os.path.join(settings.BASE_DIR, 'chroma_db'))
        try:
            self.chroma_client = chromadb.PersistentClient(path=chroma_path)
            self.collection = self.chroma_client.get_or_create_collection(
                name="clinical_evidence"
            )
        except Exception as e:
            logger.warning(f"ChromaDB initialization failed: {e}. Running in fallback mode.")
            self.chroma_client = None
            self.collection = None

    def retrieve_evidence(self, query: str, limit: int = 5) -> list[dict]:
        """
        Retrieves matching evidence documents from ChromaDB.
        """
        if not self.collection:
            return []
        query_vector = get_gemini_embedding(query)
        
        # If dummy vector returned, perform basic keyword query fallback if Chroma allows
        if all(v == 0.0 for v in query_vector):
            logger.warning("Dummy vector returned. Performing local keyword search fallback.")
            try:
                all_docs = self.collection.get()
                documents = all_docs.get('documents', [])
                metadatas = all_docs.get('metadatas', [])
                ids = all_docs.get('ids', [])
                
                query_words = [w.lower() for w in query.split() if len(w) > 2]
                matched_items = []
                
                for idx, doc in enumerate(documents):
                    doc_lower = doc.lower()
                    score = sum(1 for w in query_words if w in doc_lower)
                    if score > 0:
                        matched_items.append((score, idx, doc))
                
                matched_items.sort(key=lambda x: x[0], reverse=True)
                
                evidence_items = []
                for score, idx, doc in matched_items[:limit]:
                    meta = metadatas[idx] if idx < len(metadatas) else {}
                    evidence_items.append({
                        "id": ids[idx] if idx < len(ids) else f"doc_{idx}",
                        "text": doc,
                        "source": meta.get("source", "Unknown"),
                        "metadata": meta
                    })
                return evidence_items
            except Exception as e:
                logger.error(f"Local keyword search fallback failed: {e}")
                return []

        try:
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=limit
            )

            evidence_items = []
            if results and 'documents' in results and results['documents']:
                documents = results['documents'][0]
                metadatas = results['metadatas'][0] if 'metadatas' in results else []
                ids = results['ids'][0] if 'ids' in results else []
                
                for idx, doc in enumerate(documents):
                    meta = metadatas[idx] if idx < len(metadatas) else {}
                    evidence_items.append({
                        "id": ids[idx] if idx < len(ids) else f"doc_{idx}",
                        "text": doc,
                        "source": meta.get("source", "Unknown"),
                        "metadata": meta
                    })
            return evidence_items
        except Exception as e:
            logger.error(f"ChromaDB retrieval failed: {e}")
            return []

    def fetch_fda_label(self, drug_name: str) -> dict:
        """
        Queries the openFDA API for label warnings and contraindications of a specific drug.
        Returns a dict containing warnings, contraindications, and precautions.
        """
        # Format API request URL searching brand name or generic name
        url = f"https://api.fda.gov/drug/label.json?search=(openfda.brand_name:\"{drug_name}\"+OR+openfda.generic_name:\"{drug_name}\")&limit=1"
        
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 404:
                logger.info(f"No openFDA label warnings found for {drug_name}")
                return {}
            if response.status_code >= 400:
                logger.warning(
                    f"openFDA API returned HTTP {response.status_code} for drug '{drug_name}'. "
                    f"Treating as empty result."
                )
                return {}
            data = response.json()
            
            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                
                # Extract key clinical caution sections
                warnings_and_precautions = result.get("warnings_and_precautions", [])
                contraindications = result.get("contraindications", [])
                adverse_reactions = result.get("adverse_reactions", [])
                dosage_and_administration = result.get("dosage_and_administration", [])

                return {
                    "source": "openFDA API",
                    "drug_name": drug_name,
                    "warnings": " ".join(warnings_and_precautions) if isinstance(warnings_and_precautions, list) else str(warnings_and_precautions),
                    "contraindications": " ".join(contraindications) if isinstance(contraindications, list) else str(contraindications),
                    "adverse_reactions": " ".join(adverse_reactions) if isinstance(adverse_reactions, list) else str(adverse_reactions),
                    "dosage_adjustments": " ".join(dosage_and_administration) if isinstance(dosage_and_administration, list) else str(dosage_and_administration),
                }
            
            return {}
        except Exception as e:
            logger.error(f"Failed to query openFDA label for {drug_name}: {e}")
            return {}
