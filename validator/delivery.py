"""Shared readers for the lab delivery format."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from pngutil import read_rgb

Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class Box:
    line: int
    name: str
    rect: Rect


def delivery_path(delivery: Path, relative: str) -> Path:
    path = (delivery / relative).resolve()
    if not path.is_relative_to(delivery.resolve()):
        raise ValueError(f"Đường dẫn nằm ngoài delivery: {relative}")
    return path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_classes(delivery: Path) -> dict[int, str]:
    classes = delivery_path(delivery, "classes.txt").read_text(encoding="utf-8")
    return {int(key): name for key, name in (line.split(maxsplit=1) for line in classes.splitlines() if line.strip())}


def read_boxes(path: Path, classes: dict[int, str], width: int, height: int) -> list[Box] | None:
    boxes = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            key, x, y, w, h = line.split()
            name = classes[int(key)]
            x, y, w, h = map(float, (x, y, w, h))
        except (KeyError, ValueError):
            return None
        if not all(map(math.isfinite, (x, y, w, h))) or min(w, h) <= 0:
            return None
        bounds = ((x - w / 2) * width, (y - h / 2) * height,
                  (x + w / 2) * width, (y + h / 2) * height)
        epsilon = 0.002  # YOLO coordinates are rounded before delivery.
        if (min(bounds[:2]) < -epsilon or bounds[2] > width + epsilon
                or bounds[3] > height + epsilon):
            return None
        boxes.append(Box(number, name, bounds))
    return boxes
