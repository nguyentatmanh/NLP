Lumina là hệ thống hỏi đáp tiếng Việt theo kiến trúc retrieval + reader.
Hệ thống gồm ba lớp chính: retriever để tìm đoạn văn phù hợp, reader để trích span trả lời, và fallback để tạo câu trả lời khi reader không tìm được span đủ tin cậy.
Khi người dùng đặt câu hỏi, hệ thống sẽ truy hồi nhiều đoạn văn liên quan, chấm điểm từng đoạn, sau đó chọn câu trả lời tốt nhất. Nếu không có đáp án rõ ràng, hệ thống trả về thông báo không đủ thông tin hoặc dùng fallback nếu đã bật.
