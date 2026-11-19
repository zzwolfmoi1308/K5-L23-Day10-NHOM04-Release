"""Generate semantic review candidates from the two labels in a delivery."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from delivery import Box, Rect, delivery_path, read_boxes, read_classes, read_json, read_rgb

SEMANTIC_TYPES = {"class_swap", "category_swap", "bbox_drift", "missing_box", "instance_merge"}

# Match complete RGB triplets. Flat runs avoid iterating through large stuff regions.
COLOR_RUN = re.compile(rb"(.{3})\1*", re.DOTALL)


@dataclass(frozen=True)
class Thresholds:
    swap_iou: float = 0.61
    swap_coverage: float = 0.86
    drift_iou: float = 0.25
    drift_coverage_min: float = 0.22
    drift_coverage_max: float = 0.88
    missing_pixels: int = 350
    missing_fraction: float = 0.002
    merge_box_iou: float = 0.22
    merge_part: float = 0.08
    merge_union: float = 0.76
    merge_extent_iou: float = 0.47


@dataclass
class Segment:
    id: int
    name: str
    pixels: int
    rect: Rect
    runs: list[tuple[int, int, int]] = field(repr=False)

    def count_in(self, rect: Rect, margin: int = 1) -> int:
        left, top, right, bottom = (
            math.ceil(rect[0] - margin - 0.5), math.ceil(rect[1] - margin - 0.5),
            math.ceil(rect[2] + margin - 0.5), math.ceil(rect[3] + margin - 0.5),
        )
        return sum(max(0, min(stop, right) - max(start, left))
                   for y, start, stop in self.runs if top <= y < bottom)


@dataclass(frozen=True)
class Pair:
    box: Box
    segment: Segment
    iou: float
    coverage: float

    @property
    def same_class(self) -> bool:
        return self.box.name == self.segment.name


def intersection(a: Rect, b: Rect) -> Rect:
    return max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])


def extent(a: Rect, b: Rect) -> Rect:
    return min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])


def area(rect: Rect) -> float:
    return max(0, rect[2] - rect[0]) * max(0, rect[3] - rect[1])


def iou(a: Rect, b: Rect) -> float:
    overlap = area(intersection(a, b))
    union = area(a) + area(b) - overlap
    return overlap / union if union else 0.0


def read_segments(mask: Path, annotation: dict, things: dict[int, str],
                  width: int, height: int) -> list[Segment]:
    info = {s["id"]: s for s in annotation["segments_info"]
            if s["id"] and not s["iscrowd"] and s["category_id"] in things}
    if not info:
        return []
    mask_width, mask_height, pixels = read_rgb(mask)
    if (mask_width, mask_height) != (width, height):
        raise ValueError(f"Kích thước mask không khớp ảnh: {mask}")
    runs_by_id = defaultdict(list)
    stride = width * 3
    for y in range(height):
        for match in COLOR_RUN.finditer(pixels, y * stride, (y + 1) * stride):
            segment_id = int.from_bytes(match[1], "little")
            if segment_id in info:
                runs_by_id[segment_id].append((y, match.start() // 3 % width,
                                               (match.end() - y * stride) // 3))
    segments = []
    for segment_id, runs in runs_by_id.items():
        meta = info[segment_id]
        count = sum(end - start for _, start, end in runs)
        if count != meta["area"]:
            continue
        rect = (min(start for _, start, _ in runs), runs[0][0],
                max(end for _, _, end in runs), runs[-1][0] + 1)
        segments.append(Segment(segment_id, things[meta["category_id"]], count, rect, runs))
    return segments


def evidence(boxes: list[Box], segment: Segment, **measurements: float) -> dict:
    return {
        "boxes": [{"line": box.line, "class": box.name, "xyxy": [round(x, 2) for x in box.rect]}
                  for box in boxes],
        "segment": {"id": segment.id, "class": segment.name, "xyxy": list(segment.rect),
                    "pixels": segment.pixels},
        **{key: round(value, 3) for key, value in measurements.items()},
    }


def find_image_candidates(boxes: list[Box], segments: list[Segment], image_area: int,
                          limits: Thresholds) -> dict[str, list[dict]]:
    candidates = defaultdict(list)
    pairs = [
        Pair(box, segment, overlap, segment.count_in(box.rect) / segment.pixels)
        for box in boxes for segment in segments
        if (overlap := iou(box.rect, segment.rect)) >= 0.10
        or (box.name == segment.name and area(intersection(box.rect, segment.rect)) >= 0.55 * area(box.rect))
    ]
    by_segment = defaultdict(list)
    for pair in pairs:
        by_segment[pair.segment.id].append(pair)

    # Lock in reliable same-class matches before interpreting ambiguous overlaps.
    used_boxes = set()
    used_segments = set()
    anchors = sorted((p for p in pairs if p.same_class and p.iou >= 0.48 and p.coverage >= 0.91),
                     key=lambda p: (-p.iou, -p.coverage, p.box.line, p.segment.id))
    anchors_by_box = {}
    for pair in anchors:
        if pair.box.line not in used_boxes and pair.segment.id not in used_segments:
            used_boxes.add(pair.box.line)
            used_segments.add(pair.segment.id)
            anchors_by_box[pair.box.line] = pair.segment.id

    # A merged mask may have been anchored to one of its boxes. Check both contributors.
    for segment in segments:
        members = [p for p in by_segment[segment.id] if p.same_class
                   and p.coverage >= limits.merge_part
                   and anchors_by_box.get(p.box.line, segment.id) == segment.id]
        for a, b in combinations(members, 2):
            box_overlap = iou(a.box.rect, b.box.rect)
            joint_extent = iou(extent(a.box.rect, b.box.rect), segment.rect)
            if box_overlap > limits.merge_box_iou or joint_extent < limits.merge_extent_iou:
                continue
            shared = intersection(a.box.rect, b.box.rect)
            # count_in expands rectangles by 1px. Calculate the overlap of the expanded boxes.
            shared_pixels = segment.count_in(shared)
            shared_fraction = shared_pixels / segment.pixels
            union = a.coverage + b.coverage - shared_fraction
            if union < limits.merge_union or any(
                (p.coverage - shared_fraction) * segment.pixels
                < max(limits.merge_part * segment.pixels, 0.10 * area(p.box.rect), 40)
                for p in (a, b)
            ):
                continue
            candidates["instance_merge"].append(evidence([a.box, b.box], segment,
                mask_in_first=a.coverage, mask_in_second=b.coverage, mask_in_union=union,
                box_iou=box_overlap, extent_iou=joint_extent))
            used_boxes.update((a.box.line, b.box.line))
            used_segments.add(segment.id)
            break

    position_matches = sorted(pairs, key=lambda p: (-p.iou, -p.coverage, p.box.line, p.segment.id))
    for pair in position_matches:
        if pair.box.line in used_boxes or pair.segment.id in used_segments:
            continue
        if not pair.same_class and pair.iou >= limits.swap_iou and pair.coverage >= limits.swap_coverage:
            mismatch = evidence([pair.box], pair.segment, iou=pair.iou, mask_in_box=pair.coverage)
            candidates["class_swap"].append(mismatch)
            candidates["category_swap"].append(mismatch)
            used_boxes.add(pair.box.line)
            used_segments.add(pair.segment.id)

    for pair in position_matches:
        if pair.box.line in used_boxes or pair.segment.id in used_segments:
            continue
        box = pair.box.rect
        mask = pair.segment.rect
        if (pair.same_class and pair.iou >= limits.drift_iou
                and limits.drift_coverage_min <= pair.coverage <= limits.drift_coverage_max
                and 0.60 <= (box[2] - box[0]) / (mask[2] - mask[0]) <= 1.65
                and 0.60 <= (box[3] - box[1]) / (mask[3] - mask[1]) <= 1.65):
            candidates["bbox_drift"].append(evidence([pair.box], pair.segment,
                iou=pair.iou, mask_in_box=pair.coverage))
            used_boxes.add(pair.box.line)
            used_segments.add(pair.segment.id)

    for segment in segments:
        if segment.id in used_segments or segment.pixels < max(limits.missing_pixels,
                                                               limits.missing_fraction * image_area):
            continue
        # Also suppress likely matches with a loose extent, for example occluded objects.
        if any(p.coverage >= 0.65 or (p.same_class and p.coverage >= 0.28 and p.iou >= 0.20)
               for p in by_segment[segment.id]):
            continue
        candidates["missing_box"].append(evidence([], segment))
    return candidates


def find_candidates(delivery: Path, limits: Thresholds = Thresholds()) -> list[dict]:
    manifest = read_json(delivery_path(delivery, "manifest.json"))["items"]
    panoptic = read_json(delivery_path(delivery, "panoptic.json"))
    images = {Path(image["file_name"]).stem: image for image in panoptic["images"]}
    annotations = {ann["image_id"]: ann for ann in panoptic["annotations"]}
    things = {c["id"]: c["name"] for c in panoptic["categories"] if c["isthing"]}
    classes = read_classes(delivery)
    results = []
    for name, item in sorted(manifest.items()):
        image = images[name]
        width, height = image["width"], image["height"]
        label = delivery_path(delivery, item["label"])
        mask = delivery_path(delivery, item["mask"])
        if not all(path.is_file() for path in (label, mask, delivery_path(delivery, item["image"]))):
            continue
        boxes = read_boxes(label, classes, width, height)
        if boxes is None:
            continue
        segments = read_segments(mask, annotations[image["id"]], things, width, height)
        for kind, details in sorted(find_image_candidates(boxes, segments, width * height, limits).items()):
            results.append({"type": kind, "target": name, "evidence": details})
    return results
