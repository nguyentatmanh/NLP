from __future__ import annotations

import argparse
import json
import re
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def plot_line(xs, ys, xlabel, ylabel, title, out_path: Path):
    if not xs or not ys:
        return False
    plt.figure(figsize=(8, 4.8))
    plt.plot(xs, ys, marker="o", linewidth=1.8, markersize=3)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()
    return True


def plot_bar(labels, values, title, ylabel, out_path: Path):
    if not labels or not values:
        return False
    plt.figure(figsize=(8, 4.8))
    plt.bar(labels, values)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(rotation=15)
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close()
    return True


def build_metrics_plots(metrics: dict, figures_dir: Path):
    overall_labels = []
    overall_values = []
    for key in ["exact", "f1", "best_exact", "best_f1"]:
        if key in metrics:
            overall_labels.append(key)
            overall_values.append(float(metrics[key]))
    plot_bar(
        overall_labels,
        overall_values,
        "Tong quan chi so QA",
        "Gia tri",
        figures_dir / "qa_overall_metrics.png",
    )

    split_labels = []
    split_values = []
    for key in ["HasAns_f1", "NoAns_f1", "HasAns_exact", "NoAns_exact"]:
        if key in metrics:
            split_labels.append(key)
            split_values.append(float(metrics[key]))
    plot_bar(
        split_labels,
        split_values,
        "So sanh nhom co dap an va khong co dap an",
        "Gia tri",
        figures_dir / "qa_hasans_noans_metrics.png",
    )


def find_trainer_state(model_dir: Path) -> Path | None:
    direct = model_dir / "trainer_state.json"
    if direct.exists():
        return direct

    candidates = []
    for p in model_dir.glob("checkpoint-*/trainer_state.json"):
        m = re.search(r"checkpoint-(\d+)", str(p))
        step = int(m.group(1)) if m else -1
        candidates.append((step, p))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def build_trainer_plots(trainer_state: dict, figures_dir: Path):
    log_history = trainer_state.get("log_history", [])
    steps_loss, loss_values = [], []
    steps_lr, lr_values = [], []
    steps_grad, grad_values = [], []

    for item in log_history:
        if "loss" in item and "step" in item:
            try:
                steps_loss.append(item["step"])
                loss_values.append(float(item["loss"]))
            except Exception:
                pass
        if "learning_rate" in item and "step" in item:
            try:
                steps_lr.append(item["step"])
                lr_values.append(float(item["learning_rate"]))
            except Exception:
                pass
        if "grad_norm" in item and "step" in item:
            try:
                steps_grad.append(item["step"])
                grad_values.append(float(item["grad_norm"]))
            except Exception:
                pass

    generated = []

    if plot_line(
        steps_loss,
        loss_values,
        "Step",
        "Loss",
        "Duong cong training loss",
        figures_dir / "training_loss_vs_step.png",
    ):
        generated.append("training_loss_vs_step.png")

    if plot_line(
        steps_lr,
        lr_values,
        "Step",
        "Learning rate",
        "Lich trinh learning rate",
        figures_dir / "learning_rate_vs_step.png",
    ):
        generated.append("learning_rate_vs_step.png")

    if plot_line(
        steps_grad,
        grad_values,
        "Step",
        "Grad norm",
        "Do lon gradient theo step",
        figures_dir / "grad_norm_vs_step.png",
    ):
        generated.append("grad_norm_vs_step.png")

    return generated


def write_latex_snippet(out_path: Path, generated_files: list[str]):
    chunks = []

    if "training_loss_vs_step.png" in generated_files:
        chunks.append(r"""
\begin{figure}[H]
    \centering
    \includegraphics[width=0.85\textwidth]{figures/training_loss_vs_step.png}
    \caption{Duong cong training loss theo step.}
    \label{fig:training-loss}
\end{figure}
""")

    if "learning_rate_vs_step.png" in generated_files:
        chunks.append(r"""
\begin{figure}[H]
    \centering
    \includegraphics[width=0.85\textwidth]{figures/learning_rate_vs_step.png}
    \caption{Lich trinh learning rate trong qua trinh huan luyen.}
    \label{fig:learning-rate}
\end{figure}
""")

    chunks.append(r"""
\begin{figure}[H]
    \centering
    \includegraphics[width=0.85\textwidth]{figures/qa_overall_metrics.png}
    \caption{So sanh cac chi so tong quan cua mo hinh QA.}
    \label{fig:qa-overall-metrics}
\end{figure}
""")

    chunks.append(r"""
\begin{figure}[H]
    \centering
    \includegraphics[width=0.85\textwidth]{figures/qa_hasans_noans_metrics.png}
    \caption{So sanh ket qua giua nhom cau hoi co dap an va khong co dap an.}
    \label{fig:qa-hasans-noans}
\end{figure}
""")

    out_path.write_text("\n\n".join(textwrap.dedent(c).strip() for c in chunks) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Tao bieu do thuc nghiem cho bao cao QA.")
    parser.add_argument("--model_dir", type=str, default=r".\outputs\uit_reader_xlmr")
    parser.add_argument("--out_dir", type=str, default=r".\report_figures")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    out_dir = Path(args.out_dir)
    figures_dir = out_dir / "figures"
    ensure_dir(figures_dir)

    metrics_path = model_dir / "metrics.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"Khong tim thay metrics.json tai: {metrics_path}")

    metrics = load_json(metrics_path)
    build_metrics_plots(metrics, figures_dir)
    generated_files = ["qa_overall_metrics.png", "qa_hasans_noans_metrics.png"]

    trainer_state_path = find_trainer_state(model_dir)
    warning = None
    if trainer_state_path is not None:
        trainer_state = load_json(trainer_state_path)
        generated_files.extend(build_trainer_plots(trainer_state, figures_dir))
    else:
        warning = (
            "Khong tim thay trainer_state.json trong thu muc model hoac checkpoint. "
            "Van da tao cac bieu do metrics. "
            "Neu muon co them loss/lr/grad plots, hay giu lai checkpoint hoac copy trainer_state.json vao thu muc model."
        )

    generated_files = sorted(set(generated_files))
    write_latex_snippet(out_dir / "latex_figures_snippet.tex", generated_files)

    summary = {
        "metrics_path": str(metrics_path),
        "trainer_state_path": str(trainer_state_path) if trainer_state_path else None,
        "output_dir": str(out_dir),
        "generated_files": generated_files,
        "warning": warning,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
