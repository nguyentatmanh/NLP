
Chạy lại server với:
   python api_server.py --reader_model .\outputs\uit_reader_xlmr --docs_dir .\kb --retriever hybrid --segmenter pyvi --host 127.0.0.1 --port 8000

Lưu ý:
- Đây là bộ tri thức biên soạn để demo hỏi đáp.
- Có thể trộn nhiều gói với nhau.
- Nên ưu tiên nhiều file nhỏ, rõ chủ đề để retriever hoạt động tốt hơn.
