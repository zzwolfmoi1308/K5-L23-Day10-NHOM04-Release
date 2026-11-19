"""Lab validator entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cross_check import find_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiểm lô delivery và sinh ứng viên review.")
    parser.add_argument("delivery", type=Path)
    parser.add_argument("--out", type=Path, help="JSON lỗi luật")
    parser.add_argument("--candidates", type=Path, help="JSON ứng viên gán nhãn")
    args = parser.parse_args()
    delivery = args.delivery.resolve()
    outputs = [path.resolve() for path in (args.out, args.candidates) if path is not None]
    if not outputs:
        parser.error("Cần truyền --out hoặc --candidates.")
    if len(outputs) != len(set(outputs)) or any(path.is_relative_to(delivery) for path in outputs):
        parser.error("Dùng đường dẫn đầu ra riêng biệt, nằm ngoài delivery.")

    results = []
    if args.out:
        try:
            from rules import find_rule_errors
        except ModuleNotFoundError as exc:
            if exc.name != "rules":
                raise
            parser.error("Chưa tích hợp validator/rules.py. Chạy riêng với --candidates để đối chiếu.")
        results.append((args.out, "errors", find_rule_errors(delivery)))
    if args.candidates:
        results.append((args.candidates, "candidates", find_candidates(delivery)))
    for path, key, rows in results:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({key: rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{len(rows)} {key} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
