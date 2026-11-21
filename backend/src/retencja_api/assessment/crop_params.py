"""Crop water-use parameters for the soil water balance (FAO-56 single crop coefficient).

Stage dates are typical for Poland (month, day); Kc and depletion fraction p follow
FAO-56 Tables 12 and 22, adjusted to the crop groups of the IUNG drought monitoring.
"""

from dataclasses import dataclass
from datetime import date

# Bare soil / stubble outside the growing season: evaporation from the topsoil only.
KC_OFF_SEASON = 0.3

MonthDay = tuple[int, int]


@dataclass(frozen=True)
class CropParams:
    start: MonthDay  # sowing, planting or spring regrowth
    development: MonthDay  # canopy starts closing
    mid: MonthDay  # full canopy, peak water use
    late: MonthDay  # ripening
    end: MonthDay  # harvest
    kc_ini: float
    kc_mid: float
    kc_end: float
    root_depth_m: float
    depletion_p: float  # fraction of available water used before stress starts
    critical: str  # stage most sensitive to water shortage (shown to the farmer)

    def stages(self, year: int) -> list[date]:
        return [
            date(year, m, d)
            for m, d in (self.start, self.development, self.mid, self.late, self.end)
        ]

    def kc(self, day: date) -> float:
        start, dev, mid, late, end = self.stages(day.year)
        if day < start or day > end:
            return KC_OFF_SEASON
        if day < dev:
            return self.kc_ini
        if day < mid:
            return _lerp(self.kc_ini, self.kc_mid, (day - dev) / (mid - dev))
        if day < late:
            return self.kc_mid
        return _lerp(self.kc_mid, self.kc_end, (day - late) / (end - late))

    def in_season(self, day: date) -> bool:
        start, *_, end = self.stages(day.year)
        return start <= day <= end


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


CROP_PARAMS: dict[str, CropParams] = {
    "zboza_ozime": CropParams(
        (3, 20), (4, 15), (5, 20), (6, 30), (7, 25), 0.4, 1.15, 0.3, 1.2, 0.55,
        "strzelanie w źdźbło i kłoszenie (maj–czerwiec)",
    ),
    "zboza_jare": CropParams(
        (4, 1), (4, 25), (6, 1), (7, 5), (8, 5), 0.3, 1.15, 0.3, 1.0, 0.55,
        "strzelanie w źdźbło i kłoszenie (czerwiec)",
    ),
    "kukurydza_ziarno": CropParams(
        (5, 1), (5, 30), (7, 5), (8, 25), (10, 10), 0.3, 1.2, 0.35, 1.2, 0.55,
        "wiechowanie i kwitnienie (lipiec)",
    ),
    "kukurydza_kiszonka": CropParams(
        (5, 1), (5, 30), (7, 5), (8, 15), (9, 10), 0.3, 1.15, 1.05, 1.2, 0.55,
        "wiechowanie i kwitnienie (lipiec)",
    ),
    "rzepak": CropParams(
        (3, 15), (4, 10), (5, 1), (6, 15), (7, 20), 0.35, 1.1, 0.35, 1.2, 0.6,
        "kwitnienie i zawiązywanie łuszczyn (maj)",
    ),
    "ziemniak": CropParams(
        (4, 25), (5, 25), (6, 25), (8, 5), (9, 10), 0.5, 1.15, 0.75, 0.5, 0.35,
        "zawiązywanie bulw (czerwiec–lipiec)",
    ),
    "burak_cukrowy": CropParams(
        (4, 10), (5, 15), (6, 25), (9, 1), (10, 15), 0.35, 1.2, 0.7, 1.0, 0.55,
        "intensywny przyrost korzeni (lipiec–sierpień)",
    ),
    "straczkowe": CropParams(
        (4, 1), (4, 25), (5, 25), (6, 30), (7, 20), 0.5, 1.15, 0.3, 0.8, 0.4,
        "kwitnienie i zawiązywanie strąków (czerwiec)",
    ),
    "warzywa": CropParams(
        (4, 20), (5, 15), (6, 15), (8, 15), (9, 15), 0.6, 1.05, 0.9, 0.5, 0.35,
        "formowanie plonu handlowego (lipiec–sierpień)",
    ),
    "truskawki": CropParams(
        (4, 1), (4, 25), (5, 20), (7, 15), (9, 30), 0.4, 0.85, 0.75, 0.3, 0.2,
        "kwitnienie i owocowanie (maj–czerwiec)",
    ),
    "krzewy_owocowe": CropParams(
        (4, 1), (5, 1), (6, 1), (8, 15), (10, 15), 0.3, 1.05, 0.5, 0.6, 0.5,
        "wzrost owoców (czerwiec–lipiec)",
    ),
    "drzewa_owocowe": CropParams(
        (4, 10), (5, 10), (6, 15), (9, 15), (10, 31), 0.45, 0.95, 0.7, 1.0, 0.5,
        "wzrost owoców (czerwiec–sierpień)",
    ),
    "tyton": CropParams(
        (5, 20), (6, 15), (7, 15), (8, 25), (9, 20), 0.5, 1.15, 0.8, 0.8, 0.5,
        "szybki wzrost liści (lipiec)",
    ),
    "chmiel": CropParams(
        (4, 15), (5, 20), (7, 1), (8, 25), (9, 15), 0.3, 1.05, 0.85, 1.0, 0.5,
        "kwitnienie i tworzenie szyszek (lipiec)",
    ),
}
