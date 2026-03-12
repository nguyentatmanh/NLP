from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from fallback_llm import build_fallback
from qa_reader import ExtractiveReader, MockReader
from retriever import RetrieverEngine
from text_utils import simple_markdown_to_html, truncate_text

APP_ROOT = Path(__file__).resolve().parent
WEB_ROOT = APP_ROOT / "webui"

APP_CONFIG: Dict[str, Any] = {}
READER = None
RETRIEVER = None
FALLBACK = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    mode: str = Field(default="open_domain")
    context: str | None = None
    top_k_retrieve: int = 6
    top_k_reader: int = 4


class ReindexRequest(BaseModel):
    docs_dir: str | None = None


def load_env_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


app = FastAPI(title="Lumina QA")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(WEB_ROOT)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "reader_loaded": READER is not None,
        "retriever_loaded": RETRIEVER is not None,
        "fallback_loaded": FALLBACK is not None,
        "config": APP_CONFIG,
    }


@app.get("/config")
def config() -> Dict[str, Any]:
    return APP_CONFIG


@app.post("/reindex")
def reindex(req: ReindexRequest) -> Dict[str, Any]:
    global RETRIEVER
    docs_dir = req.docs_dir or APP_CONFIG.get("docs_dir")
    if not docs_dir:
        raise HTTPException(status_code=400, detail="Chua co docs_dir")
    RETRIEVER = RetrieverEngine(
        docs_dir=docs_dir,
        retriever_type=APP_CONFIG.get("retriever", "bm25"),
        dense_model_name=APP_CONFIG.get("dense_model_name"),
        chunk_size=APP_CONFIG.get("chunk_size", 180),
        chunk_overlap=APP_CONFIG.get("chunk_overlap", 40),
        segmenter=APP_CONFIG.get("segmenter", "none"),
        cache_dir=APP_ROOT / "cache",
    )
    return {"ok": True, "summary": RETRIEVER.summary()}


@app.post("/chat")
def chat(req: ChatRequest) -> Dict[str, Any]:
    question = req.message.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Cau hoi rong")

    if req.mode == "context":
        response = answer_with_context(question=question, context=req.context or "")
    else:
        response = answer_open_domain(
            question=question,
            top_k_retrieve=max(1, req.top_k_retrieve),
            top_k_reader=max(1, req.top_k_reader),
        )
    response["html"] = simple_markdown_to_html(response["answer"])
    return response


def answer_with_context(question: str, context: str) -> Dict[str, Any]:
    if not context.strip():
        raise HTTPException(status_code=400, detail="Ban chua cung cap ngữ cảnh")
    if READER is None:
        raise HTTPException(status_code=500, detail="Chua nap reader")

    pred = READER.predict(question, context)
    answer = pred.answer if pred.has_answer else "Không tìm thấy thông tin đủ tin cậy trong ngữ cảnh đã nhập."
    used_fallback = False

    if not pred.has_answer and FALLBACK is not None:
        fallback_resp = FALLBACK.generate(question, [context])
        answer = fallback_resp.answer
        used_fallback = True

    return {
        "answer": answer,
        "mode": "context",
        "answer_mode": "fallback" if used_fallback else ("reader" if pred.has_answer else "no_answer"),
        "scores": {
            "reader_score": pred.score,
            "null_score": pred.no_answer_score,
            "score_diff": pred.score_diff,
            "no_answer_probability": pred.no_answer_probability,
        },
        "sources": [
            {
                "title": "Ngữ cảnh hiện tại",
                "source": "manual_context",
                "excerpt": truncate_text(context, 320),
                "retrieval_score": 0.0,
                "reader_score": pred.score,
            }
        ],
    }



def answer_open_domain(question: str, top_k_retrieve: int, top_k_reader: int) -> Dict[str, Any]:
    if RETRIEVER is None:
        raise HTTPException(status_code=500, detail="Chua nap retriever")
    if READER is None:
        raise HTTPException(status_code=500, detail="Chua nap reader")

    retrieved = RETRIEVER.search(question, top_k=top_k_retrieve)
    if not retrieved:
        answer = "Không tìm thấy tài liệu phù hợp trong kho dữ liệu."
        return {
            "answer": answer,
            "mode": "open_domain",
            "answer_mode": "no_answer",
            "scores": {},
            "sources": [],
        }

    reader_ranked = []
    for item in retrieved[:top_k_reader]:
        pred = READER.predict(question, item.text)
        reader_ranked.append((item, pred))

    reader_ranked.sort(
        key=lambda pair: (
            1 if pair[1].has_answer else 0,
            float(pair[1].score - pair[1].no_answer_score),
            float(pair[1].score),
            float(pair[0].score),
        ),
        reverse=True,
    )
    best_item, best_pred = reader_ranked[0]
    used_fallback = False

    if best_pred.has_answer:
        answer = best_pred.answer
        answer_mode = "reader"
    else:
        if FALLBACK is not None:
            fallback_contexts = [item.text for item, _ in reader_ranked[: min(3, len(reader_ranked))]]
            fallback_resp = FALLBACK.generate(question, fallback_contexts)
            answer = fallback_resp.answer
            used_fallback = True
            answer_mode = "fallback"
        else:
            answer = "Không tìm thấy thông tin đủ tin cậy trong kho dữ liệu."
            answer_mode = "no_answer"

    sources = []
    for item, pred in reader_ranked:
        sources.append(
            {
                "title": item.title,
                "source": item.source,
                "excerpt": truncate_text(item.text, 280),
                "retrieval_score": item.score,
                "sparse_score": item.sparse_score,
                "dense_score": item.dense_score,
                "reader_score": pred.score,
                "no_answer_probability": pred.no_answer_probability,
            }
        )

    return {
        "answer": answer,
        "mode": "open_domain",
        "answer_mode": answer_mode,
        "scores": {
            "reader_score": best_pred.score,
            "null_score": best_pred.no_answer_score,
            "score_diff": best_pred.score_diff,
            "no_answer_probability": best_pred.no_answer_probability,
        },
        "sources": sources,
    }



def bootstrap(args: argparse.Namespace) -> None:
    global APP_CONFIG, READER, RETRIEVER, FALLBACK
    load_env_file(APP_ROOT / ".env")

    if args.mock_reader:
        READER = MockReader()
    elif args.reader_model:
        READER = ExtractiveReader(
            model_name_or_path=args.reader_model,
            max_length=args.reader_max_length,
            doc_stride=args.reader_doc_stride,
            max_answer_length=args.max_answer_length,
            null_score_diff_threshold=args.null_score_diff_threshold,
        )
    else:
        READER = None

    if args.docs_dir:
        RETRIEVER = RetrieverEngine(
            docs_dir=args.docs_dir,
            retriever_type=args.retriever,
            dense_model_name=args.dense_model_name,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            segmenter=args.segmenter,
            cache_dir=APP_ROOT / "cache",
        )
    else:
        RETRIEVER = None

    FALLBACK = build_fallback(args.fallback_provider)
    APP_CONFIG = {
        "app_name": args.app_name,
        "app_tagline": args.app_tagline,
        "retriever": args.retriever,
        "dense_model_name": args.dense_model_name,
        "segmenter": args.segmenter,
        "docs_dir": args.docs_dir,
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "reader_model": args.reader_model or ("mock" if args.mock_reader else None),
        "reader_max_length": args.reader_max_length,
        "reader_doc_stride": args.reader_doc_stride,
        "null_score_diff_threshold": args.null_score_diff_threshold,
        "max_answer_length": args.max_answer_length,
        "fallback_provider": args.fallback_provider,
        "retriever_summary": RETRIEVER.summary() if RETRIEVER is not None else None,
    }



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Lumina QA web server")
    parser.add_argument("--app_name", type=str, default="Lumina")
    parser.add_argument("--app_tagline", type=str, default="Kho tri thức nội bộ")
    parser.add_argument("--reader_model", type=str, default=None)
    parser.add_argument("--mock_reader", action="store_true")
    parser.add_argument("--reader_max_length", type=int, default=384)
    parser.add_argument("--reader_doc_stride", type=int, default=96)
    parser.add_argument("--max_answer_length", type=int, default=50)
    parser.add_argument("--null_score_diff_threshold", type=float, default=0.0)
    parser.add_argument("--docs_dir", type=str, default=None)
    parser.add_argument("--retriever", choices=["bm25", "dense", "hybrid"], default="bm25")
    parser.add_argument(
        "--dense_model_name",
        type=str,
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    parser.add_argument("--chunk_size", type=int, default=180)
    parser.add_argument("--chunk_overlap", type=int, default=40)
    parser.add_argument("--segmenter", choices=["none", "pyvi"], default="none")
    parser.add_argument("--fallback_provider", choices=["disabled", "openai_compatible", "ollama"], default="disabled")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    bootstrap(args)
    uvicorn.run(app, host=args.host, port=args.port)
