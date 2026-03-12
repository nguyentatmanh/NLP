# Khung báo cáo đề tài

## Tên đề tài
Xây dựng hệ thống hỏi đáp tiếng Việt tự động trên UIT-ViQuAD2.0 kết hợp truy hồi tài liệu và mô hình đọc hiểu

## 1. Mở đầu
- Bối cảnh bài toán hỏi đáp tiếng Việt
- Ý nghĩa thực tiễn của hệ thống hỏi đáp tự động
- Mục tiêu của đề tài

## 2. Cơ sở lý thuyết
### 2.1 Đặc thù tiếng Việt trong NLP
- tách từ
- dấu thanh và chuẩn hóa văn bản
- khó khăn của biểu diễn token trong tiếng Việt

### 2.2 Các phương pháp truy hồi thông tin
- TF-IDF
- BM25
- Dense retrieval
- Hybrid retrieval và Reciprocal Rank Fusion

### 2.3 Mô hình học sâu cho NLP
- BERT và Transformer
- cơ chế fine-tuning cho Question Answering
- no-answer trong extractive QA

## 3. Dữ liệu sử dụng
- Dataset UIT-ViQuAD2.0
- số lượng train / validation / test
- cấu trúc trường dữ liệu
- câu hỏi có đáp án và không có đáp án

## 4. Thiết kế hệ thống
### 4.1 Kiến trúc tổng thể
- tầng retriever
- tầng reader
- tầng fallback
- tầng giao diện web

### 4.2 Tiền xử lý và lập chỉ mục
- chuẩn hóa văn bản
- chunk tài liệu
- tokenization cho truy hồi

### 4.3 Mô hình reader
- backbone
- input format question + context
- dự đoán start/end span
- null score và ngưỡng no-answer

### 4.4 Backend API
- `/chat`
- `/config`
- `/reindex`

### 4.5 Giao diện người dùng
- bố cục
- cách hiển thị hội thoại
- trình bày nguồn tham chiếu

## 5. Thực nghiệm
- cấu hình máy
- cấu hình hyperparameters
- số epoch, learning rate, batch size
- retriever sử dụng

## 6. Kết quả và đánh giá
- EM / F1 của reader
- so sánh BM25, dense, hybrid
- chất lượng với câu hỏi impossible
- thời gian phản hồi và trải nghiệm sử dụng

## 7. Kết luận và hướng phát triển
- kết quả đạt được
- hạn chế
- hướng cải tiến: PhoBERT, reranker, calibration threshold, RAG sinh văn bản
