from __future__ import annotations

import html
import re
import unicodedata
from typing import List

try:
    from pyvi import ViTokenizer
except Exception:
    ViTokenizer = None

WORD_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)
PARA_SPLIT_RE = re.compile(r"\n\s*\n+")
SPACE_RE = re.compile(r"\s+")


def normalize_for_search(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u00a0", " ")
    text = SPACE_RE.sub(" ", text).strip()
    return text


def tokenize_for_bm25(text: str, segmenter: str = "none") -> List[str]:
    text = normalize_for_search(text).lower()
    if segmenter == "pyvi" and ViTokenizer is not None:
        text = ViTokenizer.tokenize(text)
    return [tok for tok in WORD_RE.findall(text) if tok]


def chunk_words(words: List[str], chunk_size: int, chunk_overlap: int) -> List[str]:
    if not words:
        return []
    step = max(1, chunk_size - chunk_overlap)
    chunks = []
    for start in range(0, len(words), step):
        piece = words[start : start + chunk_size]
        if not piece:
            continue
        chunks.append(" ".join(piece).strip())
        if start + chunk_size >= len(words):
            break
    return chunks


def chunk_text(text: str, chunk_size: int = 180, chunk_overlap: int = 40) -> List[str]:
    text = normalize_for_search(text)
    if not text:
        return []
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    paragraphs = [p.strip() for p in PARA_SPLIT_RE.split(text) if p.strip()]

    def flush_current() -> None:
        nonlocal current, current_len
        if current:
            merged = "\n\n".join(current).strip()
            if merged:
                chunks.append(merged)
        current = []
        current_len = 0

    for para in paragraphs or [text]:
        words = para.split()
        if len(words) > chunk_size:
            flush_current()
            chunks.extend(chunk_words(words, chunk_size, chunk_overlap))
            continue
        if current_len + len(words) > chunk_size and current:
            flush_current()
        current.append(para)
        current_len += len(words)
    flush_current()
    return chunks or [text]


def truncate_text(text: str, max_chars: int = 240) -> str:
    text = normalize_for_search(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def escape_html(text: str) -> str:
    return html.escape(text or "")


def simple_markdown_to_html(text: str) -> str:
    text = escape_html(text)
    text = re.sub(r"```(.*?)```", lambda m: f"<pre><code>{m.group(1)}</code></pre>", text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    lines = text.splitlines()
    html_lines = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{stripped[2:]}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if stripped:
                html_lines.append(f"<p>{stripped}</p>")
    if in_list:
        html_lines.append("</ul>")
    return "\n".join(html_lines) if html_lines else "<p></p>"
