"""Retention sites on a parcel: terrain depressions, their storage and inflow."""

from dataclasses import dataclass

import numpy as np
from rasterio import features
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from retencja_api.config import (
    DESIGN_RAIN_MM,
    MIN_DEPRESSION_AREA_M2,
    MIN_DEPRESSION_DEPTH_M,
    POND_MIN_DEPTH_M,
    RUNOFF_COEFF_RANGE,
)
from retencja_api.terrain.hydrology import d8_receivers, fill_depressions, terminal_cells
from retencja_api.terrain.nmt import Dem

# Cells filled less than this are not part of a depression (removes epsilon flats).
_DEPTH_FLOOR_M = 0.02
# Keep a depression only if this share of its area lies on the parcel.
MIN_PARCEL_SHARE = 0.3


@dataclass(frozen=True)
class Site:
    kind: str
    area_m2: float
    max_depth_m: float
    storage_m3: float
    catchment_ha: float
    runoff_m3: tuple[float, float]
    retained_m3: tuple[float, float]
    parcel_share: float
    geometry: BaseGeometry  # PL-1992


def _label_components(mask: np.ndarray, dem: Dem) -> tuple[np.ndarray, list[BaseGeometry]]:
    """Label 8-connected components of `mask`; label k ↔ polygons[k - 1]."""
    parts = features.shapes(
        mask.astype(np.uint8), mask=mask, connectivity=8, transform=dem.transform
    )
    polygons = [shape(geom) for geom, _ in parts]
    if not polygons:
        return np.zeros(mask.shape, dtype=np.int32), []
    labels = features.rasterize(
        ((poly, k) for k, poly in enumerate(polygons, start=1)),
        out_shape=mask.shape,
        transform=dem.transform,
        dtype=np.int32,
    )
    return labels * mask, polygons


def _touches_outlet(labels: np.ndarray, valid: np.ndarray, count: int) -> np.ndarray:
    """Labels adjacent to the grid edge or missing data: spill level is unreliable there."""
    outlet = np.pad(~valid, 1, constant_values=True)
    near = np.zeros(valid.shape, dtype=bool)
    h, w = valid.shape
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            near |= outlet[1 + dr : 1 + dr + h, 1 + dc : 1 + dc + w]
    touching = np.zeros(count + 1, dtype=bool)
    touching[np.unique(labels[near])] = True
    return touching


def find_sites(dem: Dem, parcel: BaseGeometry) -> list[Site]:
    z = dem.elevation
    valid = ~np.isnan(z)
    cell_area = dem.resolution**2

    filled = fill_depressions(z)
    depth = np.where(valid, filled - z, 0.0)
    labels, polygons = _label_components(depth > _DEPTH_FLOOR_M, dem)
    n = len(polygons)
    if n == 0:
        return []

    flat_labels = labels.ravel()
    cells = np.bincount(flat_labels, minlength=n + 1)
    volume = np.bincount(flat_labels, weights=depth.ravel(), minlength=n + 1) * cell_area
    max_depth = np.zeros(n + 1)
    np.maximum.at(max_depth, flat_labels, depth.ravel())

    on_parcel = features.rasterize(
        [(parcel, 1)], out_shape=z.shape, transform=dem.transform, dtype=np.uint8
    ).astype(bool)
    parcel_cells = np.bincount(flat_labels[on_parcel.ravel()], minlength=n + 1)

    # Catchment: every cell whose downstream path first reaches the depression.
    terminal = terminal_cells(d8_receivers(filled), labels > 0)
    catchment_cells = np.bincount(flat_labels[terminal], minlength=n + 1)

    touching = _touches_outlet(labels, valid, n)
    rain_m = DESIGN_RAIN_MM / 1000
    sites = []
    for k in range(1, n + 1):
        area = cells[k] * cell_area
        share = parcel_cells[k] / cells[k]
        if (
            touching[k]
            or max_depth[k] < MIN_DEPRESSION_DEPTH_M
            or area < MIN_DEPRESSION_AREA_M2
            or share < MIN_PARCEL_SHARE
        ):
            continue
        catchment_m2 = catchment_cells[k] * cell_area
        runoff = tuple(catchment_m2 * rain_m * c for c in RUNOFF_COEFF_RANGE)
        sites.append(
            Site(
                kind="pond" if max_depth[k] >= POND_MIN_DEPTH_M else "wet_depression",
                area_m2=float(area),
                max_depth_m=float(max_depth[k]),
                storage_m3=float(volume[k]),
                catchment_ha=float(catchment_m2 / 10_000),
                runoff_m3=(float(runoff[0]), float(runoff[1])),
                retained_m3=(float(min(volume[k], runoff[0])), float(min(volume[k], runoff[1]))),
                parcel_share=float(share),
                # Round off the cell staircase for display.
                geometry=polygons[k - 1]
                .buffer(dem.resolution / 2)
                .buffer(-dem.resolution / 2)
                .simplify(dem.resolution / 2),
            )
        )
    return sorted(sites, key=lambda s: s.retained_m3[1], reverse=True)
