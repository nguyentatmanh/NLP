# Lumina QA cho UIT-ViQuAD2.0

Lumina QA là bộ project hỏi đáp tiếng Việt gồm 3 tầng:

- reader extractive QA fine-tune trên **UIT-ViQuAD2.0**
- retriever cho kho tài liệu riêng với **BM25 / dense / hybrid RRF**
- web UI dạng chat, màu sắc mạnh, hiệu ứng mượt, không gắn nhãn công cụ hay watermark

Project này được thiết kế lại để xử lý tốt các câu hỏi **không có đáp án** trong ngữ cảnh, nhờ dataset UIT-ViQuAD2.0 có sẵn trường `is_impossible`.

## 1. Cấu trúc thư mục

```text
uit_viquad2_lumina_qa/
├── api_server.py
├── dataset_utils.py
├── fallback_llm.py
├── qa_reader.py
├── retriever.py
├── text_utils.py
├── train_reader.py
├── requirements.txt
├── README_vi.md
├── REPORT_TEMPLATE.md
├── .env.example
├── demo_kb/
├── scripts/
└── webui/
```

## 2. Cài đặt

### Windows CMD

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. Train reader trên UIT-ViQuAD2.0

Train nhanh 1 epoch:

```bat
python train_reader.py --model_name xlm-roberta-base --output_dir .\outputs\uit_reader_xlmr --num_train_epochs 1 --per_device_train_batch_size 4 --per_device_eval_batch_size 8 --fp16
```

Train demo ít dữ liệu hơn:

```bat
python train_reader.py --model_name xlm-roberta-base --output_dir .\outputs\uit_reader_demo --num_train_epochs 1 --per_device_train_batch_size 4 --per_device_eval_batch_size 8 --fp16 --limit_train_samples 12000 --limit_eval_samples 2000
```

### Gợi ý tốc độ

- `xlm-roberta-base` là cấu hình mặc định dễ chạy hơn cho offset mapping
- nếu GPU 4GB, nên giữ `batch_size=4`, `max_length=256`
- nếu muốn tiếng Việt thuần hơn, có thể thử PhoBERT ở vòng sau, nhưng cần xử lý segmentation kỹ hơn

## 4. Chạy giao diện ngay bằng mock reader

```bat
python api_server.py --mock_reader --docs_dir .\demo_kb --retriever bm25 --host 127.0.0.1 --port 8000
```

Mở trình duyệt:

```text
http://127.0.0.1:8000
```

## 5. Chạy giao diện với model thật

```bat
python api_server.py --reader_model .\outputs\uit_reader_xlmr --docs_dir .\demo_kb --retriever bm25 --host 127.0.0.1 --port 8000
```

## 6. Chạy với hybrid retrieval

```bat
python api_server.py --reader_model .\outputs\uit_reader_xlmr --docs_dir .\kb --retriever hybrid --segmenter pyvi --host 127.0.0.1 --port 8000
```

## 7. Bật fallback sinh câu trả lời khi reader trả rỗng

Project hỗ trợ 2 kiểu fallback:

- `openai_compatible`: endpoint HTTP tương thích kiểu chat completions
- `ollama`: model local chạy qua Ollama

Sao chép file cấu hình:

```bat
copy .env.example .env
```

### Ví dụ dùng OpenAI-compatible

```env
FALLBACK_PROVIDER=openai_compatible
OPENAI_COMPAT_BASE_URL=https://your-endpoint.example/v1
OPENAI_COMPAT_API_KEY=YOUR_KEY
OPENAI_COMPAT_MODEL=YOUR_MODEL
```

Chạy:

```bat
python api_server.py --reader_model .\outputs\uit_reader_xlmr --docs_dir .\kb --retriever hybrid --fallback_provider openai_compatible
```

### Ví dụ dùng Ollama

```env
FALLBACK_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
```

Chạy:

```bat
python api_server.py --reader_model .\outputs\uit_reader_xlmr --docs_dir .\kb --retriever hybrid --fallback_provider ollama
```

## 8. Đưa kho tài liệu của bạn vào hệ thống

Tạo thư mục `kb` rồi chép tài liệu vào đó. Hệ thống đọc được:

- `.txt`
- `.md`
- `.pdf`
- `.docx`

Ví dụ:

```text
kb/
├── gioi_thieu_du_an.md
├── quy_trinh.txt
├── tai_lieu.pdf
└── de_xuat.docx
```

Sau đó chạy lại server với `--docs_dir .\kb`.

## 9. Cơ chế no-answer

Backend không ép model phải trả lời khi không có span phù hợp. Nó dùng:

- best span score
- CLS null score
- ngưỡng `null_score_diff_threshold`

Khi reader không tự tin:

- nếu có fallback: gửi top context sang fallback
- nếu không có fallback: trả về câu từ chối an toàn

## 10. Cơ chế retrieval

- `bm25`: nhanh, dễ kiểm soát, phù hợp baseline
- `dense`: hiểu ngữ nghĩa tốt hơn, tốn thêm thời gian index
- `hybrid`: kết hợp sparse + dense bằng RRF

## 11. Gợi ý thực nghiệm để viết báo cáo

Bạn có thể so sánh các cấu hình sau:

1. `BM25 + XLM-R reader`
2. `Hybrid + XLM-R reader`
3. `BM25 + reader + fallback`
4. `Hybrid + reader + fallback`

Nên đo:

- EM / F1 trên validation
- thời gian train
- thời gian phản hồi trung bình
- chất lượng với câu hỏi có đáp án / không có đáp án

## 12. Lỗi hay gặp

### `unrecognized arguments: \`
Trên Windows CMD, không dùng `\` để xuống dòng. Dùng một dòng hoặc ký tự `^`.

### `... is not a local folder and is not a valid model identifier`
Đường dẫn model local đang sai hoặc thư mục model chưa tồn tại.

### `Trainer.__init__() got an unexpected keyword argument 'tokenizer'`
Project này đã xử lý tương thích bằng cách tự kiểm tra `processing_class/tokenizer`.

### GPU không chạy

Kiểm tra:

```bat
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'No GPU')"
nvidia-smi -l 1
```

## 13. Luồng demo nên dùng

1. Chạy mock UI để kiểm tra giao diện
2. Train demo reader 1 epoch
3. Chạy web với model thật
4. Đưa tài liệu riêng vào `kb`
5. Bật fallback nếu cần xử lý câu hỏi khó hoặc không có span trích trực tiếp
