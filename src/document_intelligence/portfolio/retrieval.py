"""Local block-level semantic retrieval with an injectable embedder."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from document_intelligence.ingestion.models import ParsedDocument
from document_intelligence.portfolio.models import (
    RetrievalEvaluationReport,
    RetrievalHit,
    RetrievalQuestion,
    RetrievalQuestionDiagnostic,
    RetrievalRecord,
)


DEVELOPMENT_SOURCE_IDS = frozenset({"S001", "S002", "S003", "S004", "S006"})
RRF_K = 60


class Embedder(Protocol):
    """Minimal embedding interface used by retrieval and offline tests."""

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return one dense vector per input string."""


class SentenceTransformerEmbedder:
    """Lazy adapter for the small all-MiniLM-L6-v2 embedding model."""

    def __init__(
        self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Encode text locally without calling a hosted model."""
        return np.asarray(
            self._model.encode(
                list(texts), convert_to_numpy=True, show_progress_bar=False
            ),
            dtype=np.float64,
        )


def build_retrieval_records(document: ParsedDocument) -> list[RetrievalRecord]:
    """Create one retrieval record for each nonblank ParsedDocument block."""
    if document.source_id is None or not document.source_id.strip():
        raise ValueError("ParsedDocument source_id is required for retrieval")
    return [
        RetrievalRecord(
            evidence_id=f"{document.source_id}:{block.block_id}",
            source_id=document.source_id,
            block_id=block.block_id,
            location_type=block.location.location_type.value,
            location_value=block.location.location_value,
            text=block.text,
        )
        for block in document.blocks
        if block.text.strip()
    ]


def _source_paths(root: Path, source_ids: set[str] | None) -> list[Path]:
    if source_ids is None:
        return sorted(root.rglob("*.json"))
    paths: list[Path] = []
    for source_id in sorted(source_ids):
        matches = sorted(root.rglob(f"{source_id}.json"))
        if len(matches) != 1:
            raise ValueError(
                f"expected exactly one ParsedDocument for {source_id}; found {len(matches)}"
            )
        paths.append(matches[0])
    return paths


def load_retrieval_records(
    parsed_root: Path | str, *, source_ids: Iterable[str] | None = None
) -> list[RetrievalRecord]:
    """Load selected ParsedDocuments without opening excluded source files."""
    root = Path(parsed_root)
    selected = set(source_ids) if source_ids is not None else None
    records: list[RetrievalRecord] = []
    for path in _source_paths(root, selected):
        document = ParsedDocument.model_validate_json(path.read_text(encoding="utf-8"))
        if selected is not None and document.source_id not in selected:
            raise ValueError(f"ParsedDocument source mismatch in {path.name}")
        records.extend(build_retrieval_records(document))
    evidence_ids = [record.evidence_id for record in records]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("retrieval evidence IDs must be unique")
    if not records:
        raise ValueError("no usable ParsedDocument blocks were found")
    return records


def _normalized(values: np.ndarray) -> np.ndarray:
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] == 0:
        raise ValueError("embedder must return a non-empty two-dimensional matrix")
    if not np.isfinite(values).all():
        raise ValueError("embedder returned non-finite values")
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("embedder returned a zero-length vector")
    return values / norms


class SemanticIndex:
    """In-memory normalized embedding matrix and its source records."""

    def __init__(self, records: Sequence[RetrievalRecord], embedder: Embedder) -> None:
        if not records:
            raise ValueError("at least one retrieval record is required")
        self._records = list(records)
        self._embedder = embedder
        vectors = np.asarray(
            embedder.encode([record.text for record in self._records]),
            dtype=np.float64,
        )
        if vectors.shape[0] != len(self._records):
            raise ValueError("embedder result count does not match retrieval records")
        self._vectors = _normalized(vectors)

    def search(self, query: str, *, top_k: int = 5) -> list[RetrievalHit]:
        """Return a deterministic cosine-similarity ranking."""
        if not query.strip():
            raise ValueError("query must not be blank")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        query_vector = np.asarray(self._embedder.encode([query]), dtype=np.float64)
        normalized_query = _normalized(query_vector)
        if normalized_query.shape[1] != self._vectors.shape[1]:
            raise ValueError("query and record embeddings have different dimensions")
        scores = self._vectors @ normalized_query[0]
        ranked = sorted(
            zip(self._records, scores, strict=True),
            key=lambda item: (-float(item[1]), item[0].source_id, item[0].block_id),
        )
        return [
            RetrievalHit(**record.model_dump(), score=float(score))
            for record, score in ranked[:top_k]
        ]


class LexicalIndex:
    """In-memory TF-IDF index over the exact retrieval block texts."""

    def __init__(self, records: Sequence[RetrievalRecord]) -> None:
        if not records:
            raise ValueError("at least one retrieval record is required")
        self._records = list(records)
        self._vectorizer = TfidfVectorizer()
        self._matrix = self._vectorizer.fit_transform(
            [record.text for record in self._records]
        )

    def search(self, query: str, *, top_k: int = 5) -> list[RetrievalHit]:
        """Return a deterministic TF-IDF cosine-similarity ranking."""
        if not query.strip():
            raise ValueError("query must not be blank")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        query_vector = self._vectorizer.transform([query])
        scores = (self._matrix @ query_vector.T).toarray().ravel()
        ranked = sorted(
            zip(self._records, scores, strict=True),
            key=lambda item: (-float(item[1]), item[0].source_id, item[0].block_id),
        )
        return [
            RetrievalHit(**record.model_dump(), score=float(score))
            for record, score in ranked[:top_k]
        ]


class HybridIndex:
    """Fuse dense and TF-IDF rankings with fixed-k Reciprocal Rank Fusion."""

    def __init__(
        self,
        records: Sequence[RetrievalRecord],
        embedder: Embedder,
        *,
        rrf_k: int = RRF_K,
    ) -> None:
        if rrf_k != RRF_K:
            raise ValueError(f"rrf_k is fixed at {RRF_K}")
        self._records = list(records)
        evidence_ids = [record.evidence_id for record in self._records]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("hybrid index evidence IDs must be unique")
        self._semantic = SemanticIndex(self._records, embedder)
        self._lexical = LexicalIndex(self._records)
        self._rrf_k = rrf_k

    def search(self, query: str, *, top_k: int = 5) -> list[RetrievalHit]:
        """Return deterministic dense-plus-lexical RRF results."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        result_count = len(self._records)
        dense_hits = self._semantic.search(query, top_k=result_count)
        lexical_hits = self._lexical.search(query, top_k=result_count)
        dense_ranks = {
            hit.evidence_id: rank for rank, hit in enumerate(dense_hits, start=1)
        }
        lexical_ranks = {
            hit.evidence_id: rank for rank, hit in enumerate(lexical_hits, start=1)
        }
        fused = [
            (
                record,
                1.0 / (self._rrf_k + dense_ranks[record.evidence_id])
                + 1.0 / (self._rrf_k + lexical_ranks[record.evidence_id]),
            )
            for record in self._records
        ]
        ranked = sorted(
            fused,
            key=lambda item: (-item[1], item[0].source_id, item[0].block_id),
        )
        return [
            RetrievalHit(**record.model_dump(), score=score)
            for record, score in ranked[:top_k]
        ]


def retrieve_blocks(
    records: Sequence[RetrievalRecord],
    query: str,
    *,
    embedder: Embedder,
    top_k: int = 5,
) -> list[RetrievalHit]:
    """Convenience wrapper for the default hybrid search."""
    return HybridIndex(records, embedder).search(query, top_k=top_k)


def load_retrieval_questions(path: Path | str) -> list[RetrievalQuestion]:
    """Load and validate a labelled retrieval benchmark."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    questions = [RetrievalQuestion.model_validate(item) for item in payload]
    identifiers = [question.id for question in questions]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("retrieval question IDs must be unique")
    return questions


def evaluate_retrieval(
    records: Sequence[RetrievalRecord],
    questions: Sequence[RetrievalQuestion],
    *,
    embedder: Embedder,
    include_diagnostics: bool = False,
) -> RetrievalEvaluationReport:
    """Calculate Hit@1/3/5 and MRR without any LLM call."""
    if not questions:
        raise ValueError("at least one retrieval question is required")
    disallowed = sorted(
        {
            question.expected_source_id
            for question in questions
            if question.expected_source_id not in DEVELOPMENT_SOURCE_IDS
        }
    )
    if disallowed:
        raise ValueError(f"benchmark contains non-development sources: {disallowed}")
    index = HybridIndex(records, embedder)
    hit_counts = {1: 0, 3: 0, 5: 0}
    reciprocal_ranks: list[float] = []
    diagnostics: list[RetrievalQuestionDiagnostic] = []
    for question in questions:
        hits = index.search(question.question, top_k=len(records))
        expected = [
            f"{question.expected_source_id}:{block_id}"
            for block_id in question.expected_block_ids
        ]
        expected_set = set(expected)
        ranks = [
            rank
            for rank, hit in enumerate(hits, start=1)
            if hit.evidence_id in expected_set
        ]
        first_rank = min(ranks) if ranks else None
        for cutoff in hit_counts:
            if first_rank is not None and first_rank <= cutoff:
                hit_counts[cutoff] += 1
        reciprocal_ranks.append(0.0 if first_rank is None else 1.0 / first_rank)
        if include_diagnostics:
            diagnostics.append(
                RetrievalQuestionDiagnostic(
                    question_id=question.id,
                    expected_evidence_ids=expected,
                    first_relevant_rank=first_rank,
                    top_5_evidence_ids=[hit.evidence_id for hit in hits[:5]],
                )
            )
    count = len(questions)
    return RetrievalEvaluationReport(
        question_count=count,
        hit_at_1=hit_counts[1] / count,
        hit_at_3=hit_counts[3] / count,
        hit_at_5=hit_counts[5] / count,
        mean_reciprocal_rank=sum(reciprocal_ranks) / count,
        question_diagnostics=diagnostics if include_diagnostics else None,
    )
