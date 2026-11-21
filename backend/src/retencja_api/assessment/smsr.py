"""Official agricultural drought criterion of the IUNG Agricultural Drought Monitoring System
(SMSR), as set by the regulation of the Minister of Agriculture of 11 April 2019
(Dz.U. 2019 poz. 739): drought occurs when the climatic water balance (precipitation minus
potential evapotranspiration) of a six-dekad period falls below the threshold for the crop
and the soil category. Thresholds: https://susza.iung.pulawy.pl/progi/ (same for every
voivodeship).
"""

from datetime import date, timedelta

import numpy as np

from retencja_api.meteo.openmeteo import DailyWeather
from retencja_api.models import SmsrCheck

# (start, end) of the 14 six-dekad periods of the growing season, as (month, day).
PERIODS: list[tuple[tuple[int, int], tuple[int, int]]] = [
    ((3, 21), (5, 20)), ((4, 1), (5, 31)), ((4, 11), (6, 10)), ((4, 21), (6, 20)),
    ((5, 1), (6, 30)), ((5, 11), (7, 10)), ((5, 21), (7, 20)), ((6, 1), (7, 31)),
    ((6, 11), (8, 10)), ((6, 21), (8, 20)), ((7, 1), (8, 31)), ((7, 11), (9, 10)),
    ((7, 21), (9, 20)), ((8, 1), (9, 30)),
]

# KBW threshold in mm per crop and soil category (I = most drought-prone), one value per
# period above. None: no yield loss from drought in that period ("x"), or the crop is not
# suited to that soil ("-").
THRESHOLDS: dict[str, dict[str, tuple[int | None, ...]]] = {
    "zboza_ozime": {
        "I": (-129, -132, -137, -145, -154, -165, -180, -199, -220, None, None, None, None, None),
        "II": (-150, -153, -158, -166, -175, -186, -201, -220, -241, None, None, None, None, None),
        "III": (-188, -191, -196, -204, -213, -224, -239, -258, -279, None, None, None, None, None),
        "IV": (-215, -218, -223, -231, -240, -251, -266, -285, -306, None, None, None, None, None),
    },
    "zboza_jare": {
        "I": (-125, -127, -130, -135, -142, -153, -169, -186, -207, None, None, None, None, None),
        "II": (-144, -146, -149, -154, -161, -172, -188, -205, -226, None, None, None, None, None),
        "III": (-174, -176, -179, -184, -191, -202, -218, -235, -256, None, None, None, None, None),
        "IV": (-194, -196, -199, -204, -211, -222, -238, -255, -276, None, None, None, None, None),
    },
    "kukurydza_ziarno": {
        "I": (None, None, None, -168, -161, -156, -153, -152, -153, -154, -156, -158, -161, -164),
        "II": (None, None, None, -200, -193, -188, -185, -184, -185, -186, -188, -190, -193, -196),
        "III": (None, None, None, -236, -229, -224, -221, -220, -221, -222, -224, -226, -229, -232),
        "IV": (None, None, None, -271, -264, -259, -256, -255, -256, -257, -259, -261, -264, -267),
    },
    "kukurydza_kiszonka": {
        "I": (None, None, None, -168, -161, -156, -153, -152, -152, -152, -153, -155, -157, -160),
        "II": (None, None, None, -200, -193, -188, -185, -184, -184, -184, -185, -187, -189, -192),
        "III": (None, None, None, -236, -229, -224, -221, -220, -220, -220, -221, -223, -225, -228),
        "IV": (None, None, None, -271, -264, -259, -256, -255, -255, -255, -256, -258, -260, -263),
    },
    "rzepak": {
        "I": (-207, -187, -170, -155, -142, -132, None, None, None, None, None, None, -138, -138),
        "II": (-232, -211, -193, -177, -165, -155, None, None, None, None, None, None, -158, -158),
        "III": (-275, -254, -236, -220, -208, -198, None, None, None, None, None, None, -205, -205),
        "IV": (-297, -276, -258, -242, -230, -220, None, None, None, None, None, None, -230, -230),
    },
    "ziemniak": {
        "I": (None, None, -238, -232, -226, -219, -210, -200, -189, -178, -168, -157, -147, None),
        "II": (None, None, -257, -251, -245, -238, -229, -219, -208, -197, -187, -176, -166, None),
        "III": (None, None, -286, -280, -274, -267, -258, -248, -237, -226, -216, -205, -195, None),
        "IV": (None, None, -306, -300, -294, -287, -278, -268, -257, -246, -236, -225, -215, None),
    },
    "burak_cukrowy": {
        "I": (None, None, None, None, None, None, None, None, None, None, None, None, None, None),
        "II": (-250, -248, -245, -241, -237, -232, -226, -220, -212, -202, -192, -182, -169, -155),
        "III": (-277, -275, -272, -268, -264, -259, -253, -247, -239, -229, -219, -209, -196, -182),
        "IV": (-296, -294, -291, -287, -283, -278, -272, -266, -258, -248, -238, -228, -215, -201),
    },
    "chmiel": {
        "I": (None, None, None, -230, -220, -212, -205, -199, -194, -190, -186, -182, None, None),
        "II": (None, None, None, -248, -238, -230, -223, -217, -212, -208, -204, -200, None, None),
        "III": (None, None, None, -285, -275, -267, -260, -254, -249, -245, -241, -237, None, None),
        "IV": (None, None, None, -302, -292, -284, -277, -271, -266, -262, -258, -254, None, None),
    },
    "tyton": {
        "I": (None, None, None, -189, -187, -186, -185, -186, -187, -190, -195, -200, None, None),
        "II": (None, None, None, -201, -199, -198, -197, -198, -199, -202, -207, -212, None, None),
        "III": (None, None, None, -227, -225, -224, -223, -224, -225, -228, -233, -238, None, None),
        "IV": (None, None, None, -240, -238, -237, -236, -237, -238, -241, -246, -251, None, None),
    },
    "warzywa": {
        "I": (None, None, None, -189, -187, -185, -184, -184, -184, -185, -187, -188, None, None),
        "II": (None, None, None, -207, -205, -203, -202, -202, -202, -203, -205, -206, None, None),
        "III": (None, None, None, -243, -241, -239, -238, -238, -238, -239, -241, -242, None, None),
        "IV": (None, None, None, -263, -261, -259, -258, -258, -258, -259, -261, -262, None, None),
    },
    "krzewy_owocowe": {
        "I": (-149, -148, -147, -147, -149, -154, -159, -162, -163, -162, -160, -157, None, None),
        "II": (-166, -165, -164, -164, -166, -171, -176, -179, -180, -179, -177, -174, None, None),
        "III": (-200, -199, -198, -198, -200, -205, -210, -213, -214, -213, -211, -208, None, None),
        "IV": (-217, -216, -215, -215, -217, -222, -227, -230, -231, -230, -228, -225, None, None),
    },
    "drzewa_owocowe": {
        "I": (-168, -171, -175, -180, -187, -193, -199, -205, -210, -215, -220, -223, None, None),
        "II": (-190, -193, -197, -202, -209, -215, -221, -227, -232, -237, -242, -245, None, None),
        "III": (-229, -232, -236, -241, -248, -254, -260, -266, -271, -276, -281, -284, None, None),
        "IV": (-249, -252, -256, -261, -268, -274, -280, -286, -291, -296, -301, -304, None, None),
    },
    "truskawki": {
        "I": (-133, -137, -143, -152, -163, -178, -190, -198, -202, None, None, None, None, None),
        "II": (-150, -154, -160, -169, -180, -195, -207, -215, -219, None, None, None, None, None),
        "III": (-183, -187, -193, -202, -213, -228, -240, -248, -252, None, None, None, None, None),
        "IV": (-204, -208, -214, -223, -234, -249, -261, -269, -273, None, None, None, None, None),
    },
    "straczkowe": {
        "I": (None, None, None, -161, -161, -163, -165, -166, -167, -168, -170, -172, -174, -176),
        "II": (None, None, None, -182, -182, -184, -186, -187, -188, -189, -191, -193, -195, -197),
        "III": (None, None, None, -213, -213, -215, -217, -218, -219, -220, -222, -224, -226, -228),
        "IV": (None, None, None, -234, -234, -236, -238, -239, -240, -241, -243, -245, -247, -249),
    },}


# SMSR reports every dekad; a period that ended longer ago describes another season part.
MAX_REPORT_AGE = timedelta(days=10)


def last_period(day: date) -> tuple[date, date] | None:
    """The newest six-dekad period that ended on or before `day`, at most a dekad earlier;
    None from October to mid-May, when SMSR does not assess drought."""
    done = [
        (date(day.year, *start), date(day.year, *end))
        for start, end in PERIODS
        if date(day.year, *end) <= day
    ]
    if not done or day - done[-1][1] > MAX_REPORT_AGE:
        return None
    return done[-1]


def period_number(start: date) -> int:
    """1–14, the column of the period in the IUNG tables."""
    return [s for s, _ in PERIODS].index((start.month, start.day)) + 1


def smsr_check(
    weather: DailyWeather, crop_id: str, soil_category: str, day: date
) -> SmsrCheck | None:
    """None for crops outside SMSR (grassland) and before the first period ends (20 May)."""
    table = THRESHOLDS.get(crop_id)
    period = last_period(day)
    if table is None or period is None:
        return None
    start, end = period
    i0, i1 = weather.index(start), weather.index(end)
    if i0 < 0 or i1 >= len(weather.days):
        return None
    kbw = float(np.nansum(weather.precipitation[i0 : i1 + 1] - weather.et0[i0 : i1 + 1]))
    threshold = table[soil_category][period_number(start) - 1]
    return SmsrCheck(
        period_start=start,
        period_end=end,
        soil_category=soil_category,
        kbw_mm=round(kbw),
        threshold_mm=threshold,
        drought=threshold is not None and kbw <= threshold,
    )
