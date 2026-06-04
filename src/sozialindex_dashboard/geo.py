from __future__ import annotations

import numpy as np
import pandas as pd


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


def add_distance_km(df: pd.DataFrame, latitude: float, longitude: float) -> pd.DataFrame:
    schools = df.copy()
    lat1 = np.radians(latitude)
    lon1 = np.radians(longitude)
    lat2 = np.radians(schools["latitude"].astype(float))
    lon2 = np.radians(schools["longitude"].astype(float))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    haversine = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    schools["entfernung_km"] = 6371.0088 * 2 * np.arcsin(np.sqrt(haversine))
    return schools


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
