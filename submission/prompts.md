# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | Hồ Trung Kiên | Codex | Đọc GUIDE.md; sinh ứng viên cho 5 lỗi, đo trên lô sạch, ghi lý do chọn ngưỡng, chuẩn bị công cụ xem ảnh, chia hàng đợi và gộp review_log.csv. Dùng seed 4007. | Bản đầu lọc cặp IoU dưới 0,10 nên bỏ qua box nhỏ có thể nằm trong segment gộp. Đã thêm tín hiệu box nhỏ nằm trong khung segment và đo phần pixel riêng của cả hai box. | Chạy lại trên lô sạch 50 ảnh và seed 4007, thử ngưỡng chặt/lỏng, kiểm thử bằng dữ liệu tổng hợp. Kết luận trên ảnh luyện tập do thành viên ghi. |
