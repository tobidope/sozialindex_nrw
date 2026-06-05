from __future__ import annotations


def parse_coordinate(value: str, minimum: float, maximum: float) -> float | None:
    if not value.strip():
        return None
    try:
        coordinate = float(value.replace(",", "."))
    except ValueError:
        return None
    if minimum <= coordinate <= maximum:
        return coordinate
    return None


def socialindex_color(index: int) -> list[int]:
    colors = {
        1: [20, 108, 92, 210],
        2: [45, 145, 111, 210],
        3: [96, 170, 102, 210],
        4: [157, 190, 85, 210],
        5: [220, 178, 70, 220],
        6: [229, 132, 56, 220],
        7: [214, 88, 57, 220],
        8: [178, 55, 74, 220],
        9: [128, 37, 70, 220],
    }
    return colors.get(int(index), [90, 90, 90, 200])
