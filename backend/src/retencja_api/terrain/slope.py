"""Slope of the parcel from the LIDAR terrain model: how steep it is, which way water runs,
whether it lies lower than its surroundings, and along which edge runoff leaves it.

Slope classes follow the IUNG water-erosion assessment (Józefaciuk & Józefaciuk): above
about 10 % arable land erodes strongly and permanent grass cover is advised.
"""

import math

import numpy as np
from rasterio import features
from shapely.geometry.base import BaseGeometry

from retencja_api.models import TerrainSlope
from retencja_api.terrain.channels import flow_accumulation, local_relief
from retencja_api.terrain.hydrology import d8_receivers, fill_depressions
from retencja_api.terrain.nmt import Dem

STEEP_SLOPE_PCT = 10.0
# Slope is read from the terrain smoothed over this window: field-scale slope, not the
# furrows and wheel tracks that 2 m LIDAR also shows.
SMOOTHING_M = 10.0
# Below this mean gradient the downhill direction is not meaningful (flat or ridge parcel).
MIN_DIRECTION_PCT = 0.5


def parcel_mask(dem: Dem, parcel: BaseGeometry) -> np.ndarray:
    return features.rasterize(
        [(parcel, 1)], out_shape=dem.elevation.shape, transform=dem.transform, dtype=np.uint8
    ).astype(bool)


def slope_stats(dem: Dem, parcel: BaseGeometry) -> TerrainSlope | None:
    """None when the parcel covers no valid terrain cells."""
    z = dem.elevation
    res = dem.resolution
    valid = np.isfinite(z)
    on = parcel_mask(dem, parcel) & valid
    if not on.any():
        return None
    window = max(3, int(SMOOTHING_M / res) | 1)
    smooth = z - local_relief(z, window)
    d_row, d_col = np.gradient(np.where(valid, smooth, np.nanmean(z)), res)  # row 0 is north
    slope_pct = np.hypot(d_row, d_col) * 100
    slope_on = slope_pct[on]
    cell_ha = res**2 / 10_000

    # Downhill vector in map axes: east = −dz/dcol, north = +dz/drow.
    east, north = float(np.mean(-d_col[on])), float(np.mean(d_row[on]))
    direction = math.hypot(east, north) * 100
    azimuth = (
        round(math.degrees(math.atan2(east, north))) % 360 if direction >= MIN_DIRECTION_PCT
        else None
    )

    around = valid & ~on
    relative = float(np.mean(z[on]) - np.mean(z[around])) if around.any() else 0.0

    filled = fill_depressions(z)
    receiver = d8_receivers(filled)
    area = flow_accumulation(filled, receiver).ravel()
    inside = on.ravel()
    cells = np.arange(receiver.size)
    leaves = inside & (receiver != cells) & ~inside[receiver]
    enters = valid.ravel() & ~inside & (receiver != cells) & inside[receiver]

    return TerrainSlope(
        mean_pct=round(float(np.mean(slope_on)), 1),
        p90_pct=round(float(np.percentile(slope_on, 90)), 1),
        steep_share=round(float(np.mean(slope_on > STEEP_SLOPE_PCT)), 3),
        steep_ha=round(float(np.sum(slope_on > STEEP_SLOPE_PCT)) * cell_ha, 2),
        fall_azimuth_deg=azimuth,
        relative_height_m=round(relative, 2),
        outflow_edge_m=round(float(np.sum(leaves)) * res),
        outflow_area_ha=round(float(np.sum(area[leaves])) * cell_ha, 2),
        runon_area_ha=round(float(np.sum(area[enters])) * cell_ha, 2),
    )
