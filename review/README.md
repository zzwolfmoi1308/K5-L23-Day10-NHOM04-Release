# Xem ảnh và gộp kết quả review

Chạy từ thư mục gốc repo. Trình xem tạo HTML dùng offline và cần Pillow (`python -m pip install Pillow` nếu môi trường dùng để xem ảnh chưa có).

```powershell
python -X utf8 validator/validate.py runs/r4007/delivery --candidates runs/r4007/candidates.json
python -X utf8 review/review.py prepare runs/r4007/delivery --candidates runs/r4007/candidates.json --out runs/r4007/review_queue --reviewers TrungKien0905 hang-02 hang-03 hang-04 hang-05
```

Mở `runs/r4007/review_queue/index.html` rồi chọn hàng đợi. Có thể điền tên GitHub thực vào `--reviewers` khi tạo hàng đợi mới. Tất cả ứng viên trên cùng một ảnh được giao chung. HTML cho xem vùng ảnh gốc, vùng có box detection màu cam và viền segment màu xanh, cùng liên kết mở ảnh toàn cảnh.

Điền `confirmed` hoặc `rejected` trong CSV tương ứng. Ghi chú bắt đầu bằng `[GitHub]` rồi mô tả điều quan sát được bằng ít nhất 20 ký tự. Nếu hai loại đổi lớp có chung bằng chứng, xác nhận loại tương ứng với nguồn sai hoặc loại cả hai nếu đối chiếu ảnh cho thấy lệch tự nhiên.

```powershell
$logs = @(Get-ChildItem runs/r4007/review_queue/*.csv -Exclude assignments.csv | Select-Object -ExpandProperty FullName)
python -X utf8 review/review.py merge --candidates runs/r4007/candidates.json --out runs/r4007/review_log.csv @logs
python -X utf8 scripts/merge_review.py --rules runs/r4007/rules.json --review runs/r4007/review_log.csv --out runs/r4007/errors.json
```

`merge` kiểm tra các ứng viên, ghi chú và kết luận xung đột trước khi ghi CSV. Dùng `--allow-pending` để xuất bản tạm khi còn dòng chưa review. Dòng trống sẽ được bỏ qua. Lệnh cuối cần `rules.json` của Pha 1. Khi nộp, `scripts/export_submission.py --run runs/r4007` sẽ chép CSV đã chốt sang `submission/r4007` cùng các đầu ra khác của nhóm.

Khi làm đề ẩn, đổi đối số thư mục đầu vào thành `delivery`, ghi `candidates.json`, `review_log.csv` và `errors.json` vào `submission/de_an`, và tạo hàng đợi trong `runs/de_an/review_queue`.
