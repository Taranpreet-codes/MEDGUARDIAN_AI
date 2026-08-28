import os
import hashlib
from django.core.management.base import BaseCommand
from django.conf import settings
from evidence.models import EvidenceSource
from services.rag import get_gemini_embedding
import chromadb
from pypdf import PdfReader

class Command(BaseCommand):
    help = "Ingest clinical guidelines and FDA labels from data/ into ChromaDB"

    def handle(self, *args, **options):
        data_dir = os.path.join(settings.BASE_DIR, 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # Connect to ChromaDB
        chroma_path = getattr(settings, 'CHROMA_DB_PATH', os.path.join(settings.BASE_DIR, 'chroma_db'))
        chroma_client = chromadb.PersistentClient(path=chroma_path)
        collection = chroma_client.get_or_create_collection("clinical_evidence")

        files = os.listdir(data_dir)
        if not files:
            self.stdout.write(self.style.WARNING(f"No documents found in data folder: {data_dir}. Place PDFs or TXT files here."))
            return

        for filename in files:
            file_path = os.path.join(data_dir, filename)
            if not os.path.isfile(file_path):
                continue
            
            # Check checksum
            hasher = hashlib.sha256()
            with open(file_path, 'rb') as f:
                buf = f.read()
                hasher.update(buf)
            checksum = hasher.hexdigest()

            if EvidenceSource.objects.filter(filename=filename, checksum=checksum).exists():
                self.stdout.write(self.style.SUCCESS(f"Skipping already indexed file: {filename}"))
                continue

            self.stdout.write(f"Processing document: {filename}...")

            # Extract text
            chunks = []
            if filename.endswith('.pdf'):
                chunks = self.parse_pdf(file_path, filename)
            elif filename.endswith('.txt') or filename.endswith('.json'):
                chunks = self.parse_text_file(file_path, filename)
            else:
                self.stdout.write(self.style.WARNING(f"Skipping unsupported file format: {filename}"))
                continue

            if not chunks:
                self.stdout.write(self.style.WARNING(f"No text extracted from {filename}"))
                continue

            # Embed and Index
            indexed_count = 0
            for chunk in chunks:
                text = chunk["text"]
                metadata = chunk["metadata"]
                
                # Fetch embedding vector from Gemini API
                vector = get_gemini_embedding(text)
                if all(v == 0.0 for v in vector):
                    self.stdout.write(self.style.WARNING(f"Gemini API key missing/invalid. Indexing chunk in {filename} with fallback zero vector."))
                
                # Save to Chroma
                chunk_id = f"{filename}_{metadata['page']}_{indexed_count}"
                collection.add(
                    ids=[chunk_id],
                    embeddings=[vector],
                    documents=[text],
                    metadatas=[metadata]
                )
                indexed_count += 1

            # Save reference in database
            EvidenceSource.objects.update_or_create(
                filename=filename,
                defaults={
                    "checksum": checksum,
                    "doc_type": "WHO_GUIDELINE" if filename.lower().startswith("who") else "FDA_LABEL"
                }
            )
            self.stdout.write(self.style.SUCCESS(f"Successfully indexed {indexed_count} chunks from {filename} in ChromaDB."))

    def parse_pdf(self, path, filename):
        reader = PdfReader(path)
        chunks = []
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text:
                continue
            
            # Simple chunking: 800 characters with 150 overlap
            page_chunks = self.chunk_text(text, chunk_size=800, overlap=150)
            for chunk_text in page_chunks:
                chunks.append({
                    "text": chunk_text,
                    "metadata": {
                        "source": filename,
                        "page": page_num + 1,
                    }
                })
        return chunks

    def parse_text_file(self, path, filename):
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        page_chunks = self.chunk_text(text, chunk_size=800, overlap=150)
        chunks = []
        for idx, chunk_text in enumerate(page_chunks):
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "source": filename,
                    "page": idx + 1,
                }
            })
        return chunks

    def chunk_text(self, text, chunk_size=800, overlap=150):
        words = text.split()
        chunks = []
        curr_index = 0
        
        # Simple character boundaries but respecting words
        while curr_index < len(text):
            end_index = min(curr_index + chunk_size, len(text))
            
            # Adjust to word boundary if not at end
            if end_index < len(text):
                while end_index > curr_index and text[end_index] != ' ':
                    end_index -= 1
            
            chunk = text[curr_index:end_index].strip()
            if chunk:
                chunks.append(chunk)
            
            curr_index = end_index - overlap if end_index < len(text) else len(text)
            if curr_index >= end_index: # Prevent infinite loop on edge cases
                curr_index = end_index
                
        return chunks
