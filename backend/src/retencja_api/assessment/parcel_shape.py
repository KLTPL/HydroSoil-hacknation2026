"""Plan-shape metrics of a parcel, used to fit recommendations to its geometry.

Long narrow strips (typical of southern Poland after generations of land division) need
different advice: a pond does not fit in a 15 m strip and a strip running downhill cannot
be worked across the slope.
"""

import math

from shapely.geometry.base import BaseGeometry

from retencja_api.models import ParcelShape

NARROW_WIDTH_M = 40.0  # narrower than this, a tractor cannot work across the strip
NARROW_ELONGATION = 5.0
WINDING_BOX_RATIO = 2.0  # bounding box this many times wider than the strip itself


def _equivalent_rectangle(area: float, perimeter: float) -> tuple[float, float]:
    """Sides (long, short) of the rectangle with the same area and perimeter. Unlike the
    bounding box, its short side stays the strip width when a strip bends."""
    half = perimeter / 2
    disc = half * half - 4 * area
    if disc <= 0:  # rounder than a square
        side = math.sqrt(area)
        return side, side
    short = (half - math.sqrt(disc)) / 2
    return area / short, short


def parcel_shape(geom: BaseGeometry) -> ParcelShape:
    """`geom` in a metric CRS (PL-1992)."""
    area, perimeter = geom.area, geom.length
    length, width = _equivalent_rectangle(area, perimeter)
    box = list(geom.minimum_rotated_rectangle.exterior.coords)
    sides = [(box[i + 1][0] - box[i][0], box[i + 1][1] - box[i][1]) for i in range(2)]
    long_dx, long_dy = max(sides, key=lambda s: math.hypot(*s))
    box_width = min(math.hypot(*s) for s in sides)
    elongation = length / width if width else 1.0
    narrow = width < NARROW_WIDTH_M and elongation >= NARROW_ELONGATION
    return ParcelShape(
        length_m=round(length, 1),
        width_m=round(width, 1),
        box_width_m=round(box_width, 1),
        elongation=round(elongation, 1),
        compactness=round(4 * math.pi * area / perimeter**2, 3) if perimeter else 1.0,
        axis_azimuth_deg=round(math.degrees(math.atan2(long_dx, long_dy))) % 180,
        narrow_strip=narrow,
        winding=narrow and box_width > WINDING_BOX_RATIO * width,
    )


def axis_angle(axis_deg: float, direction_deg: float) -> float:
    """Angle (0–90°) between an undirected axis and a direction."""
    diff = abs(axis_deg - direction_deg) % 180
    return min(diff, 180 - diff)
