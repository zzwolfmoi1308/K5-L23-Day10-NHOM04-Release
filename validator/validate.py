"""Lab validator entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

def main() -> int:
    parser = argparse.ArgumentParser(description="Kiểm lô delivery và sinh ứng viên review.")
    parser.add_argument("delivery", type=Path)
    parser.add_argument("--out", type=Path, help="JSON lỗi luật")
    parser.add_argument("--candidates", type=Path, help="JSON ứng viên gán nhãn")
    args = parser.parse_args()
    delivery = args.delivery.resolve()
    if not delivery.is_dir():
        parser.error(f"Không tìm thấy thư mục delivery: {delivery}")
    outputs = [path.resolve() for path in (args.out, args.candidates) if path is not None]
    if not outputs:
        parser.error("Cần truyền --out hoặc --candidates.")
    if len(outputs) != len(set(outputs)) or any(path.is_relative_to(delivery) or path.is_dir() for path in outputs):
        parser.error("Dùng đường dẫn đầu ra riêng biệt, nằm ngoài delivery.")

    results = []
    if args.out:
        from detection_rules import check_detection_rules
        from panoptic_rules import check_rules as check_panoptic_rules

        findings = [*check_detection_rules(delivery), *check_panoptic_rules(delivery)]
        pairs = sorted({(row["type"], row["target"]) for row in findings})
        errors = [{"type": kind, "target": target} for kind, target in pairs]
        results.append((args.out, "errors", errors))
    if args.candidates:
        from cross_check import find_candidates

        results.append((args.candidates, "candidates", find_candidates(delivery)))
    for path, key, rows in results:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({key: rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{len(rows)} {key} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
