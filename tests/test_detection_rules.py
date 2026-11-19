"""Unit test cho 7 luật File, YOLO và Metadata (validator/detection_rules.py).

Chạy bằng: python -m unittest tests/test_detection_rules.py -v
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validator.detection_rules import (  # noqa: E402
    DETECTION_RULE_TYPES,
    check_detection_rules,
    is_duplicate_pair,
)

HAVE_CALIB = (ROOT / "data_source" / "coco_panoptic250_calib" / "panoptic.json").is_file()


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


def _set_label(d: Path, stem: str, content: bytes) -> None:
    """Ghi đè file nhãn và cập nhật label_sha256 trong manifest.json để cô lập lỗi cần test."""
    (d / "labels" / f"{stem}.txt").write_bytes(content)
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    man["items"][stem]["label_sha256"] = _sha(content)
    (d / "manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")


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
            # 1) Ảnh bị thay nội dung trong khi manifest vẫn giữ hash cũ (đủ 64 ký tự hex)
            (d / "images" / "img_0002.jpg").write_bytes(b"corrupted-bytes")
            # 2) Label/mask sai hash cũng bị phát hiện (nội dung vẫn đúng cú pháp YOLO, chỉ đổi bytes)
            (d / "labels" / "img_0003.txt").write_bytes(b"5 0.600000 0.600000 0.250000 0.250000\n")
            # 3) Hash viết HOA nhưng khớp bytes thật -> KHÔNG báo lỗi
            man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
            man["items"]["img_0001"]["image_sha256"] = man["items"]["img_0001"]["image_sha256"].upper()
            (d / "manifest.json").write_text(json.dumps(man), encoding="utf-8")

            self.assertEqual(
                check_detection_rules(d),
                [
                    {"type": "wrong_hash", "target": "img_0002"},
                    {"type": "wrong_hash", "target": "img_0003"},
                ],
            )

    def test_guideline_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            # Ghi jobs.csv kèm UTF-8 BOM để kiểm tính bền vững
            jobs_csv = (d / "jobs.csv").read_text(encoding="utf-8")
            (d / "jobs.csv").write_text(jobs_csv, encoding="utf-8-sig")

            meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
            # Cả 2 ảnh trong J01 đều bị ghi sai sang v1.3 (so với jobs.csv J01=v1.2, không so theo số đông)
            meta["items"][0]["guideline_version"] = "v1.3"
            meta["items"][1]["guideline_version"] = "v1.3"
            meta["items"][2]["guideline_version"] = "v1.2"  # J02 là v1.3
            (d / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
            self.assertEqual(
                check_detection_rules(d),
                [
                    {"type": "guideline_mismatch", "target": "img_0001"},
                    {"type": "guideline_mismatch", "target": "img_0002"},
                    {"type": "guideline_mismatch", "target": "img_0003"},
                ],
            )

    def test_scene_leak_target_is_scene_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
            meta["items"][1]["split"] = "VAL "  # scene_001 có cả train và val
            (d / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
            self.assertEqual(
                check_detection_rules(d),
                [{"type": "scene_leak", "target": "scene_001"}],
            )

    def test_invalid_class_variants_and_valid_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            # Biên hợp lệ: class 0 và class 79 -> KHÔNG báo lỗi
            _set_label(d, "img_0001", b"0 0.20 0.20 0.10 0.10\n79 0.80 0.80 0.10 0.10\n")
            # Lỗi: class 80 (ngoài 0..79)
            _set_label(d, "img_0002", b"80 0.50 0.50 0.20 0.20\n")
            # Lỗi: class âm (-1)
            _set_label(d, "img_0003", b"-1 0.50 0.50 0.20 0.20\n")
            self.assertEqual(
                check_detection_rules(d),
                [
                    {"type": "invalid_class", "target": "img_0002"},
                    {"type": "invalid_class", "target": "img_0003"},
                ],
            )

            # Lỗi: số thập phân không nguyên (1.5) hoặc chuỗi rác
            _set_label(d, "img_0002", b"1.5 0.50 0.50 0.20 0.20\n")
            _set_label(d, "img_0003", b"car 0.50 0.50 0.20 0.20\n")
            self.assertEqual(
                check_detection_rules(d),
                [
                    {"type": "invalid_class", "target": "img_0002"},
                    {"type": "invalid_class", "target": "img_0003"},
                ],
            )

    def test_bbox_out_of_bounds_all_edges_and_rounding(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            # Sát mép [0, 1] với sai số làm tròn .6f (~1e-6) -> KHÔNG báo lỗi
            _set_label(d, "img_0001", b"0 0.500000 0.500000 1.000001 1.000001\n")
            # Tràn mép phải 1% (x2 = 1.01)
            _set_label(d, "img_0002", b"0 0.91 0.50 0.20 0.20\n")
            # Tràn mép trái (x1 = -0.01)
            _set_label(d, "img_0003", b"0 0.09 0.50 0.20 0.20\n")
            self.assertEqual(
                check_detection_rules(d),
                [
                    {"type": "bbox_out_of_bounds", "target": "img_0002"},
                    {"type": "bbox_out_of_bounds", "target": "img_0003"},
                ],
            )

            # Tràn mép trên (y1 = -0.01), tràn mép dưới (y2 = 1.01), và w <= 0
            _set_label(d, "img_0001", b"0 0.50 0.09 0.20 0.20\n")
            _set_label(d, "img_0002", b"0 0.50 0.91 0.20 0.20\n")
            _set_label(d, "img_0003", b"0 0.50 0.50 0.00 0.20\n")
            self.assertEqual(
                check_detection_rules(d),
                [
                    {"type": "bbox_out_of_bounds", "target": "img_0001"},
                    {"type": "bbox_out_of_bounds", "target": "img_0002"},
                    {"type": "bbox_out_of_bounds", "target": "img_0003"},
                ],
            )

    def test_duplicate_box_catches_shifted_same_size_and_ignores_natural_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            # 1) Cặp tự nhiên chồng nhau (~0.66 IoU) và cặp nhỏ chồng nhau (IoU ~0.57, chênh cỡ ~10%) -> KHÔNG báo lỗi
            natural_label = (
                "0 0.500000 0.500000 0.300000 0.400000\n"
                "0 0.520000 0.510000 0.240000 0.340000\n"
                f"1 {100/640:.6f} {100/480:.6f} {20/640:.6f} {20/480:.6f}\n"
                f"1 {104/640:.6f} {102/480:.6f} {22/640:.6f} {21/480:.6f}\n"
            ).encode("utf-8")
            _set_label(d, "img_0001", natural_label)

            # 2) Cặp box bị lặp: cùng lớp, cùng kích thước, lệch 2 px trên ảnh 640x480
            dup_label = (
                "2 0.500000 0.500000 0.200000 0.200000\n"
                f"2 {0.5 + 2/640:.6f} {0.5 + 1/480:.6f} 0.200000 0.200000\n"
            ).encode("utf-8")
            _set_label(d, "img_0002", dup_label)

            # 3) Cặp giống kích thước nhưng KHÁC lớp -> KHÔNG báo lỗi
            diff_cls_label = (
                "2 0.500000 0.500000 0.200000 0.200000\n"
                "7 0.500000 0.500000 0.200000 0.200000\n"
            ).encode("utf-8")
            _set_label(d, "img_0003", diff_cls_label)

            self.assertEqual(
                check_detection_rules(d),
                [{"type": "duplicate_box", "target": "img_0002"}],
            )

    def test_duplicate_box_small_tiny_edge_and_no_panoptic_fallback(self):
        img_size = (640, 480)
        # 1) Box nhỏ 10x10 px dịch (2, 2) px -> IoU chỉ ~0.471 nhưng cùng kích thước -> BẮT ĐƯỢC
        small_a = (3, 100 / 640, 100 / 480, 10 / 640, 10 / 480)
        small_b = (3, 102 / 640, 102 / 480, 10 / 640, 10 / 480)
        self.assertTrue(is_duplicate_pair(small_a, small_b, img_size))
        # Không có panoptic.json (img_size=None) -> nhánh dự phòng chuẩn hóa vẫn bắt được
        self.assertTrue(is_duplicate_pair(small_a, small_b, None))

        # 2) Box siêu nhỏ 2x2 px dịch (2, 2) px -> IoU = 0 nhưng cùng kích thước và lệch <= 2.5 px -> BẮT ĐƯỢC
        tiny_a = (3, 50 / 640, 50 / 480, 2 / 640, 2 / 480)
        tiny_b = (3, 52 / 640, 52 / 480, 2 / 640, 2 / 480)
        self.assertTrue(is_duplicate_pair(tiny_a, tiny_b, img_size))

        # 3) Box sát mép bị kẹp tọa độ (dx=0, dy=0, IoU=1.0) -> BẮT ĐƯỢC
        edge_a = (0, 0.90, 0.50, 0.20, 0.20)
        edge_b = (0, 0.90, 0.50, 0.20, 0.20)
        self.assertTrue(is_duplicate_pair(edge_a, edge_b, img_size))

        # 4) Box lớn 100x100 px dịch 5 px (mức lệch lớn hơn ở đề ẩn, IoU ~0.82) -> BẮT ĐƯỢC
        large_a = (0, 200 / 640, 200 / 480, 100 / 640, 100 / 480)
        large_b = (0, 205 / 640, 205 / 480, 100 / 640, 100 / 480)
        self.assertTrue(is_duplicate_pair(large_a, large_b, img_size))

        # 5) Hai box cùng cỡ 40x40 nhưng cách nhau 15 px (2 vật khác nhau) -> KHÔNG báo lỗi
        sep_a = (0, 200 / 640, 200 / 480, 40 / 640, 40 / 480)
        sep_b = (0, 215 / 640, 200 / 480, 40 / 640, 40 / 480)
        self.assertFalse(is_duplicate_pair(sep_a, sep_b, img_size))

    def test_cli_writes_standard_errors_json_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _make_clean_delivery(Path(tmp))
            (d / "images" / "img_0001.jpg").unlink()
            out_json = Path(tmp) / "out" / "errors.json"
            proc = subprocess.run(
                [sys.executable, str(ROOT / "validator" / "detection_rules.py"), str(d), "--out", str(out_json)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0)
            doc = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(doc, {"errors": [{"type": "missing_image", "target": "img_0001"}]})
            self.assertTrue(all(e["type"] in DETECTION_RULE_TYPES for e in doc["errors"]))

    @unittest.skipUnless(HAVE_CALIB, "chưa có dữ liệu calib: python scripts/download_public.py")
    def test_real_clean_calib_batch_has_zero_detection_rule_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean_dir = Path(tmp) / "clean"
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "inject_release.py"), "--seed", "5", "--no-faults", "--out", str(clean_dir)],
                check=True,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(check_detection_rules(clean_dir / "delivery"), [])


if __name__ == "__main__":
    unittest.main()
