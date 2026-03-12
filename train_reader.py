from __future__ import annotations

import argparse
import inspect
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import evaluate
import numpy as np
import torch
from datasets import Dataset
from transformers import (
    AutoModelForQuestionAnswering,
    AutoTokenizer,
    DefaultDataCollator,
    Trainer,
    TrainingArguments,
    set_seed,
)

from dataset_utils import DEFAULT_DATASET, load_uit_viquad2, maybe_limit_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune extractive QA reader tren UIT-ViQuAD2.0")
    parser.add_argument("--dataset_name", type=str, default=DEFAULT_DATASET)
    parser.add_argument("--data_dir", type=str, default=None)
    parser.add_argument("--model_name", type=str, default="xlm-roberta-base")
    parser.add_argument("--output_dir", type=str, default="outputs/uit_viquad2_reader")
    parser.add_argument("--max_length", type=int, default=256)
    parser.add_argument("--doc_stride", type=int, default=96)
    parser.add_argument("--max_answer_length", type=int, default=50)
    parser.add_argument("--n_best_size", type=int, default=20)
    parser.add_argument("--null_score_diff_threshold", type=float, default=0.0)
    parser.add_argument("--per_device_train_batch_size", type=int, default=4)
    parser.add_argument("--per_device_eval_batch_size", type=int, default=8)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=1)
    parser.add_argument("--learning_rate", type=float, default=3e-5)
    parser.add_argument("--num_train_epochs", type=float, default=1.0)
    parser.add_argument("--weight_decay", type=float, default=0.01)
    parser.add_argument("--warmup_ratio", type=float, default=0.1)
    parser.add_argument("--logging_steps", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--limit_train_samples", type=int, default=None)
    parser.add_argument("--limit_eval_samples", type=int, default=None)
    parser.add_argument("--dataloader_num_workers", type=int, default=2 if os.name == "nt" else 4)
    return parser.parse_args()


def prepare_train_features_fn(tokenizer, max_length: int, doc_stride: int):
    def _prepare(examples: Dict[str, List]) -> Dict[str, List]:
        questions = [q.lstrip() for q in examples["question"]]
        tokenized_examples = tokenizer(
            questions,
            examples["context"],
            truncation="only_second",
            max_length=max_length,
            stride=doc_stride,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding="max_length",
        )

        sample_mapping = tokenized_examples.pop("overflow_to_sample_mapping")
        offset_mapping = tokenized_examples.pop("offset_mapping")

        start_positions = []
        end_positions = []

        for i, offsets in enumerate(offset_mapping):
            input_ids = tokenized_examples["input_ids"][i]
            cls_index = input_ids.index(tokenizer.cls_token_id)
            sequence_ids = tokenized_examples.sequence_ids(i)
            sample_index = sample_mapping[i]

            if examples["is_impossible"][sample_index]:
                start_positions.append(cls_index)
                end_positions.append(cls_index)
                continue

            answer_start = examples["answer_start"][sample_index]
            answer_end = examples["answer_end"][sample_index]

            token_start_index = 0
            while token_start_index < len(sequence_ids) and sequence_ids[token_start_index] != 1:
                token_start_index += 1

            token_end_index = len(sequence_ids) - 1
            while token_end_index >= 0 and sequence_ids[token_end_index] != 1:
                token_end_index -= 1

            if token_start_index > token_end_index:
                start_positions.append(cls_index)
                end_positions.append(cls_index)
                continue

            if offsets[token_start_index][0] > answer_start or offsets[token_end_index][1] < answer_end:
                start_positions.append(cls_index)
                end_positions.append(cls_index)
            else:
                while token_start_index < len(offsets) and offsets[token_start_index][0] <= answer_start:
                    token_start_index += 1
                start_positions.append(token_start_index - 1)

                while token_end_index >= 0 and offsets[token_end_index][1] >= answer_end:
                    token_end_index -= 1
                end_positions.append(token_end_index + 1)

        tokenized_examples["start_positions"] = start_positions
        tokenized_examples["end_positions"] = end_positions
        return tokenized_examples

    return _prepare


def prepare_validation_features_fn(tokenizer, max_length: int, doc_stride: int):
    def _prepare(examples: Dict[str, List]) -> Dict[str, List]:
        questions = [q.lstrip() for q in examples["question"]]
        tokenized_examples = tokenizer(
            questions,
            examples["context"],
            truncation="only_second",
            max_length=max_length,
            stride=doc_stride,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding="max_length",
        )

        sample_mapping = tokenized_examples.pop("overflow_to_sample_mapping")
        example_ids = []
        cls_indexes = []

        for i in range(len(tokenized_examples["input_ids"])):
            sequence_ids = tokenized_examples.sequence_ids(i)
            sample_index = sample_mapping[i]
            example_ids.append(examples["id"][sample_index])
            cls_indexes.append(tokenized_examples["input_ids"][i].index(tokenizer.cls_token_id))

            offsets = tokenized_examples["offset_mapping"][i]
            tokenized_examples["offset_mapping"][i] = [
                offset if sequence_ids[k] == 1 else None for k, offset in enumerate(offsets)
            ]

        tokenized_examples["example_id"] = example_ids
        tokenized_examples["cls_index"] = cls_indexes
        return tokenized_examples

    return _prepare


def postprocess_qa_predictions(
    examples: Dataset,
    features: Dataset,
    raw_predictions: Tuple[np.ndarray, np.ndarray],
    n_best_size: int,
    max_answer_length: int,
    null_score_diff_threshold: float,
) -> Tuple[Dict[str, str], Dict[str, Dict[str, float]]]:
    all_start_logits, all_end_logits = raw_predictions
    features_per_example: Dict[str, List[int]] = defaultdict(list)
    for i, feature in enumerate(features):
        features_per_example[feature["example_id"]].append(i)

    predictions: Dict[str, str] = {}
    metadata: Dict[str, Dict[str, float]] = {}

    for example in examples:
        example_id = example["id"]
        context = example["context"]
        best_text = ""
        best_score = -1e30
        null_score = -1e30

        for feature_index in features_per_example.get(example_id, []):
            start_logits = all_start_logits[feature_index]
            end_logits = all_end_logits[feature_index]
            offsets = features[feature_index]["offset_mapping"]
            cls_index = int(features[feature_index]["cls_index"])
            null_score = max(null_score, float(start_logits[cls_index] + end_logits[cls_index]))

            start_indexes = np.argsort(start_logits)[-1 : -n_best_size - 1 : -1].tolist()
            end_indexes = np.argsort(end_logits)[-1 : -n_best_size - 1 : -1].tolist()

            for start_index in start_indexes:
                for end_index in end_indexes:
                    if start_index >= len(offsets) or end_index >= len(offsets):
                        continue
                    if offsets[start_index] is None or offsets[end_index] is None:
                        continue
                    if end_index < start_index:
                        continue
                    if end_index - start_index + 1 > max_answer_length:
                        continue
                    start_char = offsets[start_index][0]
                    end_char = offsets[end_index][1]
                    text = context[start_char:end_char].strip()
                    if not text:
                        continue
                    score = float(start_logits[start_index] + end_logits[end_index])
                    if score > best_score:
                        best_score = score
                        best_text = text

        score_diff = null_score - best_score
        no_answer_probability = 1.0 / (1.0 + math.exp(-score_diff)) if abs(score_diff) < 50 else (1.0 if score_diff > 0 else 0.0)
        if best_text and score_diff <= null_score_diff_threshold:
            predictions[example_id] = best_text
        else:
            predictions[example_id] = ""
        metadata[example_id] = {
            "best_span_score": float(best_score),
            "null_score": float(null_score),
            "score_diff": float(score_diff),
            "no_answer_probability": float(no_answer_probability),
        }

    return predictions, metadata


def build_references(examples: Dataset) -> List[Dict]:
    refs = []
    for example in examples:
        refs.append(
            {
                "id": example["id"],
                "answers": {
                    "text": list(example["answers_texts"]),
                    "answer_start": list(example["answers_starts"]),
                },
            }
        )
    return refs


def save_json(data, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    dataset = load_uit_viquad2(dataset_name=args.dataset_name, data_dir=args.data_dir)
    dataset["train"] = maybe_limit_dataset(dataset["train"], args.limit_train_samples)
    eval_split = "validation" if "validation" in dataset else "test"
    dataset[eval_split] = maybe_limit_dataset(dataset[eval_split], args.limit_eval_samples)

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
    if not getattr(tokenizer, "is_fast", False):
        raise ValueError("Can fast tokenizer de tao offset mapping cho QA extractive.")
    model = AutoModelForQuestionAnswering.from_pretrained(args.model_name)

    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU name:", torch.cuda.get_device_name(0))

    train_examples = dataset["train"]
    eval_examples = dataset[eval_split]
    train_features = train_examples.map(
        prepare_train_features_fn(tokenizer, args.max_length, args.doc_stride),
        batched=True,
        remove_columns=train_examples.column_names,
        desc="Tokenizing train split",
    )
    eval_features = eval_examples.map(
        prepare_validation_features_fn(tokenizer, args.max_length, args.doc_stride),
        batched=True,
        remove_columns=eval_examples.column_names,
        desc="Tokenizing validation split",
    )
    eval_features_for_model = eval_features.remove_columns(["example_id", "offset_mapping", "cls_index"])

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        num_train_epochs=args.num_train_epochs,
        weight_decay=args.weight_decay,
        warmup_ratio=args.warmup_ratio,
        save_strategy="epoch",
        eval_strategy="no",
        logging_steps=args.logging_steps,
        report_to="none",
        seed=args.seed,
        fp16=args.fp16,
        tf32=torch.cuda.is_available(),
        remove_unused_columns=True,
        save_total_limit=2,
        dataloader_num_workers=args.dataloader_num_workers,
        dataloader_pin_memory=torch.cuda.is_available(),
    )
    print("Training device:", training_args.device)

    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": train_features,
        "data_collator": DefaultDataCollator(),
    }
    trainer_signature = inspect.signature(Trainer.__init__)
    if "processing_class" in trainer_signature.parameters:
        trainer_kwargs["processing_class"] = tokenizer
    elif "tokenizer" in trainer_signature.parameters:
        trainer_kwargs["tokenizer"] = tokenizer

    trainer = Trainer(**trainer_kwargs)
    trainer.train()
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    predictions_output = trainer.predict(eval_features_for_model)
    raw_predictions = predictions_output.predictions
    if isinstance(raw_predictions, tuple):
        start_logits, end_logits = raw_predictions
    else:
        start_logits, end_logits = raw_predictions[0], raw_predictions[1]

    final_predictions, metadata = postprocess_qa_predictions(
        eval_examples,
        eval_features,
        (start_logits, end_logits),
        n_best_size=args.n_best_size,
        max_answer_length=args.max_answer_length,
        null_score_diff_threshold=args.null_score_diff_threshold,
    )

    metric = evaluate.load("squad_v2")
    formatted_predictions = [
        {
            "id": example_id,
            "prediction_text": prediction_text,
            "no_answer_probability": metadata[example_id]["no_answer_probability"],
        }
        for example_id, prediction_text in final_predictions.items()
    ]
    references = build_references(eval_examples)
    metrics = metric.compute(predictions=formatted_predictions, references=references)

    runtime_config = {
        "model_name": args.model_name,
        "dataset_name": args.dataset_name,
        "max_length": args.max_length,
        "doc_stride": args.doc_stride,
        "max_answer_length": args.max_answer_length,
        "null_score_diff_threshold": args.null_score_diff_threshold,
    }

    print("=== Evaluation ===")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    save_json(metrics, output_dir / "metrics.json")
    save_json(final_predictions, output_dir / "predictions.json")
    save_json(metadata, output_dir / "prediction_metadata.json")
    save_json(runtime_config, output_dir / "reader_runtime_config.json")


if __name__ == "__main__":
    main()
