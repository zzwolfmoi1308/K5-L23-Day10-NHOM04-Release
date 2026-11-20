Release: lab250_d0b5af9eb610_v2
Parent: lab250_d0b5af9eb610
Số ảnh: 242
Số nhãn: 1678
Guideline: v1.2 (J01, J02, J03, J04), v1.3 (J05, J06, J07, J08, J09, J10)
QC v1: 16/250 = 6,4%
Kết luận v1: Hold — tỷ lệ lỗi 6,4% vượt ngưỡng 2%.
Kết luận v2: Release — bàn giao 242 cặp ảnh và nhãn detection. Đã tách 8 ảnh cần người gán và người kiểm xử lý theo rework_queue.csv.
Ghi chú: Đưa cả scene_933 về train theo 4/5 ảnh cùng cảnh. Dùng guideline của job J07 và J08 cho 000000016502 và 000000017899. Đã mở và kiểm hai ảnh sai hash: 000000009772 thấy hai bồn rửa và người trong gương, 000000019042 thấy chim ở bờ sông. Giữ nguyên ảnh và tính lại SHA-256 trong manifest.csv. Phân công gán lại theo cặp người gán và người kiểm: A01 và Q03 (000000007977, 000000008844) / A04 và Q01 (000000018575, 000000019402) / A04 và Q02 (000000015440) / A05 và Q02 (000000014038, 000000015272) / A05 và Q03 (000000006213). Báo nhóm panoptic xử lý 000000017379 (category_swap), 000000005600 (invalid_category_id), 000000002685 (thing_overlap). Nhãn detection của các ảnh này được giữ trong v2.
