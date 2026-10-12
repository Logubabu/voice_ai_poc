import time
from typing import Dict, Any


class KBMetricsCollector:
    """In-memory collector for Knowledge Base & RAG operational metrics."""

    def __init__(self):
        self.counters = {
            "knowledge_search_total": 0,
            "knowledge_search_success": 0,
            "knowledge_search_no_results": 0,
            "knowledge_search_errors": 0,
            "document_ingestion_total": 0,
            "document_ingestion_failed": 0,
        }
        self.latency_records = []

    def record_search(self, success: bool, found: bool, latency_ms: float, confidence: float):
        self.counters["knowledge_search_total"] += 1
        if success:
            self.counters["knowledge_search_success"] += 1
            if not found:
                self.counters["knowledge_search_no_results"] += 1
        else:
            self.counters["knowledge_search_errors"] += 1

        self.latency_records.append({
            "latency_ms": latency_ms,
            "confidence": confidence,
            "timestamp": time.time(),
        })

        # Keep rolling window of last 1000 records
        if len(self.latency_records) > 1000:
            self.latency_records.pop(0)

    def record_ingestion(self, success: bool):
        self.counters["document_ingestion_total"] += 1
        if not success:
            self.counters["document_ingestion_failed"] += 1

    def get_summary(self) -> Dict[str, Any]:
        latencies = [r["latency_ms"] for r in self.latency_records]
        confidences = [r["confidence"] for r in self.latency_records]

        p50 = 0.0
        p95 = 0.0
        p99 = 0.0
        avg_confidence = 0.0

        if latencies:
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            p50 = sorted_lat[int(n * 0.50)]
            p95 = sorted_lat[int(n * 0.95)] if n >= 20 else sorted_lat[-1]
            p99 = sorted_lat[int(n * 0.99)] if n >= 100 else sorted_lat[-1]
            avg_confidence = round(sum(confidences) / len(confidences), 4)

        return {
            "counters": self.counters,
            "latency_ms": {
                "p50": round(p50, 2),
                "p95": round(p95, 2),
                "p99": round(p99, 2),
            },
            "rag_confidence_avg": avg_confidence,
            "rag_hit_rate": round(
                (self.counters["knowledge_search_success"] - self.counters["knowledge_search_no_results"])
                / max(1, self.counters["knowledge_search_total"]),
                4,
            ),
        }


kb_metrics = KBMetricsCollector()
