import os
import json
import time
import math
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from services.rag import RAGEngine

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Evaluate the accuracy and latency of the RAG evidence retrieval engine against clinical query benchmarks."

    def add_arguments(self, parser):
        parser.add_argument('--k', type=int, default=5, help="Number of retrieved documents to evaluate (K)")
        parser.add_argument('--dataset', type=str, default='rag_benchmark.json', help="Benchmark filename in data/")

    def handle(self, *args, **options):
        k = options['k']
        dataset_name = options['dataset']

        data_dir = os.path.join(settings.BASE_DIR, 'data')
        benchmark_path = os.path.join(data_dir, dataset_name)

        if not os.path.exists(benchmark_path):
            self.stdout.write(self.style.ERROR(
                f"RAG evaluation dataset not found at {benchmark_path}.\n"
                "Please run 'python generate_benchmarks.py' inside backend/data/ first."
            ))
            return

        with open(benchmark_path, 'r', encoding='utf-8') as f:
            rag_cases = json.load(f)

        self.stdout.write(f"Loaded {len(rag_cases)} RAG evaluation queries. Running retrieval evaluation at K={k}...")

        rag_engine = RAGEngine()
        
        # Keep track of metrics
        hits = 0
        precisions = []
        recalls = []
        reciprocal_ranks = []
        ndcgs = []
        retrieval_times = []

        detailed_results = []

        for case in rag_cases:
            query = case["query"]
            expected_sources = [s.lower() for s in case["expected_sources"]]

            start_time = time.perf_counter()
            retrieved = rag_engine.retrieve_evidence(query, limit=k)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            retrieval_times.append(duration_ms)

            # Analyze retrieved sources
            retrieved_sources = [r["source"].lower() for r in retrieved]
            
            # Hit count
            hit_detected = False
            relevant_retrieved_count = 0
            first_rank = None

            dcg = 0.0
            for rank_idx, r_src in enumerate(retrieved_sources):
                rank = rank_idx + 1
                if r_src in expected_sources:
                    hit_detected = True
                    relevant_retrieved_count += 1
                    dcg += 1.0 / math.log2(rank + 1)
                    if first_rank is None:
                        first_rank = rank

            # Hit Rate
            if hit_detected:
                hits += 1

            # Precision@K and Recall@K
            p_k = relevant_retrieved_count / len(retrieved_sources) if retrieved_sources else 0.0
            r_k = relevant_retrieved_count / len(expected_sources) if expected_sources else 0.0
            precisions.append(p_k)
            recalls.append(r_k)

            # MRR (Mean Reciprocal Rank)
            mrr_score = 1.0 / first_rank if first_rank is not None else 0.0
            reciprocal_ranks.append(mrr_score)

            # IDCG and nDCG
            idcg = sum(1.0 / math.log2(i + 2) for i in range(min(k, len(expected_sources))))
            ndcg_score = dcg / idcg if idcg > 0.0 else 0.0
            ndcgs.append(ndcg_score)

            detailed_results.append({
                "query": query,
                "expected_sources": expected_sources,
                "retrieved_sources": retrieved_sources,
                "hit": hit_detected,
                "precision": p_k,
                "recall": r_k,
                "mrr": mrr_score,
                "ndcg": ndcg_score,
                "latency_ms": duration_ms
            })

        # Calculate averages
        avg_hit_rate = (hits / len(rag_cases)) * 100.0
        avg_precision = sum(precisions) / len(precisions) * 100.0
        avg_recall = sum(recalls) / len(recalls) * 100.0
        avg_mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
        avg_ndcg = sum(ndcgs) / len(ndcgs)
        avg_time = sum(retrieval_times) / len(retrieval_times)

        # Output to console
        self.stdout.write("=" * 60)
        self.stdout.write("      MedGuardian AI — RAG Retrieval Evaluation")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total Queries Evaluated    : {len(rag_cases)}")
        self.stdout.write(f"Top-{k} Retrieval Accuracy : {avg_hit_rate:.2f}%")
        self.stdout.write(f"Precision@{k}               : {avg_precision:.2f}%")
        self.stdout.write(f"Recall@{k}                  : {avg_recall:.2f}%")
        self.stdout.write(f"Mean Reciprocal Rank (MRR) : {avg_mrr:.4f}")
        self.stdout.write(f"nDCG@{k}                    : {avg_ndcg:.4f}")
        self.stdout.write(f"Average Retrieval Time     : {avg_time:.2f} ms")
        self.stdout.write("=" * 60)

        # Save reports
        reports_dir = os.path.join(settings.BASE_DIR, 'reports')
        os.makedirs(reports_dir, exist_ok=True)

        json_out = {
            "evaluation_date": datetime.now().isoformat(),
            "k": k,
            "metrics": {
                "top_k_accuracy": avg_hit_rate,
                "precision_at_k": avg_precision,
                "recall_at_k": avg_recall,
                "mrr": avg_mrr,
                "ndcg": avg_ndcg,
                "avg_retrieval_time_ms": avg_time
            },
            "queries": detailed_results
        }

        with open(os.path.join(reports_dir, "rag_metrics.json"), 'w', encoding='utf-8') as f:
            json.dump(json_out, f, indent=2)

        self.stdout.write(self.style.SUCCESS(f"Saved RAG evaluation metrics to reports/rag_metrics.json"))
