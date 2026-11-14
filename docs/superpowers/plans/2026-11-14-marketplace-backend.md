# Marketplace Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Xây nền nghiệp vụ chạy local để nối Deplao sau khi sửa listener.

**Architecture:** Bridge tin cậy gửi sự kiện chuẩn hóa đến FastAPI bằng bridge key. SQLite lưu nháp, trạng thái, quyết định duyệt và kết quả xử lý tin nhắn. BQL dùng admin key riêng cho demo local.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, unittest, httpx.

**Spec:** docs/brief-prd.md

## Global Constraints
- Không tuyên bố Zalo end-to-end, Gemini extraction hoặc semantic search đã chạy.
- Không chia sẻ thông tin liên hệ; bridge chỉ do server tin cậy gọi.
- Không cho tin chờ duyệt/từ chối/đã bán xuất hiện khi tìm mua.
- Không lưu secrets trong repo. Chỉ bind localhost mặc định.

## Review Focus
- Event trùng phải trả cùng kết quả, kể cả nội dung bị đổi.
- Không thao tác hoặc tìm kiếm chéo khu.
- ID người dùng khác không được đóng tin của chủ tin.
- Giá âm, thiếu thông tin, quá dài phải bị từ chối.
- Tin tự gửi và tin nhóm không tạo nháp; admin/bridge key không dùng thay nhau.

## Task 1: Nghiệp vụ lưu tin và sự kiện
- [x] Viết unittest bằng TestClient cho vòng tạo nháp–xác nhận–duyệt–tìm–đóng.
- [x] Chạy và quan sát lỗi trước khi có app.
- [x] Tạo `backend/app.py`: POST /events, GET /listings, POST /listings/{id}/review.
- [x] Test lại quyền, khu, tin trùng và dữ liệu xấu.

## Task 2: Hướng dẫn tích hợp và vận hành local
- [x] Viết cấu hình môi trường mẫu không có khóa thật, README và hợp đồng sự kiện.
- [x] Smoke test HTTP thật trên localhost; không gửi Zalo.
- [x] Commit và push branch lên repo GitHub đã được yêu cầu; PR #1 đã mở, chưa merge.

## Bằng chứng kiểm tra
- 6 unittest pass: lifecycle, phân quyền/khu, trùng sự kiện, từ chối, đầu vào, khóa riêng.
- HTTP smoke thật qua uvicorn: health, tạo nháp, docs đều OK; process đã dừng.
- PowerShell parser: không có lỗi cú pháp. Chưa chạy tương tác script với người dùng.
- Review độc lập: không phát hiện lỗi critical/important trong phạm vi local demo.
- CI được cấu hình để chạy cùng bộ test khi push; chưa xác nhận CI remote.

## Các chặng tiếp theo (chưa triển khai trong đợt này)
- Khôi phục listener Deplao; nối HTTP đã xác minh đúng schema và ánh xạ người gửi/khu từ backend.
- Gemini extraction, xác nhận nhiều lượt, gắn cờ nghi ngờ và đánh giá moderation.
- Supabase/PostgreSQL + pgvector, kho ảnh, RLS và đăng nhập BQL.
- Dashboard, tìm kiếm ngữ nghĩa, triển khai VPS, retry/outbox, giám sát và backup.
