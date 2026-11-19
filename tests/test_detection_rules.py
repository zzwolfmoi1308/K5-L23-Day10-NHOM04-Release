"""Unit test cho 7 luật File, YOLO và Metadata (validator/detection_rules.py).

Chạy bằng: python -m unittest tests/test_detection_rules.py -v
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validator.detection_rules import check_detection_rules  # noqa: E402


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_clean_delivery(base: Path) -> Path:
    """Tạo một thư mục delivery tối giản hoàn toàn sạch (3 ảnh, 2 scene, 2 job)."""
    d = base / "delivery"
    (d / "images").mkdir(parents=True)
    (d / "labels").mkdir(parents=True)
    (d / "masks").mkdir(parents=True)

    # classes.txt (0..79)
    (d / "classes.txt").write_text(
        "\n".join(f"{i} class_{i}" for i in range(80)) + "\n",
        encoding="utf-8",
    )

    # jobs.csv
    (d / "jobs.csv").write_text(
        "job_id,annotator,reviewer,guideline\n"
        "J01,A01,Q01,v1.2\n"
        "J02,A02,Q02,v1.3\n",
        encoding="utf-8",
    )

    specs = [
        ("img_0001", "scene_001", "train", "J01", "v1.2", "0 0.50 0.50 0.20 0.20\n2 0.20 0.20 0.10 0.10\n"),
        ("img_0002", "scene_001", "train", "J01", "v1.2", "0 0.40 0.40 0.30 0.30\n"),
        ("img_0003", "scene_002", "val", "J02", "v1.3", "5 0.60 0.60 0.25 0.25\n"),
    ]

    manifest_items = {}
    metadata_items = []
    panoptic_images = []

    for idx, (stem, scene_id, split, job_id, guideline, label_text) in enumerate(specs, start=1):
        img_bytes = f"fake-jpeg-{stem}".encode("utf-8")
        lab_bytes = label_text.encode("utf-8")
        mask_bytes = f"fake-png-{stem}".encode("utf-8")

        (d / "images" / f"{stem}.jpg").write_bytes(img_bytes)
        (d / "labels" / f"{stem}.txt").write_bytes(lab_bytes)
        (d / "masks" / f"{stem}.png").write_bytes(mask_bytes)

        manifest_items[stem] = {
            "image": f"images/{stem}.jpg",
            "label": f"labels/{stem}.txt",
            "mask": f"masks/{stem}.png",
            "image_sha256": _sha(img_bytes),
            "label_sha256": _sha(lab_bytes),
            "mask_sha256": _sha(mask_bytes),
        }
        metadata_items.append({
            "image": stem,
            "scene_id": scene_id,
            "split": split,
            "job_id": job_id,
            "guideline_version": guideline,
        })
        panoptic_images.append({
            "id": idx,
            "file_name": f"{stem}.jpg",
            "width": 640,
            "height": 480,
        })

    (d / "manifest.json").write_text(json.dumps({"items": manifest_items}, indent=2), encoding="utf-8")
    (d / "metadata.json").write_text(json.dumps({"items": metadata_items}, indent=2), encoding="utf-8")
    (d / "panoptic.json").write_text(
        json.dumps({"images": panoptic_images, "categories": [], "annotations": []}, indent=2),
        encoding="utf-8",
    )
    return d


class DetectionRulesTest(unittest.TestCase):
    def test_clean_delivery_has_zero_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            self.assertEqual(check_detection_rules(d), [])

    def test_missing_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            (d / "images" / "img_0001.jpg").unlink()
            self.assertEqual(
                check_detection_rules(d),
                [{"type": "missing_image", "target": "img_0001"}],
            )

    def test_wrong_hash_detected_from_real_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            # Sửa nội dung ảnh trong khi manifest vẫn giữ hash cũ (đủ 64 ký tự hex)
            (d / "images" / "img_0002.jpg").write_bytes(b"corrupted-bytes")
            self.assertEqual(
                check_detection_rules(d),
                [{"type": "wrong_hash", "target": "img_0002"}],
            )

    def test_guideline_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
            meta["items"][2]["guideline_version"] = "v1.2"  # J02 là v1.3
            (d / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
            self.assertEqual(
                check_detection_rules(d),
                [{"type": "guideline_mismatch", "target": "img_0003"}],
            )

    def test_scene_leak_target_is_scene_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
            meta["items"][1]["split"] = "val"  # scene_001 có cả train và val
            (d / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
            self.assertEqual(
                check_detection_rules(d),
                [{"type": "scene_leak", "target": "scene_001"}],
            )

    def test_invalid_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            new_label = b"80 0.50 0.50 0.20 0.20\n"
            (d / "labels" / "img_0001.txt").write_bytes(new_label)
            man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            man["items"]["img_0001"]["label_sha256"] = _sha(new_label)
            (d / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
            self.assertEqual(
                check_detection_rules(d),
                [{"type": "invalid_class", "target": "img_0001"}],
            )

    def test_bbox_out_of_bounds_even_slight_overflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            # x + w/2 = 0.91 + 0.10 = 1.01 -> tràn mép phải 1%
            new_label = b"0 0.91 0.50 0.20 0.20\n"
            (d / "labels" / "img_0001.txt").write_bytes(new_label)
            man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            man["items"]["img_0001"]["label_sha256"] = _sha(new_label)
            (d / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
            self.assertEqual(
                check_detection_rules(d),
                [{"type": "bbox_out_of_bounds", "target": "img_0001"}],
            )

    def test_duplicate_box_catches_shifted_same_size_and_ignores_natural_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            # 1) Cặp tự nhiên chồng nhau (~0.66 IoU) nhưng khác kích thước -> KHÔNG báo lỗi
            natural_label = (
                "0 0.500000 0.500000 0.300000 0.400000\n"
                "0 0.520000 0.510000 0.240000 0.340000\n"
            ).encode("utf-8")
            (d / "labels" / "img_0001.txt").write_bytes(natural_label)

            # 2) Cặp box bị lặp: cùng lớp, cùng kích thước, lệch 2 px trên ảnh 640x480
            dup_label = (
                "2 0.500000 0.500000 0.200000 0.200000\n"
                f"2 {0.5 + 2/640:.6f} {0.5 + 1/480:.6f} 0.200000 0.200000\n"
            ).encode("utf-8")
            (d / "labels" / "img_0002.txt").write_bytes(dup_label)

            # 3) Cặp giống kích thước nhưng KHÁC lớp -> KHÔNG báo lỗi
            diff_cls_label = (
                "2 0.500000 0.500000 0.200000 0.200000\n"
                "7 0.500000 0.500000 0.200000 0.200000\n"
            ).encode("utf-8")
            (d / "labels" / "img_0003.txt").write_bytes(diff_cls_label)

            man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            man["items"]["img_0001"]["label_sha256"] = _sha(natural_label)
            man["items"]["img_0002"]["label_sha256"] = _sha(dup_label)
            man["items"]["img_0003"]["label_sha256"] = _sha(diff_cls_label)
            (d / "manifest.json").write_text(json.dumps(man), encoding="utf-8")

            self.assertEqual(
                check_detection_rules(d),
                [{"type": "duplicate_box", "target": "img_0002"}],
            )


if __name__ == "__main__":
    unittest.main()
