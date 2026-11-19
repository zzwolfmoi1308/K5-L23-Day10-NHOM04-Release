# Báo cáo nhóm 04

## 1. Số liệu luyện tập
- Seed chính: `4007` (`lab250_d0b5af9eb610`), đã ghi sự kiện tạo lô và training run `R-021` trong lineage. Seed kiểm tra thêm: `4008`.
- Kết quả chạy riêng mô-đun panoptic (`invalid_category_id` / `thing_overlap`): `4007` báo 1 / 1, `4008` báo 1 / 2, lô sạch 50 ảnh báo 0 / 0.
- F1 seed 4007 (rule / cross_check / overall) sẽ đo sau khi tích hợp lỗi luật và chốt review bằng mắt.
- Lô sạch seed 5, pool calib 50 ảnh, có **0 ứng viên**. Lô luyện tập seed 4007 có **9 dòng ứng viên trên 6 ảnh** gồm 3 `class_swap`, 3 `category_swap`, 1 `bbox_drift`, 1 `missing_box` và 1 `instance_merge`. Ba ca lệch lớp đều có hai khả năng; người xem ảnh xác định nguồn nào sai.
- Ghép theo tên lớp trước nếu IoU bbox ≥ 0,48 và ít nhất 91% pixel segment nằm trong box. Loại crowd, chỉ dùng thing có diện tích khai báo khớp mask. Khi đếm pixel trong box, nới 1 px để dung sai làm tròn YOLO và mask.
- Lệch lớp cần IoU ≥ 0,61 và bao phủ ≥ 86% pixel segment. Lệch box cùng lớp cần IoU ≥ 0,25, bao phủ 22–88% và chiều rộng, chiều cao của box nằm trong 0,60–1,65 lần so với segment. Các ngưỡng này ưu tiên cặp gần nhau và lọc khác biệt do kích thước nhãn.
- Thiếu box cần segment có ít nhất 350 pixel và 0,2% diện tích ảnh, không có box giải thích được vùng mask. Gộp instance cần hai box cùng lớp có IoU giữa chúng ≤ 0,22, khung bao chung khớp khung segment với IoU ≥ 0,47, và hai box cùng chứa ≥ 76% pixel segment. Phần riêng trong mỗi box phải đạt ít nhất 8% pixel segment, 10% diện tích box và 40 pixel để loại các ca chỉ chạm mép. Xét thêm box nhỏ nằm chủ yếu trong khung segment để phát hiện trường hợp hai vật chênh kích thước.
- Thử ba mức trên đúng hai lô từ dữ liệu `delivery/`. Mức chặt dùng ngưỡng lệch lớp 0,68 IoU và 91% bao phủ, lệch box 0,30 IoU và 28–83%, thiếu box 550 pixel và 0,3%, gộp 17% phần riêng và 82% phần chung. Mức lỏng hạ các ngưỡng tương ứng xuống 0,45 và 74%, 0,19 và 12–95%, 100 pixel và 0,04%, 4% và 66%. Cả ba mức cho cùng số đếm (0 trên lô sạch, 9 dòng trên 6 ảnh luyện tập). Chọn mức giữa để giữ độ nhạy với lệch vừa, đồng thời giữ yêu cầu về kích thước và độ khớp hình học. Số liệu lô sạch đo nhiễu trên tập calib. Độ bỏ sót cần được đánh giá sau khi nhóm chốt kết quả review.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
Nếu đưa cả 9 dòng ứng viên của seed 4007 vào lỗi cuối, riêng 3 ảnh bất đồng về lớp đã tạo ít nhất 3 báo thừa vì mỗi ảnh có tối đa một lỗi. Báo thừa làm giảm precision và kéo F1 xuống nếu recall giữ nguyên. Review giữ dòng đúng theo ảnh và giúp loại các lệch tự nhiên giữa hai nguồn nhãn.

## 3. Quyết định và lineage
- QC v1: <<ảnh lỗi / tổng số ảnh; tỷ lệ và kết luận>>. Theo ngưỡng lab, tỷ lệ trên 2% dẫn đến `HOLD`. Một mục `scene_leak` tính cho một ảnh.
- Kết quả `lineage.py impact` cho `R-021`: <<điền sau khi ghi quyết định>>. `R-021` đã train bằng v1. Nếu v1 bị giữ lại do lỗi, cần xem lại kết quả của run hoặc train lại với dữ liệu đã xử lý vì bàn giao v2 không làm thay đổi trọng số của model đã train.

## 4. Hash chứng minh gì, không chứng minh gì?
SHA-256 giúp kiểm tra file nhận được có khớp từng byte với file đã lập manifest hay không. Độ đúng của lớp, box và nội dung ảnh cần được kiểm tra bằng quy tắc và review ảnh. Hai file cùng nội dung có thể cùng chứa một nhãn sai.

## 5. Truy vết
- `tier_a` gồm ảnh trong các cảnh được ticket nêu, thuộc job theo guideline cũ và có ít nhất một box detection thuộc lớp đổi quy tắc.
- `tier_b` gồm các ảnh ngoài các cảnh được nêu với cùng điều kiện về job và lớp detection. `notify` gồm mã người gán và người kiểm của các job chứa ảnh ở hai tầng.
- Dùng guideline trong `jobs.csv` vì phiên bản lưu theo ảnh có thể bị `guideline_mismatch`. Kết quả truy vết của nhóm: <<điền sau khi có `trace.json`>>.

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
- Trên máy Windows dùng CP1258, `py -X utf8 scripts/run_lab.py --seeds 4007` tạo xong lô v1 nhưng tiến trình con lỗi khi in tiếng Việt, trước khi `run_lab.py` ghi lineage. Nhóm xác nhận `release.json` đã có và dùng `lineage.py record` để ghi hai sự kiện `inject` và `train` cho lô hiện có.
