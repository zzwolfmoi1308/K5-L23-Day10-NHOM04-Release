# Báo cáo nhóm 04

## 1. Số liệu luyện tập
- Kết quả Pha 1 của bảy luật file, YOLO và metadata khớp từng cặp `(type, target)` với phần tương ứng trong `errors.json` đã dùng để tự đo. Lô sạch 50 ảnh báo **0 lỗi luật**. F1 gán nhãn và F1 tổng của bài nộp chờ kết quả review bằng mắt.
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
Nếu đưa cả 9 dòng ứng viên của seed 4007 vào lỗi cuối, riêng 3 ảnh bất đồng về lớp đã tạo ít nhất 3 báo thừa vì mỗi ảnh có tối đa một lỗi. Báo thừa làm giảm precision và kéo F1 xuống nếu recall giữ nguyên. Review giữ dòng đúng theo ảnh và giúp loại các lệch tự nhiên giữa hai nguồn nhãn.

## 3. Quyết định và lineage
<<QC v1 a/b, kết luận, vì sao R-021 phải xem lại hoặc train lại.>>

## 4. Hash chứng minh gì, không chứng minh gì?
<<>>

## 5. Truy vết
<<Tiêu chí tầng a/b, vì sao lấy guideline theo job.>>

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
<<>>
