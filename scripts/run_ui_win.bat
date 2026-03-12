@echo off
python api_server.py --reader_model .\outputs\uit_reader_xlmr --docs_dir .\demo_kb --retriever bm25 --host 127.0.0.1 --port 8000
