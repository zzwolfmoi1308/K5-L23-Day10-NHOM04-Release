"""Prepare offline review queues and combine the team's completed CSV files."""

from __future__ import annotations

import argparse
import csv
import html
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validator"))
from cross_check import SEMANTIC_TYPES
from delivery import delivery_path, read_json
from pngutil import segment_rgb

FIELDS = ["image", "type", "verdict", "note"]
NOTE = re.compile(r"^\[([a-zA-Z0-9][a-zA-Z0-9-]*)\]\s+(.+)$", re.DOTALL)


def candidates_by_image(path: Path) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    seen = set()
    for row in read_json(path)["candidates"]:
        image, kind = row["target"], row["type"]
        if not image or kind not in SEMANTIC_TYPES or (image, kind) in seen:
            raise ValueError(f"Ứng viên không hợp lệ hoặc bị lặp: {image}, {kind}")
        seen.add((image, kind))
        groups[image].append(row)
    return dict(groups)


def write_csv(path: Path, headers: list[str], rows, encoding: str = "utf-8") -> None:
    file = NamedTemporaryFile(mode="w", newline="", encoding=encoding, dir=path.parent, delete=False)
    temp_path = Path(file.name)
    try:
        with file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def crop_bounds(rects: list[list], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1 = (min(rect[i] for rect in rects) for i in (0, 1))
    x2, y2 = (max(rect[i] for rect in rects) for i in (2, 3))
    padding = max(16, max(x2 - x1, y2 - y1) * 0.18)
    return (max(0, math.floor(x1 - padding)), max(0, math.floor(y1 - padding)),
            min(width, math.ceil(x2 + padding)), min(height, math.ceil(y2 + padding)))


def save_overlays(delivery: Path, item: dict, detail: dict, assets: Path, stem: str) -> tuple[str, str, str]:
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageFilter
    except ModuleNotFoundError as exc:
        raise ValueError("Công cụ xem ảnh cần Pillow. Cài bằng: python -m pip install Pillow") from exc

    with Image.open(delivery_path(delivery, item["image"])) as file:
        original = file.convert("RGB")
    with Image.open(delivery_path(delivery, item["mask"])) as file:
        mask = file.convert("RGB")
    segment = detail["segment"]
    red, green, blue = ImageChops.difference(mask, Image.new("RGB", mask.size, segment_rgb(segment["id"]))).split()
    region = ImageChops.lighter(ImageChops.lighter(red, green), blue).point(lambda value: 255 if value == 0 else 0)
    overlay = original.copy()
    tint = (45, 215, 243)
    overlay.paste(tint, mask=region.point(lambda value: value // 4))
    boundary = ImageChops.subtract(region, region.filter(ImageFilter.MinFilter(5)))
    overlay.paste(tint, mask=boundary)
    draw = ImageDraw.Draw(overlay)
    for box in detail["boxes"]:
        draw.rectangle(box["xyxy"], outline="#ffad42", width=3)
        x, y, _, _ = box["xyxy"]
        draw.text((x + 2, max(0, y - 15)), f"L{box['line']} {box['class']}",
                  fill="#ffad42", stroke_width=1, stroke_fill="black")

    region_rect = crop_bounds([segment["xyxy"], *(box["xyxy"] for box in detail["boxes"])], *original.size)
    filenames = [f"{stem}-{suffix}.jpg" for suffix in ("anh", "vung", "nhan")]
    crops = [original, original.crop(region_rect), overlay.crop(region_rect)]
    for filename, picture in zip(filenames, crops):
        picture.save(assets / filename, quality=91)
    return tuple(f"assets/{name}" for name in filenames)


def render_image(delivery: Path, item: dict, image: str, rows: list[dict], assets: Path, index: int) -> str:
    title = html.escape(image)
    types = html.escape(", ".join(row["type"] for row in rows))
    cards = [f"<article><h2>{title}</h2><p>{types}</p>"]
    # The two possible class swaps share the same image and evidence.
    seen = set()
    for row in rows:
        for detail in row["evidence"]:
            key = (detail["segment"]["id"], tuple(box["line"] for box in detail["boxes"]))
            if key in seen:
                continue
            seen.add(key)
            full, raw, overlay = save_overlays(delivery, item, detail, assets, f"{index}-{len(seen)}")
            boxes = ", ".join(f"dòng {b['line']} – {b['class']}" for b in detail["boxes"]) or "không thấy box phù hợp"
            segment = html.escape(detail["segment"]["class"])
            cards.append(f'<p>Detection {html.escape(boxes)} · Panoptic {segment} · <a href="{full}">Mở ảnh toàn cảnh</a></p>')
            cards.append('<div class="views">')
            for name, label in ((raw, "Vùng ảnh gốc"), (overlay, "Vùng ảnh có nhãn")):
                cards.append(f'<figure><a href="{name}"><img src="{name}" alt="{label}" loading="lazy"></a>'
                             f"<figcaption>{label}</figcaption></figure>")
            cards.append("</div>")
    return "\n".join(cards) + "</article>"


def page(title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="vi">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body {{ font: 16px/1.5 system-ui, sans-serif; max-width: 72rem; margin: 2rem auto; padding: 0 1rem; color: #13263a; background: #f8fafc; }}
h1, h2 {{ line-height: 1.2; }}
a {{ color: #07539a; }}
article {{ border-top: 1px solid #ccd9e4; padding: 1rem 0; }}
.views {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(21rem, 100%), 1fr)); gap: 1rem; }}
figure {{ margin: 0; }}
img {{ display: block; width: 100%; height: auto; image-rendering: auto; background: #16273a; }}
</style>
<main><h1>{html.escape(title)}</h1>{content}</main>
</html>
"""


def prepare(delivery: Path, source: Path, out: Path, reviewers: list[str]) -> None:
    groups = candidates_by_image(source)
    manifest = read_json(delivery_path(delivery, "manifest.json"))["items"]
    for image in groups:
        if image not in manifest:
            raise ValueError(f"Ứng viên không có trong manifest: {image}")
    if any(not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]*", name) for name in reviewers):
        raise ValueError("Tên hàng đợi chỉ gồm chữ cái, chữ số và dấu gạch ngang.")
    if len({name.lower() for name in reviewers}) != len(reviewers):
        raise ValueError("Tên hàng đợi bị trùng.")
    out = out.resolve()
    if out.is_relative_to(delivery.resolve()):
        raise ValueError("Thư mục đầu ra phải nằm ngoài delivery.")
    if out.exists():
        raise ValueError(f"Thư mục đã tồn tại: {out}. Chọn đầu ra mới để giữ CSV đang review.")
    assets = out / "assets"
    assets.mkdir(parents=True)
    queues = {name: [] for name in reviewers}
    loads = dict.fromkeys(reviewers, 0)
    for index, (image, rows) in enumerate(sorted(groups.items(),
                                                    key=lambda group: (-len(group[1]), group[0])), 1):
        reviewer = min(reviewers, key=lambda name: (len(queues[name]), loads[name]))
        queues[reviewer].append((index, image, rows))
        loads[reviewer] += len(rows)

    index_links = []
    assignments = []
    for reviewer, images in queues.items():
        queue = f"{reviewer}.csv"
        details = []
        for index, image, rows in images:
            details.append(render_image(delivery, manifest[image], image, rows, assets, index))
            assignments.extend({"queue": reviewer, "image": image, "type": row["type"]} for row in rows)
        template = [{"image": image, "type": row["type"], "verdict": "", "note": ""}
                    for _, image, rows in images for row in rows]
        write_csv(out / queue, FIELDS, template, encoding="utf-8-sig")
        instructions = (
            f'<p>Mở <a href="{quote(queue)}">{html.escape(queue)}</a>. Sau khi xem ảnh, điền '
            "<code>confirmed</code> hoặc <code>rejected</code> và ghi chú dạng "
            "<code>[GitHub] mô tả vật đã thấy</code>. Box detection màu cam, viền segment màu xanh. "
            "Bấm ảnh để mở vùng cắt riêng.</p>"
        )
        (out / f"{reviewer}.html").write_text(page(reviewer, instructions + "\n".join(details)), encoding="utf-8")
        index_links.append(f'<li><a href="{quote(reviewer)}.html">{html.escape(reviewer)}</a>'
                           f" · {len(images)} ảnh · {loads[reviewer]} ứng viên</li>")
    write_csv(out / "assignments.csv", ["queue", "image", "type"], assignments)
    (out / "index.html").write_text(page("Hàng đợi kiểm ảnh", "<ul>" + "".join(index_links) + "</ul>"),
                                   encoding="utf-8")
    print(f"{sum(loads.values())} ứng viên / {len(groups)} ảnh / {len(reviewers)} hàng đợi -> {out}")


def merge(source: Path, inputs: list[Path], out: Path, allow_pending: bool) -> None:
    if out.resolve() == source.resolve():
        raise ValueError("Dùng đường dẫn khác cho review_log.csv và candidates.json.")
    expected = {(image, row["type"]) for image, rows in candidates_by_image(source).items() for row in rows}
    reviews = {}
    for path in inputs:
        with path.open(newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames != FIELDS:
                raise ValueError(f"Sai cột CSV trong {path}. Cần {','.join(FIELDS)}.")
            for number, row in enumerate(reader, 2):
                location = f"{path}:{number}"
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"Sai số cột tại {location}.")
                row = {key: value.strip() for key, value in row.items()}
                key = (row["image"], row["type"])
                if key not in expected:
                    raise ValueError(f"Không có ứng viên {key} tại {location}.")
                if not row["verdict"] and not row["note"]:
                    continue
                note = NOTE.fullmatch(row["note"])
                if row["verdict"] not in {"confirmed", "rejected"} or not note or len(note[2].strip()) < 20:
                    raise ValueError(f"Cần verdict hợp lệ và [GitHub] kèm ít nhất 20 ký tự mô tả tại {location}.")
                if key in reviews and reviews[key] != row:
                    raise ValueError(f"Kết luận bị trùng và khác nhau cho {key} tại {location}.")
                reviews[key] = row

    confirmed = set()
    for (image, _), row in reviews.items():
        if row["verdict"] == "confirmed":
            if image in confirmed:
                raise ValueError(f"Có nhiều kết luận confirmed trên ảnh {image}.")
            confirmed.add(image)
    pending = expected - reviews.keys()
    if pending and not allow_pending:
        raise ValueError(f"Còn {len(pending)} ứng viên chưa review. "
                         f"Dùng --allow-pending nếu cần xuất bản tạm.")
    out.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out, FIELDS, [reviews[key] for key in sorted(reviews)])
    print(f"{len(reviews)} kết luận, {len(pending)} ứng viên đang chờ -> {out}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    queue = commands.add_parser("prepare", help="Tạo HTML xem ảnh và mẫu CSV cho từng hàng đợi.")
    queue.add_argument("delivery", type=Path)
    queue.add_argument("--reviewers", nargs="+", required=True)
    combine = commands.add_parser("merge", help="Gộp CSV do thành viên điền thành review_log.csv.")
    combine.add_argument("logs", type=Path, nargs="+")
    combine.add_argument("--allow-pending", action="store_true")
    for command in (queue, combine):
        command.add_argument("--candidates", type=Path, required=True)
        command.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare(args.delivery, args.candidates, args.out, args.reviewers)
        else:
            merge(args.candidates, args.logs, args.out, args.allow_pending)
    except (OSError, ValueError) as exc:
        parser.exit(status=1, message=f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
