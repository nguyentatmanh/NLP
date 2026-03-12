from __future__ import annotations

from typing import Dict

from datasets import Dataset, DatasetDict, load_dataset

DEFAULT_DATASET = "taidng/UIT-ViQuAD2.0"


def load_uit_viquad2(dataset_name: str = DEFAULT_DATASET, data_dir: str | None = None) -> DatasetDict:
    if data_dir:
        dataset = load_dataset(data_dir)
    else:
        dataset = load_dataset(dataset_name)

    def _normalize(example: Dict) -> Dict:
        answers = example.get("answers") or {"text": [], "answer_start": []}
        plausible = example.get("plausible_answers") or {"text": [], "answer_start": []}
        answer_texts = list(answers.get("text") or [])
        answer_starts = list(answers.get("answer_start") or [])
        has_answer = bool(answer_texts)
        answer_text = answer_texts[0] if has_answer else ""
        answer_start = int(answer_starts[0]) if has_answer else -1
        answer_end = answer_start + len(answer_text) if has_answer else -1
        return {
            "id": example.get("id") or example.get("uit_id") or "",
            "uit_id": example.get("uit_id") or "",
            "title": example.get("title") or "",
            "context": example.get("context") or "",
            "question": (example.get("question") or "").strip(),
            "answer_text": answer_text,
            "answer_start": answer_start,
            "answer_end": answer_end,
            "answers_texts": answer_texts,
            "answers_starts": answer_starts,
            "is_impossible": bool(example.get("is_impossible", not has_answer)),
            "plausible_texts": list(plausible.get("text") or []),
            "plausible_starts": list(plausible.get("answer_start") or []),
        }

    return dataset.map(_normalize)


def maybe_limit_dataset(dataset: Dataset, limit: int | None) -> Dataset:
    if limit is None or limit >= len(dataset):
        return dataset
    return dataset.select(range(limit))
