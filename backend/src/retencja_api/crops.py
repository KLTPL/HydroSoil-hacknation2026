"""Crop catalogue: the 14 crop groups assessed by the IUNG-PIB agricultural drought
monitoring system (SMSR), plus permanent grassland (meadows and pastures). Agronomic
parameters are added by the assessment module."""

from retencja_api.models import Crop

CROPS: list[Crop] = [
    Crop(id="zboza_ozime", name="Zboża ozime"),
    Crop(id="zboza_jare", name="Zboża jare"),
    Crop(id="kukurydza_ziarno", name="Kukurydza na ziarno"),
    Crop(id="kukurydza_kiszonka", name="Kukurydza na kiszonkę"),
    Crop(id="rzepak", name="Rzepak i rzepik"),
    Crop(id="ziemniak", name="Ziemniak"),
    Crop(id="burak_cukrowy", name="Burak cukrowy"),
    Crop(id="straczkowe", name="Rośliny strączkowe"),
    Crop(id="warzywa", name="Warzywa gruntowe"),
    Crop(id="truskawki", name="Truskawki"),
    Crop(id="krzewy_owocowe", name="Krzewy owocowe"),
    Crop(id="drzewa_owocowe", name="Drzewa owocowe"),
    Crop(id="tyton", name="Tytoń"),
    Crop(id="chmiel", name="Chmiel"),
    Crop(id="laki", name="Łąki trwałe (koszone)"),
    Crop(id="pastwiska", name="Pastwiska trwałe"),
]

CROPS_BY_ID = {crop.id: crop for crop in CROPS}
