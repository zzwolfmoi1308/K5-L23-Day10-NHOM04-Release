"""Module kiểm tra 2 lỗi luật Panoptic cho Day 10 Lab.
Phụ trách: Ngô Xuân Tùng (MSHV: 2A202603225)

Chức năng:
1. invalid_category_id: category_id trong segments_info không tồn tại trong categories.
2. thing_overlap: area khai báo trong segments_info nhiều hơn số pixel thực tế trong mask (bị vật khác đè lên).

Chỉ dùng thư viện chuẩn của Python và scripts/pngutil.py.
Chỉ đọc thư mục delivery được truyền vào.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Nạp pngutil từ scripts/ (thư viện chuẩn)
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import pngutil  # noqa: E402


def check_panoptic_rules(delivery_dir: Path | str) -> list[dict]:
    """Quét thư mục delivery và trả về danh sách các lỗi panoptic luật:

    [{"type": "invalid_category_id", "target": "<image_name>"}, ...]
    """
    delivery_path = Path(delivery_dir)
    panoptic_path = delivery_path / "panoptic.json"
    masks_dir = delivery_path / "masks"

    if not panoptic_path.is_file():
        return []

    with open(panoptic_path, "r", encoding="utf-8") as f:
        panoptic_data = json.load(f)

    categories = panoptic_data.get("categories", [])
    valid_cat_ids = {cat["id"] for cat in categories}
    thing_cat_ids = {cat["id"] for cat in categories if cat.get("isthing") == 1}

    # Ánh xạ image_id sang tên file gốc (bỏ phần mở rộng)
    images_info = panoptic_data.get("images", [])
    id_to_stem = {}
    for img in images_info:
        id_to_stem[img["id"]] = Path(img["file_name"]).stem

    errors = []

    for ann in panoptic_data.get("annotations", []):
        img_id = ann["image_id"]
        # Lấy tên định danh ảnh (target) không kèm đuôi mở rộng
        if img_id in id_to_stem:
            target = id_to_stem[img_id]
        elif "file_name" in ann:
            target = Path(ann["file_name"]).stem
        else:
            target = f"{img_id:012d}"

        segments = ann.get("segments_info", [])
        if not segments:
            continue

        # --- LUẬT 1: invalid_category_id ---
        has_invalid_cat = False
        for seg in segments:
            cat_id = seg.get("category_id")
            if cat_id not in valid_cat_ids:
                has_invalid_cat = True
                break

        if has_invalid_cat:
            errors.append({"type": "invalid_category_id", "target": target})

        # --- LUẬT 2: thing_overlap ---
        # Chỉ kiểm tra thing_overlap nếu có các segment thuộc dạng "thing" và không phải crowd
        thing_segments = [s for s in segments if s.get("category_id") in thing_cat_ids and not s.get("iscrowd")]
        if not thing_segments:
            continue

        mask_file_name = ann.get("file_name", f"{img_id:012d}.png")
        mask_path = masks_dir / mask_file_name
        if not mask_path.is_file():
            continue

        width, height, pixels = pngutil.read_rgb(mask_path)

        # Đếm tần số xuất hiện của từng segment ID trong mask
        counts: dict[int, int] = {}
        for i in range(0, len(pixels), 3):
            sid = pixels[i] | (pixels[i + 1] << 8) | (pixels[i + 2] << 16)
            if sid != 0:
                counts[sid] = counts.get(sid, 0) + 1

        has_overlap = False
        for seg in thing_segments:
            declared_area = seg.get("area", 0)
            actual_count = counts.get(seg["id"], 0)
            # Nếu diện tích thực tế trên mask nhỏ hơn diện tích khai báo -> bị đè lên
            if actual_count < declared_area:
                has_overlap = True
                break

        if has_overlap:
            errors.append({"type": "thing_overlap", "target": target})

    return errors


def check_rules(delivery: Path) -> list[dict]:
    """Entry point used by the group validator."""
    return check_panoptic_rules(delivery)


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiểm tra 2 lỗi luật Panoptic (Tùng phụ trách)")
    parser.add_argument("delivery", help="Đường dẫn tới thư mục delivery")
    args = parser.parse_args()

    delivery_path = Path(args.delivery)
    if not delivery_path.is_dir():
        print(f"Lỗi: Thư mục không tồn tại: {delivery_path}", file=sys.stderr)
        return 1

    findings = check_panoptic_rules(delivery_path)
    print(f"Kết quả kiểm tra Panoptic ({delivery_path}): {len(findings)} lỗi tìm thấy.")
    for item in findings:
        print(f" - [{item['type']}] ảnh: {item['target']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
