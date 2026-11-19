# Nhóm 04

- Seed luyện tập: 4007
- Repo: https://github.com/zzwolfmoi1308/K5-L23-Day10-NHOM04-Release

| Họ và tên | MSHV | Tài khoản GitHub | Phần chính |
|---|---|---|---|
| Nguyễn Văn Bảo | 2A202603104 | baobao201 | Chốt seed, viết CLI `validator/validate.py`, tích hợp 9 luật và phần sinh ứng viên. Kiểm thử trên ít nhất hai seed và lô sạch. Gộp lỗi sau review, ghi quyết định v1 và ảnh hưởng tới `R-021`, tổng hợp `REPORT.md` và kiểm tra bài nộp. |
| Nguyễn Tuấn Điệp | 2A202603057 | diepnguyentuan | Viết và kiểm thử 7 luật về file, YOLO và metadata: `missing_image`, `wrong_hash`, `invalid_class`, `bbox_out_of_bounds`, `duplicate_box`, `scene_leak`, `guideline_mismatch`. |
| Ngô Xuân Tùng | 2A202603225 | zzwolfmoi1308 | Viết và kiểm thử `invalid_category_id` và `thing_overlap`. Đọc mask panoptic và cung cấp logic ghép box–segment theo tên lớp, vị trí và độ phủ pixel cho thành viên 4. |
| Hồ Trung Kiên | 2A202603090 | TrungKien0905 | Sinh `candidates.json` cho 5 lỗi gán nhãn. Đo số ứng viên trên lô sạch, ghi lý do chọn ngưỡng, chuẩn bị công cụ xem ảnh, chia hàng đợi và gộp `review_log.csv`. |
| Vũ Duy Khanh | 2A202603142 | o0DzeroK0o | Làm `trace.json` và `security.md`. Dựng lô v2 từ `errors.json` đã chốt, lập manifest, thống kê nhãn, bảng truy vết và hàng đợi gán lại. Đóng gói, ghi lineage release v2 cùng nhóm trưởng và chạy `check_handover.py`. |

## Việc chung

- Cả 5 người trực tiếp xem ảnh ở bài luyện tập và đề ẩn. Mỗi dòng review ghi người xem và quan sát cụ thể trong cột `note`.
- Trong 40 phút đề ẩn, nhóm trưởng chạy validator và chốt `errors.json`, thành viên 4 chia ảnh và gộp review, thành viên 5 làm truy vết ngay khi nhận lô. Dành 5 phút cuối để kiểm đủ bốn file trong `submission/de_an/` và chốt commit.
- Mỗi người có ít nhất 2 commit có nội dung. Ai dùng AI ghi prompt, chỗ AI sai nếu có và cách kiểm lại vào `submission/prompts.md`.
