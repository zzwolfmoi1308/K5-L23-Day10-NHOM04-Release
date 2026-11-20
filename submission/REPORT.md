# Báo cáo nhóm 04

## 1. Số liệu luyện tập
- Seed chính: `4007` (`lab250_d0b5af9eb610`), đã ghi sự kiện tạo lô và training run `R-021` trong lineage. Seed kiểm tra thêm: `4008`.
- Kết quả chạy riêng mô-đun panoptic (`invalid_category_id` / `thing_overlap`): `4007` báo 1 / 1, `4008` báo 1 / 2, lô sạch 50 ảnh báo 0 / 0.
- Kết quả Pha 1 của bảy luật file, YOLO và metadata khớp từng cặp `(type, target)` với phần tương ứng trong `errors.json` đã dùng để tự đo. Lô sạch 50 ảnh báo **0 lỗi luật**.
- Sau review, `score_findings.py` cho seed `4007` báo F1 lỗi luật ≈ **1,0**, F1 lỗi gán nhãn ≈ **0,8** và F1 tổng ≈ **0,9**. Số liệu được làm tròn đến một chữ số thập phân.
- Lô sạch seed 5, pool calib 50 ảnh, có **0 ứng viên**. Lô luyện tập seed 4007 có **9 dòng ứng viên trên 6 ảnh** gồm 3 `class_swap`, 3 `category_swap`, 1 `bbox_drift`, 1 `missing_box` và 1 `instance_merge`. Ba ca lệch lớp đều có hai khả năng; người xem ảnh xác định nguồn nào sai.
- Ghép theo tên lớp trước nếu IoU bbox ≥ 0,48 và ít nhất 91% pixel segment nằm trong box. Loại crowd, chỉ dùng thing có diện tích khai báo khớp mask. Khi đếm pixel trong box, nới 1 px để dung sai làm tròn YOLO và mask.
- Lệch lớp cần IoU ≥ 0,61 và bao phủ ≥ 86% pixel segment. Lệch box cùng lớp cần IoU ≥ 0,25, bao phủ 22–88% và chiều rộng, chiều cao của box nằm trong 0,60–1,65 lần so với segment. Các ngưỡng này ưu tiên cặp gần nhau và lọc khác biệt do kích thước nhãn.
- Thiếu box cần segment có ít nhất 350 pixel và 0,2% diện tích ảnh, không có box giải thích được vùng mask. Gộp instance cần hai box cùng lớp có IoU giữa chúng ≤ 0,22, khung bao chung khớp khung segment với IoU ≥ 0,47, và hai box cùng chứa ≥ 76% pixel segment. Phần riêng trong mỗi box phải đạt ít nhất 8% pixel segment, 10% diện tích box và 40 pixel để loại các ca chỉ chạm mép. Xét thêm box nhỏ nằm chủ yếu trong khung segment để phát hiện trường hợp hai vật chênh kích thước.
- Thử ba mức trên đúng hai lô từ dữ liệu `delivery/`. Mức chặt dùng ngưỡng lệch lớp 0,68 IoU và 91% bao phủ, lệch box 0,30 IoU và 28–83%, thiếu box 550 pixel và 0,3%, gộp 17% phần riêng và 82% phần chung. Mức lỏng hạ các ngưỡng tương ứng xuống 0,45 và 74%, 0,19 và 12–95%, 100 pixel và 0,04%, 4% và 66%. Cả ba mức cho cùng số đếm (0 trên lô sạch, 9 dòng trên 6 ảnh luyện tập). Chọn mức giữa để giữ độ nhạy với lệch vừa, đồng thời giữ yêu cầu về kích thước và độ khớp hình học. Số liệu lô sạch đo nhiễu trên tập calib. Độ bỏ sót cần được đánh giá sau khi nhóm chốt kết quả review.

| Lô | Số phát hiện thuộc bảy luật file, YOLO và metadata | F1 của cả nhóm lỗi luật, làm tròn bởi `score_findings.py` |
|---|---:|---:|
| Sạch, seed 5 | 0 | ≈ 1,0 |
| Luyện tập, seed 4007 | 9 | ≈ 1,0 |
| Seed 4008 | 7 | ≈ 1,0 |
| Seed 4009 | 7 | ≈ 1,0 |

Chạy lệnh sau để kiểm riêng bảy luật trên seed luyện tập.

```powershell
python -X utf8 validator/detection_rules.py runs/r4007/delivery --out runs/r4007/detection_rules.json
```

## 2. Vì sao báo hết ứng viên làm F1 giảm?
Review seed `4007` xác nhận 5 ứng viên và bác bỏ 4. Đưa cả 9 dòng vào lỗi cuối sẽ tính cả 4 ứng viên bị bác bỏ là lỗi, gồm 3 khả năng đổi lớp sai nguồn và 1 ca segment chỉ bao quanh một người. Báo thừa làm giảm precision và kéo F1 xuống nếu recall giữ nguyên.

## 3. Quyết định và lineage
- QC v1: **16/250 ảnh (6,4%)**, gồm 11 lỗi luật và 5 lỗi gán nhãn đã xác nhận. Mỗi mục `scene_leak` tính cho một ảnh. Tỷ lệ vượt ngưỡng 2%, nên lineage ghi **`HOLD`** cho `lab250_d0b5af9eb610`.
- `lineage.py impact` trả về `R-021: affected=True action=review_or_retrain`. Run này đã train bằng v1. Cần xem lại kết quả hoặc train lại với dữ liệu đã xử lý vì trọng số của model hiện tại vẫn phản ánh lô v1. Lineage đã ghi release `lab250_d0b5af9eb610_v2` với parent `lab250_d0b5af9eb610`. Lô v2 bàn giao 242 ảnh với 1.678 nhãn detection và tách 8 ảnh để gán lại. Bộ kiểm bàn giao đạt 17/17 mục. [README của lô v2](r4007/handover/lab250_d0b5af9eb610_v2/README.txt)

## 4. Hash chứng minh gì, không chứng minh gì?
SHA-256 giúp kiểm tra file nhận được có khớp từng byte với file đã lập manifest hay không. Độ đúng của lớp, box và nội dung ảnh cần được kiểm tra bằng quy tắc và review ảnh. Hai file cùng nội dung có thể cùng chứa một nhãn sai.

## 5. Truy vết
- `tier_a` gồm ảnh trong các cảnh được ticket nêu, thuộc job theo guideline cũ và có ít nhất một box detection thuộc lớp đổi quy tắc.
- `tier_b` gồm các ảnh ngoài các cảnh được nêu với cùng điều kiện về job và lớp detection. `notify` gồm mã người gán và người kiểm của các job chứa ảnh ở hai tầng.
- Dùng guideline trong `jobs.csv` vì phiên bản lưu theo ảnh có thể bị `guideline_mismatch`. Với seed `4007`, ticket nêu lớp `wine glass` ở `scene_156` và `scene_643`. Trong các job dùng v1.2, có 4 ảnh có box lớp này ở hai cảnh được báo và 3 ảnh ở các cảnh khác. Hai tầng cùng dẫn đến người gán `A01` và người kiểm `Q03`. [Danh sách ảnh và người cần báo](r4007/trace.json).

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
- Trên máy Windows dùng CP1258, `py -X utf8 scripts/run_lab.py --seeds 4007` tạo xong lô v1 nhưng tiến trình con lỗi khi in tiếng Việt, trước khi `run_lab.py` ghi lineage. Nhóm xác nhận `release.json` đã có và dùng `lineage.py record` để ghi hai sự kiện `inject` và `train` cho lô hiện có.
- Với gói v2 của seed `4007`, H15 đạt trên Windows. Khi mô phỏng cách POSIX sắp tên tệp và ghi hệ điều hành tạo ZIP, cùng 489 tệp cho SHA-256 khác. `pack_release.py` dùng thứ tự của `Path` và thông tin hệ điều hành mặc định của `ZipInfo`. Khi trao đổi giữa các hệ điều hành, có thể kiểm tra trực tiếp ZIP đã bàn giao bằng tệp `.sha256` đi kèm.
