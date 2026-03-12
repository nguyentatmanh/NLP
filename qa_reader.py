from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch


@dataclass
class ReaderPrediction:
    answer: str
    score: float
    no_answer_score: float
    score_diff: float
    no_answer_probability: float
    has_answer: bool
    start_char: int
    end_char: int
    context: str


class ExtractiveReader:
    def __init__(
        self,
        model_name_or_path: str,
        max_length: int = 384,
        doc_stride: int = 96,
        max_answer_length: int = 50,
        null_score_diff_threshold: float | None = None,
        device: str | None = None,
    ) -> None:
        self.model_name_or_path = model_name_or_path
        self.max_length = max_length
        self.doc_stride = doc_stride
        self.max_answer_length = max_answer_length
        try:
            from transformers import AutoModelForQuestionAnswering, AutoTokenizer
        except Exception as exc:
            raise RuntimeError("Can cai transformers de nap reader that.") from exc
        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, use_fast=True)
        self.model = AutoModelForQuestionAnswering.from_pretrained(model_name_or_path)
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self.device = torch.device(device)
        self.model.to(self.device)
        self.model.eval()
        saved_threshold = self._load_saved_threshold(model_name_or_path)
        self.null_score_diff_threshold = saved_threshold if null_score_diff_threshold is None else null_score_diff_threshold

    @staticmethod
    def _load_saved_threshold(model_name_or_path: str) -> float:
        config_path = Path(model_name_or_path) / "reader_runtime_config.json"
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                return float(data.get("null_score_diff_threshold", 0.0))
            except Exception:
                return 0.0
        return 0.0

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)
        z = math.exp(value)
        return z / (1.0 + z)

    def predict(self, question: str, context: str) -> ReaderPrediction:
        encoded = self.tokenizer(
            [question],
            [context],
            truncation="only_second",
            max_length=self.max_length,
            stride=self.doc_stride,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding=False,
        )
        offset_mappings = encoded.pop("offset_mapping")
        model_inputs: Dict[str, torch.Tensor] = {key: torch.tensor(value, device=self.device) for key, value in encoded.items()}
        with torch.no_grad():
            outputs = self.model(**model_inputs)
            start_logits = outputs.start_logits.detach().cpu().numpy()
            end_logits = outputs.end_logits.detach().cpu().numpy()
        best_span_text = ""
        best_span_score = -1e30
        best_start = -1
        best_end = -1
        best_null_score = -1e30
        for feature_index in range(len(start_logits)):
            input_ids = encoded["input_ids"][feature_index]
            offsets = offset_mappings[feature_index]
            sequence_ids = encoded.sequence_ids(feature_index)
            cls_index = input_ids.index(self.tokenizer.cls_token_id)
            null_score = float(start_logits[feature_index][cls_index] + end_logits[feature_index][cls_index])
            best_null_score = max(best_null_score, null_score)
            filtered_offsets: List[tuple[int, int] | None] = []
            for idx, offset in enumerate(offsets):
                filtered_offsets.append(offset if sequence_ids[idx] == 1 else None)
            start_indexes = np.argsort(start_logits[feature_index])[-1 : -21 : -1].tolist()
            end_indexes = np.argsort(end_logits[feature_index])[-1 : -21 : -1].tolist()
            for start_index in start_indexes:
                for end_index in end_indexes:
                    if start_index >= len(filtered_offsets) or end_index >= len(filtered_offsets):
                        continue
                    if filtered_offsets[start_index] is None or filtered_offsets[end_index] is None:
                        continue
                    if end_index < start_index:
                        continue
                    if end_index - start_index + 1 > self.max_answer_length:
                        continue
                    start_char = filtered_offsets[start_index][0]
                    end_char = filtered_offsets[end_index][1]
                    span_text = context[start_char:end_char].strip()
                    if not span_text:
                        continue
                    score = float(start_logits[feature_index][start_index] + end_logits[feature_index][end_index])
                    if score > best_span_score:
                        best_span_score = score
                        best_span_text = span_text
                        best_start = start_char
                        best_end = end_char
        score_diff = best_null_score - best_span_score
        no_answer_probability = self._sigmoid(score_diff)
        has_answer = bool(best_span_text) and score_diff <= self.null_score_diff_threshold
        answer = best_span_text if has_answer else ""
        return ReaderPrediction(
            answer=answer,
            score=float(best_span_score),
            no_answer_score=float(best_null_score),
            score_diff=float(score_diff),
            no_answer_probability=float(no_answer_probability),
            has_answer=has_answer,
            start_char=int(best_start),
            end_char=int(best_end),
            context=context,
        )


class MockReader:
    def predict(self, question: str, context: str) -> ReaderPrediction:
        q_terms = {t.lower() for t in question.split() if len(t) > 2}
        best_sentence = ""
        best_overlap = -1
        for sentence in context.replace("\n", " ").split(". "):
            s_terms = {t.lower() for t in sentence.split()}
            overlap = len(q_terms & s_terms)
            if overlap > best_overlap:
                best_overlap = overlap
                best_sentence = sentence.strip()
        has_answer = bool(best_sentence)
        answer = best_sentence[:180].strip()
        return ReaderPrediction(
            answer=answer if has_answer else "",
            score=float(best_overlap),
            no_answer_score=0.0 if has_answer else 1.0,
            score_diff=-1.0 if has_answer else 1.0,
            no_answer_probability=0.2 if has_answer else 0.95,
            has_answer=has_answer,
            start_char=0,
            end_char=min(len(context), len(answer)),
            context=context,
        )
