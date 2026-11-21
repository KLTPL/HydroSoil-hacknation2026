"""Coordinate transformations between WGS84 (map) and PL-1992 (analysis)."""

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry.base import BaseGeometry

from retencja_api.config import CRS_METRIC, CRS_WGS84

_to_metric = Transformer.from_crs(CRS_WGS84, CRS_METRIC, always_xy=True)
_to_wgs84 = Transformer.from_crs(CRS_METRIC, CRS_WGS84, always_xy=True)


def lonlat_to_metric(lon: float, lat: float) -> tuple[float, float]:
    return _to_metric.transform(lon, lat)


def geometry_to_wgs84(geom: BaseGeometry) -> BaseGeometry:
    def project(xy: np.ndarray) -> np.ndarray:
        return np.column_stack(_to_wgs84.transform(xy[:, 0], xy[:, 1]))

    return shapely.transform(geom, project)
