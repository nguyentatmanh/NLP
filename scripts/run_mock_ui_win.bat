@echo off
python api_server.py --mock_reader --docs_dir .\demo_kb --retriever bm25 --host 127.0.0.1 --port 8000
