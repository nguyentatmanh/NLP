from __future__ import annotations

import hashlib
import json
import pickle
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
try:
    from rank_bm25 import BM25Okapi
except Exception:
    BM25Okapi = None

from text_utils import chunk_text, normalize_for_search, tokenize_for_bm25, truncate_text


@dataclass
class DocumentChunk:
    chunk_id: str
    source: str
    title: str
    text: str


@dataclass
class RetrievalResult:
    chunk_id: str
    source: str
    title: str
    text: str
    score: float
    retrieval_method: str
    sparse_score: float = 0.0
    dense_score: float = 0.0




class SimpleBM25:
    def __init__(self, corpus_tokens: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.corpus_tokens = [list(doc) for doc in corpus_tokens]
        self.k1 = k1
        self.b = b
        self.doc_lens = [len(doc) for doc in self.corpus_tokens]
        self.avgdl = sum(self.doc_lens) / max(1, len(self.doc_lens))
        self.term_freqs = []
        self.doc_freqs = defaultdict(int)
        for doc in self.corpus_tokens:
            tf = defaultdict(int)
            seen = set()
            for token in doc:
                tf[token] += 1
                if token not in seen:
                    self.doc_freqs[token] += 1
                    seen.add(token)
            self.term_freqs.append(tf)
        self.N = len(self.corpus_tokens)

    def _idf(self, term: str) -> float:
        n_qi = self.doc_freqs.get(term, 0)
        return float(np.log((self.N - n_qi + 0.5) / (n_qi + 0.5) + 1.0))

    def get_scores(self, query_tokens: Sequence[str]) -> np.ndarray:
        scores = np.zeros(self.N, dtype=np.float32)
        for idx, tf in enumerate(self.term_freqs):
            dl = self.doc_lens[idx]
            score = 0.0
            for term in query_tokens:
                freq = tf.get(term, 0)
                if freq == 0:
                    continue
                idf = self._idf(term)
                denom = freq + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1e-9))
                score += idf * (freq * (self.k1 + 1)) / denom
            scores[idx] = score
        return scores


class BM25Retriever:
    def __init__(self, chunks: Sequence[DocumentChunk], segmenter: str = "none") -> None:
        self.chunks = list(chunks)
        self.segmenter = segmenter
        self.corpus_tokens = [tokenize_for_bm25(chunk.text, segmenter=segmenter) for chunk in self.chunks]
        self.index = BM25Okapi(self.corpus_tokens) if BM25Okapi is not None else SimpleBM25(self.corpus_tokens)

    def search(self, question: str, top_k: int = 8) -> List[RetrievalResult]:
        query_tokens = tokenize_for_bm25(question, segmenter=self.segmenter)
        if not query_tokens:
            return []
        scores = self.index.get_scores(query_tokens)
        ranked = np.argsort(scores)[::-1][:top_k]
        results: List[RetrievalResult] = []
        for idx in ranked:
            score = float(scores[idx])
            if score <= 0:
                continue
            chunk = self.chunks[int(idx)]
            results.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    source=chunk.source,
                    title=chunk.title,
                    text=chunk.text,
                    score=score,
                    retrieval_method="bm25",
                    sparse_score=score,
                )
            )
        return results


class DenseRetriever:
    def __init__(self, chunks: Sequence[DocumentChunk], model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            raise RuntimeError(
                "SentenceTransformers chua duoc cai dat. Hay pip install -r requirements.txt."
            ) from exc

        self.chunks = list(chunks)
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        corpus = [chunk.text for chunk in self.chunks]
        embeddings = self.model.encode(corpus, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True)
        self.embeddings = embeddings.astype(np.float32)

    def search(self, question: str, top_k: int = 8) -> List[RetrievalResult]:
        question_embedding = self.model.encode([question], convert_to_numpy=True, normalize_embeddings=True)[0]
        scores = np.dot(self.embeddings, question_embedding).astype(np.float32)
        ranked = np.argsort(scores)[::-1][:top_k]
        results: List[RetrievalResult] = []
        for idx in ranked:
            score = float(scores[idx])
            chunk = self.chunks[int(idx)]
            results.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    source=chunk.source,
                    title=chunk.title,
                    text=chunk.text,
                    score=score,
                    retrieval_method="dense",
                    dense_score=score,
                )
            )
        return results


class HybridRetriever:
    def __init__(self, chunks: Sequence[DocumentChunk], segmenter: str, dense_model_name: str) -> None:
        self.chunks = list(chunks)
        self.by_id = {chunk.chunk_id: chunk for chunk in self.chunks}
        self.bm25 = BM25Retriever(self.chunks, segmenter=segmenter)
        self.dense = DenseRetriever(self.chunks, model_name=dense_model_name)

    @staticmethod
    def _rrf(rank: int, k: int = 60) -> float:
        return 1.0 / (k + rank)

    def search(self, question: str, top_k: int = 8) -> List[RetrievalResult]:
        sparse = self.bm25.search(question, top_k=top_k * 3)
        dense = self.dense.search(question, top_k=top_k * 3)
        sparse_rank = {item.chunk_id: idx + 1 for idx, item in enumerate(sparse)}
        dense_rank = {item.chunk_id: idx + 1 for idx, item in enumerate(dense)}
        sparse_scores = {item.chunk_id: item.score for item in sparse}
        dense_scores = {item.chunk_id: item.score for item in dense}

        fused_scores: Dict[str, float] = defaultdict(float)
        for chunk_id, rank in sparse_rank.items():
            fused_scores[chunk_id] += self._rrf(rank)
        for chunk_id, rank in dense_rank.items():
            fused_scores[chunk_id] += self._rrf(rank)

        ranked_ids = sorted(fused_scores, key=fused_scores.get, reverse=True)[:top_k]
        results: List[RetrievalResult] = []
        for chunk_id in ranked_ids:
            chunk = self.by_id[chunk_id]
            results.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    source=chunk.source,
                    title=chunk.title,
                    text=chunk.text,
                    score=float(fused_scores[chunk_id]),
                    retrieval_method="hybrid",
                    sparse_score=float(sparse_scores.get(chunk_id, 0.0)),
                    dense_score=float(dense_scores.get(chunk_id, 0.0)),
                )
            )
        return results


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        texts = []
        for page in reader.pages:
            texts.append(page.extract_text() or "")
        return "\n".join(texts)
    except Exception:
        return ""


def _read_docx(path: Path) -> str:
    try:
        from docx import Document
    except Exception:
        return ""
    doc = Document(str(path))
    texts = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(texts)


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    return ""


def discover_documents(docs_dir: str | Path) -> List[Path]:
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        return []
    return sorted([p for p in docs_path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS])


def build_chunks(docs_dir: str | Path, chunk_size: int = 180, chunk_overlap: int = 40) -> List[DocumentChunk]:
    chunks: List[DocumentChunk] = []
    for path in discover_documents(docs_dir):
        raw_text = read_document(path)
        text = normalize_for_search(raw_text)
        if not text:
            continue
        title = path.stem.replace("_", " ").replace("-", " ").strip()
        for idx, chunk_text_value in enumerate(chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap), start=1):
            chunk_id = f"{path.stem}-{idx:04d}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    source=str(path.relative_to(Path(docs_dir))),
                    title=title,
                    text=chunk_text_value,
                )
            )
    return chunks


class RetrieverEngine:
    def __init__(
        self,
        docs_dir: str | Path,
        retriever_type: str = "bm25",
        dense_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        chunk_size: int = 180,
        chunk_overlap: int = 40,
        segmenter: str = "none",
        cache_dir: str | Path | None = None,
    ) -> None:
        self.docs_dir = Path(docs_dir)
        self.retriever_type = retriever_type
        self.dense_model_name = dense_model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.segmenter = segmenter
        self.cache_dir = Path(cache_dir) if cache_dir else self.docs_dir / ".cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.chunks = self._load_or_build_chunks()
        if retriever_type == "bm25":
            self.engine = BM25Retriever(self.chunks, segmenter=segmenter)
        elif retriever_type == "dense":
            self.engine = DenseRetriever(self.chunks, model_name=dense_model_name)
        elif retriever_type == "hybrid":
            self.engine = HybridRetriever(self.chunks, segmenter=segmenter, dense_model_name=dense_model_name)
        else:
            raise ValueError(f"Retriever khong ho tro: {retriever_type}")

    def _docs_signature(self) -> str:
        h = hashlib.sha256()
        for path in discover_documents(self.docs_dir):
            stat = path.stat()
            h.update(str(path.relative_to(self.docs_dir)).encode("utf-8"))
            h.update(str(stat.st_mtime_ns).encode("utf-8"))
            h.update(str(stat.st_size).encode("utf-8"))
        h.update(str(self.chunk_size).encode("utf-8"))
        h.update(str(self.chunk_overlap).encode("utf-8"))
        return h.hexdigest()

    def _load_or_build_chunks(self) -> List[DocumentChunk]:
        signature = self._docs_signature()
        cache_file = self.cache_dir / f"chunks_{signature}.pkl"
        if cache_file.exists():
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        chunks = build_chunks(self.docs_dir, chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
        with open(cache_file, "wb") as f:
            pickle.dump(chunks, f)
        return chunks

    def search(self, question: str, top_k: int = 6) -> List[RetrievalResult]:
        return self.engine.search(question, top_k=top_k)

    def summary(self) -> Dict[str, object]:
        return {
            "documents": len(discover_documents(self.docs_dir)),
            "chunks": len(self.chunks),
            "retriever": self.retriever_type,
            "dense_model_name": self.dense_model_name,
            "segmenter": self.segmenter,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }
