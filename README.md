### STK 9384222614 Vietcombank

# Hệ thống Hỏi Đáp Tự Động Tiếng Việt với UIT-ViQuAD2.0

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![Transformers](https://img.shields.io/badge/Transformers-HuggingFace-yellow)
![PyTorch](https://img.shields.io/badge/PyTorch-Deep%20Learning-ee4c2c)
![BM25](https://img.shields.io/badge/Retrieval-BM25-orange)
![Git LFS](https://img.shields.io/badge/Model-Git%20LFS-black)
![License](https://img.shields.io/badge/License-MIT-green)

## Giới thiệu

Đây là kho lưu trữ của một **hệ thống hỏi đáp tự động tiếng Việt** được xây dựng theo hướng **Retriever + Reader**, sử dụng dataset **UIT-ViQuAD2.0** để huấn luyện mô hình đọc hiểu trích xuất đáp án (extractive question answering).

Hệ thống hỗ trợ:

- hỏi đáp trên **đoạn văn đầu vào**
- hỏi đáp trên **kho tri thức tài liệu**
- xử lý trường hợp **không có đáp án**
- fallback sang mô hình sinh câu trả lời khi cần
- giao diện web dạng **chat hiện đại**
- backend triển khai bằng **FastAPI**

Mục tiêu của dự án là xây dựng một hệ thống QA tiếng Việt có thể:
- huấn luyện từ dữ liệu chuẩn
- suy luận trên văn bản thực tế
- tích hợp giao diện web để demo
- phục vụ cho mục đích học tập, đồ án, nghiên cứu và triển khai thử nghiệm

---

## Mục lục

- [Giới thiệu](#giới-thiệu)
- [Bài toán hệ thống](#bài-toán-hệ-thống)
- [Dataset sử dụng](#dataset-sử-dụng)
- [Ngôn ngữ và công nghệ](#ngôn-ngữ-và-công-nghệ)
- [Thư viện chính](#thư-viện-chính)
- [Tiền xử lý dữ liệu](#tiền-xử-lý-dữ-liệu)
- [Phương pháp](#phương-pháp)
- [Pipeline hệ thống](#pipeline-hệ-thống)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Quick Start](#quick-start)
- [Cài đặt môi trường](#cài-đặt-môi-trường)
- [Huấn luyện mô hình QA](#huấn-luyện-mô-hình-qa)
- [Chạy giao diện web](#chạy-giao-diện-web)
- [Cách sử dụng](#cách-sử-dụng)
- [Tải model đã train bằng Git LFS](#tải-model-đã-train-bằng-git-lfs)
- [Dữ liệu tri thức đầu vào](#dữ-liệu-tri-thức-đầu-vào)
- [Hướng phát triển](#hướng-phát-triển)
- [Tài liệu tham khảo](#tài-liệu-tham-khảo)

---

## Bài toán hệ thống

Hệ thống giải quyết bài toán **Question Answering (QA)** tiếng Việt theo hai chế độ:

### 1. Extractive QA
Người dùng đưa vào:
- một đoạn văn bản (`context`)
- một câu hỏi (`question`)

Mô hình sẽ tìm **span** phù hợp nhất trong đoạn văn để trích xuất làm câu trả lời.

### 2. Open-domain QA trên kho tri thức
Người dùng chỉ nhập câu hỏi. Hệ thống sẽ:
1. chia tài liệu trong kho tri thức thành các đoạn nhỏ
2. truy hồi top-k đoạn liên quan nhất
3. đưa các đoạn này vào reader
4. chọn đáp án tốt nhất
5. nếu không đủ tự tin thì có thể fallback sang mô hình sinh

---

## Dataset sử dụng

Hệ thống sử dụng dataset:

**UIT-ViQuAD2.0**  
Nguồn: Hugging Face Dataset Hub

Đây là dataset hỏi đáp tiếng Việt theo hướng **extractive QA**, có hỗ trợ cả:
- câu hỏi **có đáp án**
- câu hỏi **không có đáp án** (`is_impossible`)

Các trường dữ liệu quan trọng:
- `context`
- `question`
- `answers`
- `is_impossible`
- `plausible_answers`

Dataset này phù hợp để huấn luyện:
- mô hình reader dạng span extraction
- cơ chế nhận diện **no-answer**
- hệ thống QA tiếng Việt gần với kịch bản thực tế hơn

---

## Ngôn ngữ và công nghệ

- **Ngôn ngữ chính:** Python
- **Backend:** FastAPI
- **Frontend:** HTML, CSS, JavaScript
- **Mô hình QA:** Transformer-based Extractive QA
- **Retriever:** BM25 / Dense Retrieval / Hybrid Retrieval
- **Reader:** XLM-RoBERTa fine-tuned trên UIT-ViQuAD2.0
- **Fallback:** OpenAI-compatible endpoint hoặc Ollama
- **Quản lý model lớn:** Git LFS

---

## Thư viện chính

Dự án sử dụng các thư viện tiêu biểu sau:

- `torch`
- `transformers`
- `datasets`
- `evaluate`
- `fastapi`
- `uvicorn`
- `rank-bm25`
- `sentence-transformers`
- `pydantic`
- `numpy`
- `pyvi` hoặc tokenizer tiếng Việt tương đương

---

## Tiền xử lý dữ liệu

Quy trình tiền xử lý dữ liệu gồm:

- chuẩn hóa schema dữ liệu từ dataset
- chuyển `answers` về định dạng thống nhất
- xử lý các mẫu có `is_impossible = True`
- tạo `answer_start`, `answer_end`
- tokenize câu hỏi và ngữ cảnh bằng tokenizer của mô hình
- ánh xạ từ character span sang token span
- padding / truncation với `max_length`
- sliding window với `doc_stride` cho context dài

Với dữ liệu kho tri thức:
- đọc file `.txt`, `.md`, `.pdf` hoặc nguồn văn bản khác
- làm sạch ký tự
- chuẩn hóa khoảng trắng
- chunk văn bản thành nhiều đoạn nhỏ
- lập chỉ mục phục vụ retrieval

---

## Phương pháp

Hệ thống được xây dựng theo kiến trúc:

### 1. Retriever
Tìm các đoạn văn liên quan nhất đến câu hỏi từ kho tri thức.

Các phương pháp hỗ trợ:
- **BM25**
- **Dense Retrieval**
- **Hybrid Retrieval** (kết hợp sparse + dense)

### 2. Reader
Mô hình đọc hiểu trích xuất đáp án từ các đoạn đã truy hồi.

- backbone mặc định: `xlm-roberta-base`
- fine-tune cho bài toán question answering
- đầu ra: vị trí bắt đầu và kết thúc của span đáp án

### 3. No-answer Handling
Nếu mô hình reader cho độ tin cậy thấp hoặc dự đoán null score vượt ngưỡng:
- hệ thống có thể trả về **không tìm thấy đáp án phù hợp**
- hoặc gọi sang mô hình fallback để diễn giải câu trả lời

### 4. Fallback Generation
Tùy chọn tích hợp:
- OpenAI-compatible API
- Ollama local model

Mục đích:
- hỗ trợ trả lời mềm hơn khi reader không tìm được span tốt
- cải thiện trải nghiệm người dùng trong chế độ chat

---

## Pipeline hệ thống

Pipeline tổng quát:

```text
Người dùng nhập câu hỏi
        ↓
Chọn chế độ:
- Hỏi theo context
- Hỏi theo kho tri thức
        ↓
Nếu là kho tri thức:
    Chunk tài liệu → Retriever → Top-k đoạn liên quan
        ↓
Reader QA dự đoán answer span
        ↓
Kiểm tra confidence / no-answer
        ↓
Nếu cần: gọi fallback LLM
        ↓
Trả kết quả ra giao diện web
```

---

## Cấu trúc thư mục

```text
.
├── api_server.py
├── train_reader.py
├── dataset_utils.py
├── qa_reader.py
├── retriever.py
├── fallback_llm.py
├── text_utils.py
├── requirements.txt
├── README.md
├── REPORT_TEMPLATE.docx
├── REPORT_TEMPLATE.md
├── webui/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── scripts/
│   ├── train_reader_win.bat
│   ├── run_ui_win.bat
│   └── run_mock_ui_win.bat
├── demo_kb/
├── kb/
└── outputs/
```

---

## Quick Start

### 1. Clone repository

```bash
git clone https://github.com/nguyentatmanh/NLP.git
cd NLP
```

### 2. Tạo môi trường ảo

**Windows (PowerShell / CMD):**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Cài dependencies

```bash
pip install -r requirements.txt
```

### 4. Chạy giao diện demo nhanh

```bash
python api_server.py --mock_reader --docs_dir .\demo_kb --retriever bm25 --host 127.0.0.1 --port 8000
```

### 5. Mở trình duyệt

```text
http://127.0.0.1:8000
```

---

## Cài đặt môi trường

Yêu cầu khuyến nghị:

- Python **3.10+**
- Git
- Git LFS
- CUDA + GPU NVIDIA (nếu muốn train nhanh)
- RAM tối thiểu 8GB
- GPU khuyến nghị: NVIDIA RTX 3050 trở lên

Nếu muốn kiểm tra GPU:

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

---

## Huấn luyện mô hình QA

### Huấn luyện reader từ UIT-ViQuAD2.0

Ví dụ lệnh huấn luyện:

```bash
python train_reader.py \
  --model_name xlm-roberta-base \
  --output_dir .\outputs\uit_reader_xlmr \
  --num_train_epochs 1 \
  --per_device_train_batch_size 4 \
  --per_device_eval_batch_size 8 \
  --fp16
```

### Mô tả nhanh
- `model_name`: mô hình backbone
- `output_dir`: nơi lưu model sau khi train
- `num_train_epochs`: số epoch
- `fp16`: mixed precision để tiết kiệm VRAM và tăng tốc

### Sau khi train xong
Model sẽ được lưu trong thư mục:

```text
outputs/uit_reader_xlmr
```

Các file quan trọng:
- `model.safetensors`
- `config.json`
- `tokenizer.json`
- `tokenizer_config.json`
- `training_args.bin`
- `metrics.json`
- `predictions.json`

---

## Chạy giao diện web

### Chạy bằng model thật

```bash
python api_server.py \
  --reader_model .\outputs\uit_reader_xlmr \
  --docs_dir .\kb \
  --retriever hybrid \
  --host 127.0.0.1 \
  --port 8000
```

### Chạy chế độ demo không cần model thật

```bash
python api_server.py \
  --mock_reader \
  --docs_dir .\demo_kb \
  --retriever bm25 \
  --host 127.0.0.1 \
  --port 8000
```

---

## Cách sử dụng

### Chế độ 1: Hỏi theo context
- nhập đoạn văn bản
- nhập câu hỏi
- hệ thống trả span đáp án trích xuất trực tiếp từ context

### Chế độ 2: Hỏi theo kho tri thức
- nạp tài liệu vào thư mục `kb/`
- nhập câu hỏi trên giao diện
- hệ thống tự retrieval các đoạn phù hợp
- reader chọn đáp án tốt nhất
- nếu không chắc chắn, fallback có thể được kích hoạt

### Chế độ 3: Demo nhanh
- dùng `demo_kb/`
- không cần model thật nếu bật `--mock_reader`
- phù hợp để test giao diện và luồng hệ thống

---

## Tải model đã train bằng Git LFS

Nếu repo chứa model lớn, bạn cần Git LFS để tải đầy đủ:

### Cài Git LFS

```bash
git lfs install
```

### Clone repo và kéo model LFS

```bash
git clone https://github.com/nguyentatmanh/NLP.git
cd NLP
git lfs pull
```

### Kiểm tra file LFS

```bash
git lfs ls-files
```

---

## Dữ liệu tri thức đầu vào

Kho tri thức mặc định có thể đặt trong:

```text
kb/
```

Bạn có thể thêm các file:
- `.txt`
- `.md`

Mỗi file nên chứa:
- nội dung sạch
- có cấu trúc tiêu đề rõ ràng
- chia đoạn hợp lý
- không chứa quá nhiều ký tự rác

Hệ thống sẽ:
- đọc tài liệu
- chunk nội dung
- xây dựng index retrieval
- trả lời theo cơ chế retriever + reader

---

## Hướng phát triển

Một số hướng mở rộng trong tương lai:

- bổ sung vector database
- thêm reranker sau retrieval
- huấn luyện trên nhiều dataset tiếng Việt hơn
- cải thiện ngưỡng no-answer
- tích hợp mô hình sinh câu trả lời tốt hơn
- hỗ trợ upload tài liệu trực tiếp từ giao diện
- hỗ trợ multi-turn conversation
- thêm lịch sử hội thoại
- thêm đánh giá định lượng và logging chuyên sâu

---

## Tài liệu tham khảo

- UIT-ViQuAD2.0
- Hugging Face Transformers
- Hugging Face Datasets
- PyTorch
- FastAPI
- BM25 Retrieval
- Dense Retrieval
- Hybrid QA Systems
- Các tài liệu về NLP và Deep Learning tiếng Việt được sử dụng để xây dựng phần lý thuyết và thiết kế hệ thống

---
