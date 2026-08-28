import os
from django.test import TestCase
from unittest.mock import patch, MagicMock
from services.rag import RAGEngine, get_gemini_embedding
from evidence.models import EvidenceSource


class RAGServiceTest(TestCase):
    
    @patch('requests.get')
    def test_openfda_api_client_success(self, mock_get):
        # Mock successful openFDA API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{
                "warnings_and_precautions": ["Lisinopril warning info."],
                "contraindications": ["Do not take if pregnant."],
                "adverse_reactions": ["Coughing."],
                "dosage_and_administration": ["Adjust for renal impairment."]
            }]
        }
        mock_get.return_value = mock_response

        engine = RAGEngine()
        result = engine.fetch_fda_label("Lisinopril")

        self.assertEqual(result["source"], "openFDA API")
        self.assertEqual(result["drug_name"], "Lisinopril")
        self.assertIn("Lisinopril warning info", result["warnings"])
        self.assertIn("Do not take if pregnant", result["contraindications"])

    @patch('requests.get')
    def test_openfda_api_client_not_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        engine = RAGEngine()
        result = engine.fetch_fda_label("UnknownDrugXYZ")
        self.assertEqual(result, {})

    @patch('services.rag.get_gemini_embedding')
    def test_chroma_retrieval_flow(self, mock_embed):
        # Mock embedding return
        mock_embed.return_value = [0.1] * 768

        engine = RAGEngine()
        
        # Manually inject a dummy doc into ChromaDB for testing
        engine.collection.add(
            ids=["doc_test_1"],
            embeddings=[[0.1] * 768],
            documents=["Lisinopril warnings: Monitor eGFR and creatinine levels closely. Reduce dose if kidney function drops."],
            metadatas=[{"source": "test_guide.txt", "page": 1}]
        )

        results = engine.retrieve_evidence("Lisinopril kidney guidelines", limit=1)
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "doc_test_1")
        self.assertIn("Monitor eGFR", results[0]["text"])
        self.assertEqual(results[0]["source"], "test_guide.txt")
        self.assertEqual(results[0]["metadata"]["page"], 1)

        # Cleanup
        try:
            engine.collection.delete(ids=["doc_test_1"])
        except Exception:
            pass


class GeminiSecurityConfigTest(TestCase):
    """
    Security regression tests for BUG-04:
    Ensures Gemini API key is exclusively sourced from the environment,
    never hardcoded in service implementations, and missing keys fail gracefully.
    """

    def test_services_read_api_key_from_environment(self):
        """Verify services load the API key from os.environ dynamically."""
        mock_env_key = "test-mock-env-api-key-12345"
        with patch.dict(os.environ, {"GEMINI_API_KEY": mock_env_key}):
            with patch('services.risk_engine.RAGEngine'):
                from services.risk_engine import RiskEngine
                from services.ingestion import IngestionPipeline
                
                with patch('google.genai.Client') as mock_client:
                    risk_eng = RiskEngine()
                    self.assertEqual(risk_eng.api_key, mock_env_key)

                    ingest = IngestionPipeline()
                    self.assertEqual(ingest.api_key, mock_env_key)

    def test_services_gracefully_handle_missing_api_key_without_hardcoded_secrets(self):
        """Verify services gracefully handle missing/empty API keys without hardcoded fallback credentials."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with patch('services.risk_engine.RAGEngine'):
                from services.risk_engine import RiskEngine
                from services.ingestion import IngestionPipeline
                from services.rag import get_gemini_embedding

                risk_eng = RiskEngine()
                self.assertFalse(bool(risk_eng.api_key))
                self.assertIsNone(risk_eng.client)

                ingest = IngestionPipeline()
                self.assertFalse(bool(ingest.api_key))
                self.assertIsNone(ingest.client)

                # Embedding should return zero vector fallback rather than throwing an exception
                embedding = get_gemini_embedding("test query")
                self.assertEqual(len(embedding), 768)
                self.assertTrue(all(v == 0.0 for v in embedding))


