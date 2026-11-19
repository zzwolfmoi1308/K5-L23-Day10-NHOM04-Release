<p align="center">
  <img src="docs/assets/hero.png" alt="Day 10 Lab: Bàn giao dataset và Truy vết" width="100%">
</p>

# Day 10 Lab — Nhóm 04

<p align="center">
  <img alt="nhóm" src="https://img.shields.io/badge/lab-nhóm%205–6%20người-0b1f3a">
  <img alt="thời lượng" src="https://img.shields.io/badge/thời%20lượng-~4%20giờ-ff8a3d">
  <img alt="ảnh" src="https://img.shields.io/badge/dữ%20liệu-250%20ảnh%20COCO-12b3a8">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B%20(chỉ%20thư%20viện%20chuẩn)-3776ab">
  <img alt="gpu" src="https://img.shields.io/badge/GPU-không%20cần-2fbf71">
</p>

> **Không có đáp án để so.** Nhóm phải tự bắt lỗi, quyết định lô có được train không, bàn giao bản sửa mà không ghi đè bản cũ, và chỉ ra ai cần sửa khi team AI báo lỗi.

## Bạn sẽ làm gì

Nhóm nhận một lô 250 ảnh có cả nhãn **detection** và **panoptic**, cùng giấy tờ đi kèm (người gán, người kiểm, guideline, ticket của team AI). Trong lô có lỗi được gài theo seed. **Số lỗi mỗi loại thay đổi theo seed** và lô **không kèm nhãn gốc**.

| Việc | Công cụ |
|---|---|
| Bắt lỗi luật (file, hash, class, box, split, guideline) | **`validator/` do nhóm tự viết** |
| Đối chiếu detection ↔ panoptic, mở ảnh xem từng ứng viên | validator + `review_log.csv` |
| Quyết định Release / Hold theo ngưỡng 2%, ghi lineage | `lineage.py` |
| Bàn giao lô v2: manifest + sha256, label summary, truy vết, rework | `pack_release.py`, `check_handover.py` |
| Truy vết ticket: ảnh nào, tầng nào, báo ai | `trace.json` |
| Đo chính mình | `score_findings.py` (F1: báo thừa bị trừ như bỏ sót) |

![Hai loại lỗi](docs/assets/two_kinds.png)

## Lộ trình

![Lộ trình 6 pha](docs/assets/roadmap.png)

```mermaid
flowchart LR
  A[P1 Bắt lỗi luật<br/>validator tự viết] --> B[P2 Đối chiếu<br/>det ↔ panoptic + xem ảnh]
  B --> C[P3 Quyết định<br/>ngưỡng 2%, lineage]
  C --> D[P4 Bàn giao v2<br/>không ghi đè v1]
  D --> E[P5 Truy vết ticket<br/>tầng a/b, báo ai]
  E --> F[P6 Bảo mật<br/>+ đề ẩn 40 phút]
  style A fill:#2fbf71,color:#fff
  style B fill:#7b61ff,color:#fff
  style C fill:#ff8a3d,color:#fff
  style D fill:#e5484d,color:#fff
  style E fill:#12b3a8,color:#fff
  style F fill:#0b1f3a,color:#fff
```

## Bộ dữ liệu: 250 ảnh COCO, hai loại nhãn, một câu chuyện bàn giao

- **250 ảnh COCO val2017.** Mỗi ảnh có nhãn detection (YOLO, 80 lớp) và mask panoptic. Mọi máy tải ra cùng 250 ảnh.
- **Giấy tờ giả lập:** cảnh (5 ảnh/cảnh), job (25 ảnh/job) kèm người gán, người kiểm và phiên bản guideline (v1.2 rồi v1.3), changelog, và ticket của team AI.
- **Đề ẩn cuối buổi:** dùng **250 ảnh khác**, tên ảnh đã mã hoá, file đã ghi lại. Validator nào dựa vào nhãn gốc sẽ không có gì để so.

![Bàn giao v2 và lineage](docs/assets/handover.png)

## Bắt đầu nhanh (5 bước)

1. Tạo repo nhóm từ repo này (tên: xem [SUBMISSION.md](SUBMISSION.md)), `git clone`. Kiểm Python: `python3 --version` (Windows: `py --version`) cần 3.10+. **Không cần `pip install`.**
2. Tải dữ liệu (một lần, khoảng 1 GB): `python scripts/download_public.py`
3. Tạo lô luyện tập cho nhóm: `python scripts/run_lab.py --seeds <seed của nhóm>`
4. Làm theo **[GUIDE.md](GUIDE.md)** từ **P1**. Đọc trước định dạng lô ở [docs/DELIVERY.md](docs/DELIVERY.md).
5. Trước khi nộp: `python scripts/check_handover.py --run runs/r<seed>` không còn FAIL.

> **Khi nộp:** làm theo checklist trong [SUBMISSION.md](SUBMISSION.md).

<details>
<summary><b>Vì sao không có nhãn gốc để so?</b></summary>

Ngoài đời, người kiểm chỉ có ảnh và nhãn được giao. Nếu có sẵn nhãn đúng thì đã không cần QC. Ở bản trước của lab, một script diff khoảng 40 dòng với nhãn gốc đạt điểm tối đa trên mọi seed. Bản này bỏ lối đó:
- Lỗi gán nhãn chỉ thấy khi **đối chiếu hai nguồn** (detection và panoptic của cùng ảnh).
- Sau đó phải **mở ảnh ra xem** để biết bên nào sai.
</details>

<details>
<summary><b>Báo hết ứng viên cho chắc có được không?</b></summary>

Không có lợi. Điểm là **F1**, nên báo thừa bị trừ như bỏ sót. Detection và panoptic của COCO vốn lệch nhau tự nhiên (vật bị che, crowd), nên với cách ghép thô, nhiều ứng viên **không phải lỗi**. Khi giảng viên thử bằng một validator ghép thô:

| Cách làm | F1 |
|---|---|
| Chỉ kiểm luật | khoảng 0,7 |
| Báo hết ứng viên mà không xem ảnh | khoảng 0,6 |
| Đối chiếu đúng cộng xem ảnh cẩn thận | trên 0,9 |
</details>

<details>
<summary><b>PASS của <code>check_handover.py</code> có nghĩa là nhãn đúng không?</b></summary>

Không. PASS chỉ nói lô v2 **đúng định dạng và nhất quán**: hash, số liệu, truy vết, ngưỡng, lineage. Nhãn đúng hay sai vẫn là việc của người xem ảnh.
</details>

<details>
<summary><b>Mình dùng Windows / Mac thì sao?</b></summary>

- **Windows (PowerShell):** gọi `py`, chạy từng lệnh riêng (không `&&`), thêm `-X utf8` nếu lỗi font.
- **macOS:** dùng `python3`. Script tự bỏ qua `.DS_Store`.
- **Mở ảnh để review:** dùng trình xem ảnh bất kỳ. Nếu muốn vẽ box lên ảnh thì tự viết thêm (Pillow là tuỳ chọn, không bắt buộc).
</details>

## Tài liệu

| Bạn cần | Xem |
|---|---|
| Các pha và lệnh chạy | [GUIDE.md](GUIDE.md) |
| Mốc tiến độ 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Quy tắc làm bài, dùng AI | [RULES.md](RULES.md) |
| Chấm điểm (100 điểm) | [RUBRIC.md](RUBRIC.md) |
| Sản phẩm phải nộp, tên repo | [SUBMISSION.md](SUBMISSION.md) |
| Định dạng lô, các loại lỗi, format `errors.json` | [docs/DELIVERY.md](docs/DELIVERY.md) |
| Các script | [scripts/README.md](scripts/README.md) |
| Mẫu file phải điền | [templates/](templates/) |

## Bạn học được gì

- **Hai loại lỗi:** lỗi luật thì máy bắt được; lỗi gán nhãn thì cần **đối chiếu nguồn** và **mắt người**. Một F1 tổng cao có thể che việc bỏ sót loại thứ hai.
- **Đánh đổi precision/recall** khi không có đáp án: báo thừa cũng có giá.
- **Quyết định phát hành theo ngưỡng** (Day 7: trên 2% ảnh lỗi thì không Release) và ghi lại quyết định bằng **lineage**.
- **Bàn giao không ghi đè:** lô v2 có lô cha, có manifest + sha256, có hàng đợi gán lại giao đúng người.
- **Truy vết:** từ một ticket, khoanh vùng hai tầng ảnh cần mở lại và biết phải báo ai.
- **Hậu quả của lỗi đã train:** đổi dataset không tự sửa model đã học; phải xem lại hoặc train lại run bị ảnh hưởng.

<sub>Sơ đồ do giảng viên vẽ (`docs/assets/make_figures.py`). Ảnh dữ liệu: COCO val2017, xem [COCO terms of use](https://cocodataset.org/dataset/termsofuse.htm); annotation CC BY 4.0.</sub>
