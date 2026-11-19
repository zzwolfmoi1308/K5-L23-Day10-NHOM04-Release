# Validator của nhóm

Chạy từ thư mục gốc repo:

```
python validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]
```

Phần đối chiếu Pha 2 đã chạy độc lập bằng thư viện chuẩn:

```powershell
python -X utf8 validator/validate.py runs/r4007/delivery --candidates runs/r4007/candidates.json
```

`candidates.json` có khóa `candidates`. Mỗi phần tử có `type`, `target` là tên ảnh và `evidence` có dòng nhãn YOLO, tọa độ pixel, ID segment và số đo dùng để đưa vào hàng đợi. Hai khả năng đổi lớp trên cùng ảnh dùng chung bằng chứng.

`--out` chạy 7 luật trong `detection_rules.py` và 2 luật trong `panoptic_rules.py`, rồi ghi các cặp `type,target` vào khóa `errors`. `--candidates` chạy `cross_check.py` và có thể dùng riêng hoặc cùng `--out`. Đặt đầu ra ngoài thư mục `delivery`.

```powershell
py -X utf8 validator/validate.py runs/r4007/delivery --out runs/r4007/rules.json --candidates runs/r4007/candidates.json
py -X utf8 scripts/merge_review.py --rules runs/r4007/rules.json --review runs/r4007/review_log.csv --out runs/r4007/errors.json
```

Validator dùng thư viện chuẩn và chỉ đọc dữ liệu trong thư mục delivery được truyền vào. Xem [GUIDE.md](../GUIDE.md) Pha 1–2 và [RULES.md](../RULES.md).
