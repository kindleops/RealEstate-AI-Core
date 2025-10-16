"""Simple local vector store for lead embeddings."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

PERSIST_PATH = Path("data/vector_index.json")


@dataclass
class VectorRecord:
    id: str
    embedding: List[float]
    metadata: Dict[str, object] = field(default_factory=dict)


class VectorStore:
    """A lightweight embedding store with cosine similarity search."""

    def __init__(self, persist_path: Path | None = None) -> None:
        self.persist_path = persist_path or PERSIST_PATH
        self.vectors: Dict[str, VectorRecord] = {}
        self._load()

    def add(self, records: Iterable[Tuple[str, str, Dict[str, object]]]) -> None:
        for record_id, text, metadata in records:
            embedding = self._embed(text)
            self.vectors[record_id] = VectorRecord(id=record_id, embedding=embedding, metadata=metadata)
        self._save()

    def query(self, text: str, top_k: int = 3) -> List[Dict[str, object]]:
        if not self.vectors:
            return []
        query_vector = self._embed(text)
        scored = []
        for record in self.vectors.values():
            score = self._cosine_similarity(query_vector, record.embedding)
            scored.append((score, record))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {"id": record.id, "score": round(score, 4), "metadata": record.metadata}
            for score, record in scored[:top_k]
        ]

    def _save(self) -> None:
        serializable = {
            record_id: {
                "embedding": record.embedding,
                "metadata": record.metadata,
            }
            for record_id, record in self.vectors.items()
        }
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        with self.persist_path.open("w", encoding="utf-8") as fh:
            json.dump(serializable, fh)

    def _load(self) -> None:
        if not self.persist_path.exists():
            return
        with self.persist_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        for record_id, payload in data.items():
            self.vectors[record_id] = VectorRecord(
                id=record_id,
                embedding=list(payload.get("embedding", [])),
                metadata=dict(payload.get("metadata", {})),
            )

    @staticmethod
    def _embed(text: str) -> List[float]:
        # A deterministic hash-based embedding as a placeholder for real models.
        text = text or ""
        values = [0.0] * 12
        for idx, ch in enumerate(text):
            bucket = idx % len(values)
            values[bucket] += (ord(ch) % 31) / 100.0
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [round(v / norm, 6) for v in values]

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b:
            return 0.0
        length = min(len(vec_a), len(vec_b))
        dot = sum(vec_a[i] * vec_b[i] for i in range(length))
        norm_a = math.sqrt(sum(vec_a[i] * vec_a[i] for i in range(length)))
        norm_b = math.sqrt(sum(vec_b[i] * vec_b[i] for i in range(length)))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


__all__ = ["VectorStore", "VectorRecord"]
