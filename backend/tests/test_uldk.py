import pytest

from retencja_api.parcel.uldk import ParcelNotFound, UldkError, parse_response

ROW = (
    "141804_5.0029.14/108|mazowieckie|powiat piaseczyński|Piaseczno|Pęchery - Łbiska PGR|"
    "14/108|SRID=2180;POLYGON((637000 461000,637100 461000,637100 461100,637000 461100,"
    "637000 461000))"
)


def test_parses_single_parcel_response():
    [(parcel, geom)] = parse_response(f"0\n{ROW}\n")

    assert parcel.id == "141804_5.0029.14/108"
    assert parcel.commune == "Piaseczno"
    assert parcel.number == "14/108"
    assert parcel.area_ha == pytest.approx(1.0)
    assert geom.area == pytest.approx(10_000)
    lon, lat = parcel.geometry["coordinates"][0][0]
    assert 20.9 < lon < 21.1 and 51.9 < lat < 52.1


def test_parses_search_response_with_match_count():
    other = ROW.replace("141804_5.0029.14/108", "080906_5.0010.14/108")

    results = parse_response(f"2\n{ROW}\n{other}\n")

    assert [p.id for p, _ in results] == ["141804_5.0029.14/108", "080906_5.0010.14/108"]


def test_no_results_raises_not_found():
    with pytest.raises(ParcelNotFound):
        parse_response("-1 brak wyników\nbłędny format odpowiedzi XML\n")


def test_other_error_raises_uldk_error():
    with pytest.raises(UldkError):
        parse_response("-1 błąd zapytania\n")
