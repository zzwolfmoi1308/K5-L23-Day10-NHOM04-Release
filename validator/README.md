# Validator của nhóm

Viết `validate.py` ở đây. Giao diện cố định:

```
python validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]
```

Phần đối chiếu Pha 2 đã chạy độc lập bằng thư viện chuẩn:

```powershell
python -X utf8 validator/validate.py runs/r4007/delivery --candidates runs/r4007/candidates.json
```

`candidates.json` có khóa `candidates`. Mỗi phần tử có `type`, `target` là tên ảnh và `evidence` có dòng nhãn YOLO, tọa độ pixel, ID segment và số đo dùng để đưa vào hàng đợi. Hai khả năng đổi lớp trên cùng ảnh dùng chung bằng chứng.

Để chạy cả `--out`, phần Pha 1 cung cấp `validator/rules.py` với hàm `find_rule_errors(delivery: Path)` trả về danh sách mục `type,target`. Xem [GUIDE.md](../GUIDE.md) Pha 1–2 và [RULES.md](../RULES.md).
