"""Module kiểm tra 7 lỗi luật File, YOLO và Metadata cho Day 10 Lab.
Phụ trách: Nguyễn Tuấn Điệp (MSHV: 2A202603057)

Chức năng:
1. missing_image: manifest.json có khai báo ảnh nhưng thiếu file ảnh trong images/.
2. wrong_hash: mã SHA-256 tính từ bytes thật của file không khớp manifest.json.
3. invalid_class: class_id trong file nhãn YOLO nằm ngoài danh sách lớp hợp lệ (classes.txt, 0..79).
4. bbox_out_of_bounds: khung chữ nhật YOLO có kích thước <= 0 hoặc tràn ra ngoài [0, 1].
5. duplicate_box: hai box cùng class_id trong cùng ảnh có kích thước gần như giống hệt và tâm lệch rất nhỏ.
6. scene_leak: một scene_id có ảnh nằm ở cả train và val (target là scene_id).
7. guideline_mismatch: guideline_version trong metadata.json khác guideline của job trong jobs.csv.

Chỉ dùng thư viện chuẩn của Python.
Chỉ đọc thư mục delivery được truyền vào. Không đọc _private/, data_source/, không dùng mạng.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

if __package__:
    from .delivery import delivery_path as resolve_delivery_path
else:
    from delivery import delivery_path as resolve_delivery_path

# Tập 7 loại lỗi luật File, YOLO và Metadata thuộc phạm vi module này
DETECTION_RULE_TYPES: frozenset[str] = frozenset({
    "missing_image",
    "wrong_hash",
    "invalid_class",
    "bbox_out_of_bounds",
    "duplicate_box",
    "scene_leak",
    "guideline_mismatch",
})

# Ngưỡng sai số cho bbox_out_of_bounds để tránh báo nhầm do làm tròn số thực (.6f) ở mép [0, 1]
BBOX_OOB_EPS = 1e-6

# Ngưỡng cho duplicate_box theo 2 chế độ:
# IoU cao cho phép tâm lệch thêm một vài pixel, với cùng điều kiện kích thước.
DUP_HIGH_IOU = 0.80
DUP_HIGH_IOU_CENTER_PX_TOL = 5.01
DUP_SAME_SIZE_REL_TOL = 0.015
DUP_SAME_SIZE_PX_TOL = 1.0
DUP_CENTER_PX_TOL = 3.0
DUP_TINY_BOX_PX = 4.0
DUP_TINY_CENTER_PX_TOL = 2.5
# Dự phòng theo tọa độ chuẩn hóa khi thiếu kích thước ảnh trong panoptic.json
DUP_NORM_SIZE_REL_TOL = 0.005
DUP_NORM_CENTER_TOL = 0.005


def sha256_file(path: Path) -> str:
    """Tính mã SHA-256 trên nội dung nhị phân (bytes, chế độ 'rb') thật của file."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def load_valid_classes(delivery_path: Path) -> set[int]:
    """Đọc tập class_id hợp lệ từ classes.txt (mặc định 0..79 nếu thiếu file)."""
    classes_path = resolve_delivery_path(delivery_path, "classes.txt")
    if not classes_path.is_file():
        return set(range(80))

    valid_ids: set[int] = set()
    for line in classes_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        first_token = line.split(maxsplit=1)[0]
        try:
            valid_ids.add(int(first_token))
        except ValueError:
            continue
    return valid_ids if valid_ids else set(range(80))


def load_jobs(delivery_path: Path) -> dict[str, dict[str, str]]:
    """Đọc bảng jobs.csv thành ánh xạ job_id -> thông tin job."""
    jobs_path = resolve_delivery_path(delivery_path, "jobs.csv")
    if not jobs_path.is_file():
        return {}
    jobs: dict[str, dict[str, str]] = {}
    with jobs_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cleaned = {
                k.strip(): (v.strip() if isinstance(v, str) else "")
                for k, v in row.items()
                if k is not None
            }
            job_id = cleaned.get("job_id", "")
            if job_id:
                jobs[job_id] = cleaned
    return jobs


def load_image_sizes(delivery_path: Path) -> dict[str, tuple[int, int]]:
    """Đọc kích thước (width, height) từng ảnh từ panoptic.json (không cần Pillow)."""
    panoptic_path = resolve_delivery_path(delivery_path, "panoptic.json")
    if not panoptic_path.is_file():
        return {}
    data = json.loads(panoptic_path.read_text(encoding="utf-8-sig"))
    sizes: dict[str, tuple[int, int]] = {}
    for img in data.get("images", []):
        file_name = img.get("file_name")
        width = img.get("width")
        height = img.get("height")
        if file_name and isinstance(width, (int, float)) and isinstance(height, (int, float)):
            if width > 0 and height > 0:
                sizes[Path(file_name).stem] = (int(width), int(height))
    return sizes


def compute_iou_xywh(
    x1: float, y1: float, w1: float, h1: float,
    x2: float, y2: float, w2: float, h2: float,
) -> float:
    """Tính IoU giữa 2 bounding box dạng (x_center, y_center, width, height)."""
    ax1, ay1 = x1 - w1 / 2.0, y1 - h1 / 2.0
    ax2, ay2 = x1 + w1 / 2.0, y1 + h1 / 2.0
    bx1, by1 = x2 - w2 / 2.0, y2 - h2 / 2.0
    bx2, by2 = x2 + w2 / 2.0, y2 + h2 / 2.0

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, w1) * max(0.0, h1)
    area_b = max(0.0, w2) * max(0.0, h2)
    union = area_a + area_b - inter
    return inter / union if union > 0.0 else 0.0


def check_missing_and_hash(
    delivery_path: Path,
    manifest_items: dict[str, dict],
) -> list[dict[str, str]]:
    """Luật 1 & 2: kiểm tra missing_image và wrong_hash."""
    findings: list[dict[str, str]] = []
    for name, item in manifest_items.items():
        img_rel = item.get("image")
        img_path = resolve_delivery_path(delivery_path, img_rel) if img_rel else None

        # Luật 1: missing_image
        if img_path is None or not img_path.is_file():
            findings.append({"type": "missing_image", "target": name})
            continue

        # Luật 2: wrong_hash (tính lại SHA-256 trên bytes thật cho image, label, mask nếu có)
        hash_mismatch = False
        for file_key, hash_key in (
            ("image", "image_sha256"),
            ("label", "label_sha256"),
            ("mask", "mask_sha256"),
        ):
            rel = item.get(file_key)
            if not rel or hash_key not in item:
                continue
            target_path = img_path if file_key == "image" else resolve_delivery_path(delivery_path, rel)
            if not target_path.is_file():
                continue
            expected = str(item.get(hash_key) or "").strip().lower()
            if sha256_file(target_path) != expected:
                hash_mismatch = True
                break

        if hash_mismatch:
            findings.append({"type": "wrong_hash", "target": name})

    return findings


def check_metadata_rules(
    metadata_items: list[dict],
    jobs: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """Luật 6 & 7: kiểm tra scene_leak (target là scene_id) và guideline_mismatch."""
    findings: list[dict[str, str]] = []
    scene_splits: dict[str, set[str]] = {}

    for meta in metadata_items:
        img_name = str(meta.get("image") or "").strip()
        scene_id = str(meta.get("scene_id") or "").strip()
        split = str(meta.get("split") or "").strip().lower()
        job_id = str(meta.get("job_id") or "").strip()
        img_guideline = str(meta.get("guideline_version") or "").strip()

        if scene_id and split:
            scene_splits.setdefault(scene_id, set()).add(split)

        # Luật 7: guideline_mismatch (so với guideline khai báo ở job trong jobs.csv)
        if img_name and job_id and job_id in jobs:
            job_guideline = jobs[job_id].get("guideline", "").strip()
            if img_guideline != job_guideline:
                findings.append({"type": "guideline_mismatch", "target": img_name})

    # Luật 6: scene_leak (một scene xuất hiện ở nhiều hơn 1 split, ví dụ cả train và val)
    for scene_id, splits in scene_splits.items():
        if len(splits) > 1:
            findings.append({"type": "scene_leak", "target": scene_id})

    return findings


def is_duplicate_pair(
    box_a: tuple[int, float, float, float, float],
    box_b: tuple[int, float, float, float, float],
    img_size: tuple[int, int] | None,
) -> bool:
    """Kiểm tra 2 box (cùng class_id) có phải là box bị lặp không.

    Với kích thước ảnh, hai box phải gần như cùng kích thước (<= 1.5% và <= 1 px).
    Cặp có IoU cao được phép lệch tâm đến khoảng 5 px. Cặp box rất nhỏ có thể
    chỉ chạm cạnh khi tâm dịch 2 px, nên dùng khoảng cách tâm cho trường hợp đó.
    """
    ca, xa, ya, wa, ha = box_a
    cb, xb, yb, wb, hb = box_b
    if ca != cb:
        return False

    iou = compute_iou_xywh(xa, ya, wa, ha, xb, yb, wb, hb)
    max_w = max(wa, wb, 1e-9)
    max_h = max(ha, hb, 1e-9)
    rel_dw = abs(wa - wb) / max_w
    rel_dh = abs(ha - hb) / max_h

    if img_size is not None:
        img_w, img_h = img_size
        dx_px = abs(xa - xb) * img_w
        dy_px = abs(ya - yb) * img_h
        dw_px = abs(wa - wb) * img_w
        dh_px = abs(ha - hb) * img_h

        same_size = (
            rel_dw <= DUP_SAME_SIZE_REL_TOL
            and rel_dh <= DUP_SAME_SIZE_REL_TOL
            and dw_px <= DUP_SAME_SIZE_PX_TOL
            and dh_px <= DUP_SAME_SIZE_PX_TOL
        )
        if not same_size:
            return False
        center_shift = max(dx_px, dy_px)
        if iou >= DUP_HIGH_IOU and center_shift <= DUP_HIGH_IOU_CENTER_PX_TOL:
            return True
        if iou > 0.0 and center_shift <= DUP_CENTER_PX_TOL:
            return True
        min_side_px = min(wa * img_w, ha * img_h, wb * img_w, hb * img_h)
        return min_side_px <= DUP_TINY_BOX_PX and center_shift <= DUP_TINY_CENTER_PX_TOL

    # Dự phòng khi không có kích thước ảnh trong panoptic.json
    if (
        iou > 0.0
        and rel_dw <= DUP_NORM_SIZE_REL_TOL
        and rel_dh <= DUP_NORM_SIZE_REL_TOL
        and abs(xa - xb) <= DUP_NORM_CENTER_TOL
        and abs(ya - yb) <= DUP_NORM_CENTER_TOL
    ):
        return True

    return False


def check_yolo_labels(
    delivery_path: Path,
    manifest_items: dict[str, dict],
    valid_class_ids: set[int],
    image_sizes: dict[str, tuple[int, int]],
    oob_eps: float = BBOX_OOB_EPS,
) -> list[dict[str, str]]:
    """Luật 3, 4 & 5: kiểm tra invalid_class, bbox_out_of_bounds và duplicate_box."""
    findings: list[dict[str, str]] = []

    for name, item in manifest_items.items():
        label_rel = item.get("label")
        if not label_rel:
            continue
        label_path = resolve_delivery_path(delivery_path, label_rel)
        if not label_path.is_file():
            continue

        has_invalid_class = False
        has_oob = False
        boxes: list[tuple[int, float, float, float, float]] = []

        for raw_line in label_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                has_invalid_class = True
                continue

            # Luật 3: invalid_class
            try:
                c_val = float(parts[0])
                if not math.isfinite(c_val) or not c_val.is_integer():
                    has_invalid_class = True
                    continue
                cls_id = int(c_val)
            except ValueError:
                has_invalid_class = True
                continue

            if cls_id not in valid_class_ids:
                has_invalid_class = True

            # Luật 4: bbox_out_of_bounds
            try:
                x, y, w, h = (float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]))
            except ValueError:
                has_oob = True
                continue

            if not all(math.isfinite(v) for v in (x, y, w, h)) or w <= 0.0 or h <= 0.0:
                has_oob = True
                continue

            x1, y1 = x - w / 2.0, y - h / 2.0
            x2, y2 = x + w / 2.0, y + h / 2.0
            if x1 < -oob_eps or y1 < -oob_eps or x2 > 1.0 + oob_eps or y2 > 1.0 + oob_eps:
                has_oob = True
                continue

            if cls_id in valid_class_ids:
                boxes.append((cls_id, x, y, w, h))

        if has_invalid_class:
            findings.append({"type": "invalid_class", "target": name})
        if has_oob:
            findings.append({"type": "bbox_out_of_bounds", "target": name})

        # Luật 5: duplicate_box
        img_size = image_sizes.get(name)
        has_dup = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if is_duplicate_pair(boxes[i], boxes[j], img_size):
                    has_dup = True
                    break
            if has_dup:
                break

        if has_dup:
            findings.append({"type": "duplicate_box", "target": name})

    return findings


def check_detection_rules(delivery_dir: Path | str) -> list[dict[str, str]]:
    """Quét thư mục delivery và trả về danh sách 7 lỗi luật File, YOLO và Metadata.

    Định dạng trả về: [{"type": "<loại_lỗi>", "target": "<target>"}, ...] đã loại trùng và sắp xếp.
    """
    delivery_path = Path(delivery_dir)
    manifest_path = resolve_delivery_path(delivery_path, "manifest.json")
    metadata_path = resolve_delivery_path(delivery_path, "metadata.json")

    manifest_items: dict[str, dict] = {}
    if manifest_path.is_file():
        manifest_items = json.loads(manifest_path.read_text(encoding="utf-8-sig")).get("items", {})

    metadata_items: list[dict] = []
    if metadata_path.is_file():
        metadata_items = json.loads(metadata_path.read_text(encoding="utf-8-sig")).get("items", [])

    jobs = load_jobs(delivery_path)
    valid_class_ids = load_valid_classes(delivery_path)
    image_sizes = load_image_sizes(delivery_path)

    raw_findings: list[dict[str, str]] = []
    raw_findings.extend(check_missing_and_hash(delivery_path, manifest_items))
    raw_findings.extend(check_metadata_rules(metadata_items, jobs))
    raw_findings.extend(check_yolo_labels(delivery_path, manifest_items, valid_class_ids, image_sizes))

    # Loại bỏ trùng cặp (type, target) và sắp xếp ổn định
    unique_pairs = sorted({(f["type"], f["target"]) for f in raw_findings})
    return [{"type": err_type, "target": target} for err_type, target in unique_pairs]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Kiểm tra 7 lỗi luật File, YOLO và Metadata (Điệp phụ trách)"
    )
    parser.add_argument("delivery", help="Đường dẫn tới thư mục delivery")
    parser.add_argument("--out", help="Tùy chọn: ghi kết quả ra file JSON chuẩn errors.json")
    args = parser.parse_args()

    delivery_path = Path(args.delivery)
    if not delivery_path.is_dir():
        print(f"Lỗi: Thư mục không tồn tại: {delivery_path}", file=sys.stderr)
        return 1

    out_path = Path(args.out) if args.out else None
    if out_path is not None and out_path.resolve().is_relative_to(delivery_path.resolve()):
        parser.error("File đầu ra phải nằm ngoài delivery.")
    try:
        findings = check_detection_rules(delivery_path)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Không kiểm tra được lô: {exc}\n")
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps({"errors": findings}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"Kết quả kiểm tra 7 luật File/YOLO/Metadata ({delivery_path}): {len(findings)} lỗi tìm thấy.")
    for item in findings:
        print(f" - [{item['type']}] target: {item['target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
