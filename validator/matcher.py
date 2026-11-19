"""Module đọc mask Panoptic và ghép nối Box YOLO ↔ Segment Panoptic cho Pha 2.
Phụ trách: Ngô Xuân Tùng (MSHV: 2A202603225)
Chuyển giao cho: Hồ Trung Kiên (Thành viên 4) để sinh candidates.json

Chức năng:
1. Đổi box YOLO (chuẩn hóa 0-1) sang pixel [x1, y1, x2, y2].
2. Ánh xạ tên lớp đồng nhất: classes.txt (YOLO) ↔ categories (Panoptic).
3. Tính IoU hình học giữa Bbox YOLO và Bbox Segment.
4. Đọc mask PNG và tính tỷ lệ phủ pixel (Pixel Coverage):
   Bao nhiêu % pixel của mask nằm lọt bên trong box YOLO.
5. Cung cấp tín hiệu nhận diện 5 lỗi gán nhãn:
   - class_swap / category_swap (trùng vị trí, khác lớp)
   - bbox_drift (cùng lớp, nhưng box lệch khỏi mask: coverage thấp)
   - missing_box (segment thing lớn nhưng không có box YOLO nào)
   - instance_merge (1 segment mask phủ lên 2 box YOLO cùng lớp)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Nạp pngutil từ scripts/ (thư viện chuẩn)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_SCRIPTS_DIR = _ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    from scripts import pngutil
except ImportError:
    import pngutil  # type: ignore


# ---------------------------------------------------------
# 1. TẢI VÀ CHUẨN HÓA DỮ LIỆU
# ---------------------------------------------------------

def load_yolo_classes(classes_file: Path | str) -> dict[int, str]:
    """Đọc classes.txt -> {class_id: class_name}."""
    mapping = {}
    path = Path(classes_file)
    if not path.is_file():
        return mapping
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            mapping[int(parts[0])] = parts[1].strip()
    return mapping


def load_panoptic_categories(panoptic_data: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Đọc categories từ panoptic.json -> {cat_id: {'name': ..., 'isthing': ...}}."""
    categories = {}
    for cat in panoptic_data.get("categories", []):
        categories[cat["id"]] = {
            "name": cat["name"],
            "isthing": cat.get("isthing", 0),
        }
    return categories


def parse_yolo_labels(
    label_path: Path | str,
    img_width: int,
    img_height: int,
    class_map: dict[int, str],
) -> list[dict[str, Any]]:
    """Đọc file YOLO label .txt và đổi tọa độ sang pixel [x1, y1, x2, y2]."""
    path = Path(label_path)
    boxes = []
    if not path.is_file():
        return boxes

    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        cid = int(parts[0])
        xc, yc, w, h = map(float, parts[1:5])

        # Đổi tọa độ tâm chuẩn hóa sang pixel góc trên-trái, góc dưới-phải
        bw = w * img_width
        bh = h * img_height
        x1 = max(0.0, (xc * img_width) - (bw / 2.0))
        y1 = max(0.0, (yc * img_height) - (bh / 2.0))
        x2 = min(float(img_width), x1 + bw)
        y2 = min(float(img_height), y1 + bh)

        boxes.append({
            "box_idx": idx,
            "class_id": cid,
            "class_name": class_map.get(cid, f"class_{cid}"),
            "bbox_norm": [xc, yc, w, h],
            "bbox_px": [x1, y1, x2, y2],
            "area_px": (x2 - x1) * (y2 - y1),
        })
    return boxes


# ---------------------------------------------------------
# 2. CÁC HÀM TÍNH TOÁN HÌNH HỌC VÀ PIXEL
# ---------------------------------------------------------

def bbox_iou(box1: list[float], box2: list[float]) -> float:
    """Tính Intersection over Union (IoU) giữa 2 box dạng [x1, y1, x2, y2]."""
    xA = max(box1[0], box2[0])
    yA = max(box1[1], box2[1])
    xB = min(box1[2], box2[2])
    yB = min(box1[3], box2[3])

    inter_w = max(0.0, xB - xA)
    inter_h = max(0.0, yB - yA)
    inter_area = inter_w * inter_h

    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])
    union_area = area1 + area2 - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def compute_mask_pixel_coverage(
    mask_pixels: bytearray | bytes,
    width: int,
    height: int,
    seg_id: int,
    yolo_box_px: list[float],
) -> tuple[int, int, float]:
    """Tính độ phủ pixel của một segment bên trong box YOLO:

    Trả về: (số pixel segment nằm TRONG box, tổng số pixel segment, tỷ lệ coverage)
    """
    x1 = max(0, int(round(yolo_box_px[0])))
    y1 = max(0, int(round(yolo_box_px[1])))
    x2 = min(width, int(round(yolo_box_px[2])))
    y2 = min(height, int(round(yolo_box_px[3])))

    # 1. Đếm số pixel của segment nằm trong phạm vi hình chữ nhật của box
    inside_count = 0
    stride = width * 3
    for y in range(y1, y2):
        row_offset = y * stride
        for x in range(x1, x2):
            idx = row_offset + x * 3
            sid = mask_pixels[idx] | (mask_pixels[idx + 1] << 8) | (mask_pixels[idx + 2] << 16)
            if sid == seg_id:
                inside_count += 1

    return inside_count


# ---------------------------------------------------------
# 3. HÀM ĐỐI CHIẾU CHÍNH CHO TỪNG ẢNH (BÀN GIAO CHO KIÊN)
# ---------------------------------------------------------

def analyze_image_correspondence(
    delivery_dir: Path | str,
    image_name: str,
    panoptic_data: dict[str, Any] | None = None,
    classes_map: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Phân tích đối chiếu giữa Detection và Panoptic của một ảnh.

    Trả về bảng thông tin chi tiết các cặp ghép, độ phủ pixel, và các dấu hiệu bất thường.
    """
    delivery_path = Path(delivery_dir)
    target = Path(image_name).stem

    # Nạp classes nếu chưa có
    if classes_map is None:
        classes_map = load_yolo_classes(delivery_path / "classes.txt")

    # Nạp panoptic.json nếu chưa có
    if panoptic_data is None:
        with open(delivery_path / "panoptic.json", "r", encoding="utf-8") as f:
            panoptic_data = json.load(f)

    cat_map = load_panoptic_categories(panoptic_data)

    # Tìm thông tin ảnh và annotation
    img_info = None
    for img in panoptic_data.get("images", []):
        if Path(img["file_name"]).stem == target:
            img_info = img
            break

    if not img_info:
        return {"target": target, "error": "Image not found in panoptic.json"}

    img_w = img_info["width"]
    img_h = img_info["height"]
    img_id = img_info["id"]

    ann_info = None
    for ann in panoptic_data.get("annotations", []):
        if ann["image_id"] == img_id or Path(ann.get("file_name", "")).stem == target:
            ann_info = ann
            break

    # Lấy danh sách YOLO boxes
    label_path = delivery_path / "labels" / f"{target}.txt"
    yolo_boxes = parse_yolo_labels(label_path, img_w, img_h, classes_map)

    # Lấy danh sách Panoptic segments (chỉ lấy things, bỏ crowd)
    panoptic_segments = []
    if ann_info:
        for seg in ann_info.get("segments_info", []):
            cid = seg.get("category_id")
            cinfo = cat_map.get(cid, {})
            # Chỉ xét đối tượng rời rạc (thing) và không phải crowd
            if cinfo.get("isthing") == 1 and not seg.get("iscrowd"):
                sbx, sby, sbw, sbh = seg["bbox"]
                panoptic_segments.append({
                    "seg_id": seg["id"],
                    "category_id": cid,
                    "class_name": cinfo.get("name", f"cat_{cid}"),
                    "bbox_px": [float(sbx), float(sby), float(sbx + sbw), float(sby + sbh)],
                    "area": seg.get("area", 0),
                })

    # Đọc mask PNG nếu có cả boxes và segments cần đối chiếu
    mask_pixels = None
    mask_path = delivery_path / "masks" / f"{target}.png"
    if mask_path.is_file() and (yolo_boxes or panoptic_segments):
        _, _, mask_pixels = pngutil.read_rgb(mask_path)

    # Đếm số pixel thực tế của từng segment trong mask để tính mẫu số chính xác
    seg_actual_counts: dict[int, int] = {}
    if mask_pixels:
        for i in range(0, len(mask_pixels), 3):
            sid = mask_pixels[i] | (mask_pixels[i + 1] << 8) | (mask_pixels[i + 2] << 16)
            if sid != 0:
                seg_actual_counts[sid] = seg_actual_counts.get(sid, 0) + 1

    # --- BẮT ĐẦU ĐỐI CHIẾU ---
    # Tính ma trận tương quan giữa từng Box YOLO và từng Segment Panoptic
    matrix = []
    for b in yolo_boxes:
        for s in panoptic_segments:
            iou = bbox_iou(b["bbox_px"], s["bbox_px"])
            coverage = 0.0
            inside_px = 0
            total_seg_px = seg_actual_counts.get(s["seg_id"], s["area"])

            # Nếu bbox có giao nhau đáng kể (IoU > 0.05) thì mới cần quét pixel mask
            if mask_pixels and iou > 0.02 and total_seg_px > 0:
                inside_px = compute_mask_pixel_coverage(mask_pixels, img_w, img_h, s["seg_id"], b["bbox_px"])
                coverage = inside_px / total_seg_px

            same_class = (b["class_name"] == s["class_name"])
            matrix.append({
                "yolo_box": b,
                "panoptic_seg": s,
                "same_class": same_class,
                "iou": iou,
                "inside_pixels": inside_px,
                "total_pixels": total_seg_px,
                "coverage": coverage,
            })

    return {
        "target": target,
        "width": img_w,
        "height": img_h,
        "num_yolo_boxes": len(yolo_boxes),
        "num_panoptic_things": len(panoptic_segments),
        "yolo_boxes": yolo_boxes,
        "panoptic_segments": panoptic_segments,
        "matches": matrix,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo logic ghép Box YOLO ↔ Panoptic (Tùng phụ trách)")
    parser.add_argument("delivery", help="Thư mục delivery")
    parser.add_argument("--image", default="000000000139", help="Tên ảnh mẫu để thử nghiệm")
    args = parser.parse_args()

    delivery_path = Path(args.delivery)
    print(f"=== Đang thử nghiệm ghép đối chiếu trên ảnh {args.image} ===")
    res = analyze_image_correspondence(delivery_path, args.image)
    if "error" in res:
        print("Lỗi:", res["error"])
        return 1

    print(f"Kích thước: {res['width']}x{res['height']}")
    print(f"Số box YOLO: {res['num_yolo_boxes']} | Số segment thing: {res['num_panoptic_things']}")
    print("\nCác cặp có tương quan hình học (IoU > 0.2):")
    for m in res["matches"]:
        if m["iou"] > 0.2:
            y_name = m["yolo_box"]["class_name"]
            p_name = m["panoptic_seg"]["class_name"]
            cov = m["coverage"] * 100
            print(f" - YOLO [{y_name}] vs PAN [{p_name}]: IoU={m['iou']:.3f}, Độ phủ pixel trong box={cov:.1f}% (Cùng lớp: {m['same_class']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
