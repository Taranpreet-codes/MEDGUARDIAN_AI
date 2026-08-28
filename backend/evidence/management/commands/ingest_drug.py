import os
import json
import hashlib
import requests
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from evidence.models import EvidenceSource
from services.rag import get_gemini_embedding
import chromadb

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Ingest official drug safety warnings from openFDA and RxNav, compile drug guidelines, and index in ChromaDB RAG store."

    def add_arguments(self, parser):
        parser.add_argument('drug_name', type=str, help="Name of the drug to ingest (e.g. ibuprofen, fluoxetine)")

    def handle(self, *args, **options):
        drug_name = options['drug_name'].lower().strip()
        self.stdout.write(f"Initiating knowledge ingestion for drug: {drug_name.capitalize()}...")

        # 1. Fetch from openFDA
        fda_data = self.fetch_openfda_label(drug_name)
        if not fda_data:
            self.stdout.write(self.style.ERROR(f"Could not retrieve official FDA label data for '{drug_name}'. Ingestion aborted."))
            return

        # 2. Compile document data
        text_content, md_content, json_data = self.compile_documents(drug_name, fda_data)

        # 3. Write structured files to data/
        data_dir = os.path.join(settings.BASE_DIR, 'data')
        os.makedirs(data_dir, exist_ok=True)

        txt_path = os.path.join(data_dir, f"drug_{drug_name}.txt")
        md_path = os.path.join(data_dir, f"drug_{drug_name}.md")
        json_path = os.path.join(data_dir, f"drug_{drug_name}.json")

        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2)

        self.stdout.write(self.style.SUCCESS(f"Saved drug dossier files:\n - {txt_path}\n - {md_path}\n - {json_path}"))

        # 4. Generate hash/checksum of text
        checksum = hashlib.sha256(text_content.encode('utf-8')).hexdigest()

        # 5. Connect to ChromaDB
        chroma_path = getattr(settings, 'CHROMA_DB_PATH', os.path.join(settings.BASE_DIR, 'chroma_db'))
        chroma_client = chromadb.PersistentClient(path=chroma_path)
        collection = chroma_client.get_or_create_collection("clinical_evidence")

        # 6. Avoid duplicate vectors: delete old entries from ChromaDB for this drug source
        # ChromaDB matches by metadata field "source"
        source_filename = f"drug_{drug_name}.txt"
        try:
            # Query existing to check if we already have chunks
            existing = collection.get(where={"source": source_filename})
            if existing and existing.get('ids'):
                self.stdout.write(f"Removing {len(existing['ids'])} existing chunks in ChromaDB for {source_filename} to prevent duplicate vectors...")
                collection.delete(ids=existing['ids'])
        except Exception as e:
            logger.error(f"Error checking/deleting old Chroma entries: {e}")

        # 7. Split into chunks and generate embeddings
        chunks = self.chunk_text(text_content, source_filename, chunk_size=800, overlap=150)
        self.stdout.write(f"Generated {len(chunks)} chunks for {source_filename}. Embedding and indexing...")

        indexed_count = 0
        for chunk in chunks:
            text = chunk["text"]
            metadata = chunk["metadata"]

            # Add extra metadata requirements
            metadata.update({
                "drug_name": drug_name,
                "publication_date": json_data["publication_date"],
                "version": json_data["version"],
                "url": json_data["url"],
                "embedding_model": "gemini-embedding-001",
                "hash": checksum
            })

            # Fetch embedding
            vector = get_gemini_embedding(text)
            if all(v == 0.0 for v in vector):
                self.stdout.write(self.style.WARNING(f"Gemini API key missing/invalid. Indexing chunk {indexed_count} with fallback zero vector."))

            chunk_id = f"{source_filename}_{indexed_count}"
            collection.add(
                ids=[chunk_id],
                embeddings=[vector],
                documents=[text],
                metadatas=[metadata]
            )
            indexed_count += 1

        # 8. Update database EvidenceSource record
        EvidenceSource.objects.update_or_create(
            filename=source_filename,
            defaults={
                "checksum": checksum,
                "doc_type": "FDA_LABEL"
            }
        )

        self.stdout.write(self.style.SUCCESS(f"Successfully ingested and indexed {indexed_count} chunks for '{drug_name.capitalize()}' in ChromaDB RAG store!"))

    def fetch_openfda_label(self, drug_name: str) -> dict | None:
        """Fetches detailed warning and contraindication sections from openFDA API."""
        url = f"https://api.fda.gov/drug/label.json?search=(openfda.brand_name:\"{drug_name}\"+OR+openfda.generic_name:\"{drug_name}\")&limit=1"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if "results" in data and len(data["results"]) > 0:
                    return data["results"][0]
            else:
                logger.warning(f"openFDA API status: {res.status_code} for {drug_name}")
        except Exception as e:
            logger.error(f"Error querying openFDA API for {drug_name}: {e}")
        return None

    def compile_documents(self, drug_name: str, result: dict) -> tuple[str, str, dict]:
        """Compiles openFDA response lists into structured markdown, plain text, and JSON formats."""
        brand_name = ", ".join(result.get("openfda", {}).get("brand_name", [drug_name.capitalize()]))
        generic_name = ", ".join(result.get("openfda", {}).get("generic_name", [drug_name.capitalize()]))
        pub_date = result.get("effective_time", datetime.now().strftime("%Y%m%d"))
        if len(pub_date) == 8:
            pub_date = f"{pub_date[:4]}-{pub_date[4:6]}-{pub_date[6:]}"
        
        url = f"https://open.fda.gov/apis/drug/label/"
        version = result.get("version", "1.0")

        # Key warnings sections
        warnings_and_precautions = result.get("warnings_and_precautions", ["None documented"])
        contraindications = result.get("contraindications", ["None documented"])
        boxed_warning = result.get("boxed_warning", ["None documented"])
        pregnancy = result.get("pregnancy", ["None documented"])
        nursing = result.get("nursing_mothers", ["None documented"])
        pediatric = result.get("pediatric_use", ["None documented"])
        geriatric = result.get("geriatric_use", ["None documented"])
        drug_interactions = result.get("drug_interactions", ["None documented"])
        dosage_admin = result.get("dosage_and_administration", ["None documented"])
        indications = result.get("indications_and_usage", ["None documented"])

        # Format helper
        def clean_section(sec):
            if isinstance(sec, list):
                return "\n".join(sec)
            return str(sec)

        # JSON Dossier
        json_data = {
            "drug_name": drug_name,
            "brand_names": result.get("openfda", {}).get("brand_name", [drug_name.capitalize()]),
            "generic_name": result.get("openfda", {}).get("generic_name", [drug_name.capitalize()]),
            "publication_date": pub_date,
            "version": version,
            "url": url,
            "indications": clean_section(indications),
            "contraindications": clean_section(contraindications),
            "warnings_precautions": clean_section(warnings_and_precautions),
            "boxed_warning": clean_section(boxed_warning),
            "pregnancy": clean_section(pregnancy),
            "breastfeeding": clean_section(nursing),
            "pediatric_use": clean_section(pediatric),
            "geriatric_use": clean_section(geriatric),
            "drug_interactions": clean_section(drug_interactions),
            "dosage_and_administration": clean_section(dosage_admin),
        }

        # MD Dossier
        md_content = f"""# Official FDA Clinical Dossier: {drug_name.capitalize()}
**Brand Names:** {brand_name}
**Generic Name:** {generic_name}
**FDA Release Date:** {pub_date} | **Dossier Version:** {version}

---

## 1. Boxed Warning (Black Box)
{clean_section(boxed_warning)}

## 2. Indications and Usage
{clean_section(indications)}

## 3. Contraindications
{clean_section(contraindications)}

## 4. Warnings and Precautions
{clean_section(warnings_and_precautions)}

## 5. Use in Specific Populations
### Pregnancy
{clean_section(pregnancy)}

### Breastfeeding / Nursing Mothers
{clean_section(nursing)}

### Pediatric Use
{clean_section(pediatric)}

### Geriatric Use
{clean_section(geriatric)}

## 6. Drug Interactions
{clean_section(drug_interactions)}

## 7. Dosage and Administration
{clean_section(dosage_admin)}
"""

        # Plain Text Dossier
        text_content = f"""Official FDA Clinical Dossier: {drug_name.capitalize()}
Brand Names: {brand_name}
Generic Name: {generic_name}
FDA Release Date: {pub_date}

1. Boxed Warning (Black Box)
{clean_section(boxed_warning)}

2. Indications and Usage
{clean_section(indications)}

3. Contraindications
{clean_section(contraindications)}

4. Warnings and Precautions
{clean_section(warnings_and_precautions)}

5. Use in Specific Populations
Pregnancy: {clean_section(pregnancy)}
Breastfeeding: {clean_section(nursing)}
Pediatric: {clean_section(pediatric)}
Geriatric: {clean_section(geriatric)}

6. Drug Interactions
{clean_section(drug_interactions)}

7. Dosage and Administration
{clean_section(dosage_admin)}
"""

        return text_content, md_content, json_data

    def chunk_text(self, text, filename, chunk_size=800, overlap=150):
        words = text.split()
        chunks = []
        curr_index = 0
        page_num = 1
        
        while curr_index < len(text):
            end_index = min(curr_index + chunk_size, len(text))
            if end_index < len(text):
                while end_index > curr_index and text[end_index] != ' ':
                    end_index -= 1
            
            chunk = text[curr_index:end_index].strip()
            if chunk:
                chunks.append({
                    "text": chunk,
                    "metadata": {
                        "source": filename,
                        "page": page_num
                    }
                })
                # Increment page number every 3 chunks
                if len(chunks) % 3 == 0:
                    page_num += 1
            
            curr_index = end_index - overlap if end_index < len(text) else len(text)
            if curr_index >= end_index:
                curr_index = end_index
                
        return chunks
