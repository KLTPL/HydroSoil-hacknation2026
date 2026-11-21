# Metody, źródła naukowe i walidacja na nietypowych działkach

Stan na 21.11.2026. Kod: `backend/src/retencja_api/`. Testy wykonano na produkcji
(`https://splyw.kodlab.pl`, wcześniej `woda.kodlab.pl`), zapytania GET, najwyżej 2 naraz.

Punkt odniesienia: „KOWR – Podstawy naukowe” wymienia jako bazę FAO-56 (Allen i in.),
System Monitoringu Suszy Rolniczej IUNG-PIB (Doroszewski i in. 2012), wytyczne NWRM (KE 2014,
2015) oraz Minasny i in. 2017 (próchnica). Wymaga też kolejności: ocena → przyczyny →
retencja → agrotechnika → nawadnianie, oraz podania niepewności.

Najważniejszy wniosek: obliczenia fizyczne (FAO-56, Saxton i Rawls, priority-flood) są zgodne
ze źródłami. **Werdykt suszy nie korzysta jednak z kryterium SMSR IUNG** (progi KBW
z rozporządzenia MRiRW, kategoria gleby z mapy IUNG). Jury najpewniej porówna wyniki właśnie
z SMSR, a SMSR udostępnia publicznie progi, mapę kategorii gleb i tabele dla gmin
(szczegóły w części d, pkt 1–2).

## (a) Mapa metod → źródła naukowe

| # | Obliczenie (plik) | Co robi kod | Źródło naukowe | Zgodność z „Podstawami” | Odstępstwo / uproszczenie |
|---|---|---|---|---|---|
| 1 | ET0 (`meteo/openmeteo.py`, `meteo/nasa_power.py`) | ET0 Penman-Monteith z Open-Meteo (ERA5/ERA5-Land/IFS), awaryjnie własny PM z NASA POWER; Hargreaves, gdy brak Rs | FAO-56 rozdz. 2–4, równ. 6 (PM), 52 (Hargreaves) | Tak (FAO-56) | Reanaliza 9–25 km zamiast stacji. SMSR liczy ETP zmodyfikowanym wzorem Penmana (Doroszewski i Górski 1995), więc KBW nie jest liczbowo tożsamy z SMSR |
| 2 | Krzywa Kc, fazy (`assessment/crop_params.py`) | Kc_ini/mid/end z interpolacją liniową; stałe daty faz dla Polski; poza sezonem Kc = 0,3 | FAO-56 rozdz. 6, Tab. 12, rys. 25; aktualizacja Kc: Pereira i in. 2021, AWM 243:106466 | Tak | Brak korekty Kc_mid na klimat (równ. 62). W Polsce RHmin ≈ 45 %, u2 ≈ 2 m/s, więc FAO jej nie wymaga. Kiszonka: Kc_end 1,05 to wartość kukurydzy cukrowej. Daty faz kalendarzowe, nie z NDVI |
| 3 | TAW, RAW, p, Zr | TAW = AWC × Zr; RAW = p × TAW | FAO-56 równ. 82–83, Tab. 22 | Tak | p bez korekty na ETc (przypis Tab. 22: p + 0,04(5 − ETc)). Zr zbóż ozimych 1,2 m (FAO 1,5–1,8 m): ostrożnie |
| 4 | Ks i dobowy bilans strefy korzeni (`assessment/water_balance.py`) | Dr = Dr−1 − P + Ks·Kc·ET0; nadwyżka ponad FC odpada; start 1.11 roku przed najstarszym porównywanym (rozbieg) | FAO-56 równ. 84–85, rozdz. 8 | Tak | Brak spływu RO, podsiąku CR i perkolacji DP jako osobnych członów; brak warstwy parowania (Ke). Brak wód gruntowych, drenowania, śniegu i zamarzania |
| 5 | KBW 60 dni | Σ(P − ET0) za 60 dni do daty; ranga wśród ok. 11 lat | SMSR IUNG: Doroszewski i in. 2012; rozp. MRiRW z 11.04.2019 (Dz.U. 2019 poz. 739) | **Częściowo** | SMSR: ETP, okresy sześciodekadowe 21.III–30.IX i **progi KBW dla uprawy i kategorii gleby** (ok. 20 % spadku plonu). Kod nie używa progów, tylko rangi |
| 6 | Pojemność wodna gleby (`soil/soilgrids.py`) | AWC = θ33 − θ1500 wg Saxtona i Rawlsa z piasku, iłu i SOC (SoilGrids 250 m), 0–100 cm; OM = SOC × 1,724 | Saxton i Rawls 2006, SSSAJ 70:1569–1578; SoilGrids 2.0: Poggio i in. 2021, SOIL 7:217–240 | Tak (dane glebowe, pojemność wodna) | OM ucinane do 8 % → poza zakresem dla gleb organicznych. Średnia z prostokąta obejmującego działkę, nie z samej działki |
| 7 | Kategoria IUNG (`soil_category`) | Progi piasku i iłu (USDA) → I–IV | IUNG SMSR: kategorie wg WOD (I < 127,5 mm; II 127,5–169,9; III 170–202,5; IV > 202,5) i grup PTG | **Nie w pełni** | IUNG publikuje rastrową mapę kategorii (WMS `sgeo.iung.pl`, warstwa `Susza:katgl_landuse2024`). Zgodność z nią: 7 z 14 działek (część c) |
| 8 | Porównanie z 10 latami (`compare`, `_ranked`) | Ranga wartości tego dnia wśród lat; „sucho” = 3 najniższe z ok. 11 lub reanaliza < 85 % średniej | Idea percentylowa jak w SPI/SMA (McKee i in. 1993; WMO-No. 1090, 2012) | Częściowo | To nie jest SPI: bez dopasowania rozkładu, baza 10 lat (WMO zaleca ≥ 30). **Błąd przy remisach** (pkt d3) |
| 9 | Wilgotność gleby z reanalizy | ERA5-Land 0–100 cm, odchylenie od średniej | Muñoz-Sabater i in. 2021, ESSD 13:4349–4383 | Tak (niezależne źródło) | Siatka ok. 9–11 km, nie odpowiada konkretnej uprawie |
| 10 | NDVI/NDMI (`satellite/`) | Średnia po pikselach bez chmur (SCL 4/5/6), siatka 20 m; porównanie z tym samym oknem 20 dni w latach od 2017; „sucho” = NDMI o 0,05 poniżej średniej | NDVI: Rouse i in. 1974, Tucker 1979; NDMI/NDWI: Gao 1996, RSE 58:257–266; PAK 2024 rozdz. 6.3.4 | Częściowo | Zadanie wymaga, by interpretacja uwzględniała uprawę. Kod jej nie uwzględnia i nie bierze pod uwagę płodozmianu ani gołej gleby. Porównanie bywa z 1 rokiem (pkt d4) |
| 11 | Zagłębienia (`terrain/hydrology.py`, `retention.py`) | Priority-flood + ε, D8, progi 0,15 m / 300 m² / 30 % na działce | Barnes, Lehman, Mulla 2014, Comput. Geosci. 62:117–127; D8: O'Callaghan i Mark 1984 | Tak (NWRM: oczka, mokradła; KE 2014/2015) | Progi dobrane empirycznie. NMT z daty skanowania |
| 12 | Zlewnia i spływ | Zlewnia D8 w oknie działka + 60 m; spływ = zlewnia × 30 mm × C (0,05–0,25) | Metoda współczynnika spływu; zakres C odpowiada SCS-CN ≈ 75–86 przy P = 30 mm (USDA-NRCS NEH-630 rozdz. 10) | Tak, co do rzędu wielkości | C nie zależy od gleby ani spadku. Zlewnia ucięta oknem 60 m → zaniżona na stokach |
| 13 | Rowy z LIDAR (`terrain/channels.py`) | Lokalna rzeźba < −0,25 m (okno 20 m) + akumulacja ≥ 0,2 ha | Topographic Position Index (Weiss 2001) + akumulacja D8 | Heurystyka | Myli z bruzdami i rowami przydrożnymi (opisane w README) |
| 14 | Zastawki (`terrain/ditches.py`) | Odstęp = piętrzenie / spadek (≥ 50 m); retencja w rowie + pas 2 × 50 m × 0,25 m × Sy 0,05–0,15 | Zasada cofki (poziome zwierciadło); drenaż regulowany (Skaggs i in. 2012, Trans. ASABE 55:799); Sy: Johnson 1967, USGS WSP 1662-D; CDR e-poradnik 2025 | Tak (NWRM: spowalnianie odpływu w rowach) | Zasięg 50 m i Sy przyjęte, nie z gleby ani wód gruntowych |
| 15 | Próchnica → woda | ΔAWC(+1 % OM) wg Saxtona i Rawlsa × 0,3 m | Saxton i Rawls 2006; skala efektu: Minasny i McBratney 2018, EJSS 69:39–47 (+1,16 mm/100 mm na +1 % SOC) | Tak (PDF: Minasny i in. 2017) | Saxton i Rawls daje mniejszy przyrost w piaskach, a Minasny i McBratney większy |
| 16 | Mulcz | Kc 0,3 × ET0 od siewu do zwarcia łanu × 25–50 % | FAO-56 rozdz. 11: ok. 5 % mniej parowania na każde 10 % pokrycia mulczem | Tak | Parowanie z gleby przybliżone Kc 0,3 zamiast Ke (FAO-56 rozdz. 7) |
| 17 | Dawka nawodnienia | Dr (dopełnienie do FC), gdy Dr > RAW | FAO-56 rozdz. 8 (dawka netto) | Tak; nawadnianie na końcu kolejności KOWR | Tekst „2–3 dawki po 20–30 mm” niezgodny z dawką (pkt d8) |
| 18 | Scenariusze 30 dni | Ten sam model uruchomiony na pogodzie z tych samych dni wcześniejszych lat (rok suchy = drugi najsuchszy) | Analogi historyczne, jak ESP (Day 1985, J. Water Resour. Plan. Manage. 111:157) | Tak (pokazuje niepewność) | Nie jest to prognoza; tylko 10 analogów |
| 19 | Werdykt i pewność (`assessment/diagnosis.py`) | Stres bezwzględny (avail < 1 − p) + liczba źródeł „sucho”; pewność obniżana przy brakach i niezgodności | Integracja wielu źródeł (PDF; Żyłowska i Kozyra 2025); kontrola krzyżowa EDO CDI: Sepulcre-Canto i in. 2012, NHESS 12:3519; Cammalleri i in. 2021, NHESS 21:481 | Częściowo | Reguła własna, niekalibrowana. **Brak kryterium prawnego SMSR** |
| 20 | Kalendarz ryzyka | Udział lat, w których w danym miesiącu było ≥ 15 dni z Ks < 0,5 | Rozróżnienie suszy bieżącej i prawdopodobieństwa suszy (PDF, s. 1) | Tak | Próg dobrany na jednej działce (Kujawy) |
| 21 | Czy działka jest rolna | ESA WorldCover 2021, 10 m; rolna, gdy łąki i grunty orne ≥ 50 % | Zanaga i in. 2022 (WorldCover v200) | Tak | Sady i krzewy owocowe są w WorldCover „zadrzewieniami” → fałszywe ostrzeżenia (pkt d5) |
| 22 | Susza hydrologiczna | Ostrzeżenia IMGW dla województwa, tylko bieżące | IMGW-PIB | Tak (dane hydrologiczne) | Skala województwa; brak archiwum |

## (b) Odstępstwa i uproszczenia z uzasadnieniem

| Uproszczenie | Dlaczego dopuszczalne | Kiedy zawodzi / co zrobić |
|---|---|---|
| Pojedynczy Kc zamiast podwójnego (Kcb + Ke) | FAO-56 zaleca pojedynczy Kc do planowania i oceny w skali dni i tygodni (rozdz. 6) | Wiosna na gołej glebie: model widzi pełny zbiornik, a wierzch gleby jest suchy (Środa 2025: model 98 %, ERA5-Land −38 %) |
| Reanaliza zamiast stacji | Jednolite 20 lat dla każdej działki w Polsce; IMGW nie udostępnia dobowych serii dla dowolnego punktu | Burze lokalne, góry (ERA5 zaniża opad orograficzny) |
| Porównanie z 10 latami (rangi) zamiast progów bezwzględnych | Błąd systematyczny modelu się znosi; zadanie mówi o danych z 10 lat | Remisy (pkt d3); 10 lat to za krótko na stabilne percentyle (WMO: ≥ 30) |
| ET0 (FAO PM) zamiast ETP SMSR | Standard FAO-56 cytowany w PDF | Przed zastosowaniem progów SMSR do ET0 trzeba sprawdzić różnicę na kilku dekadach z map KBW IUNG |
| Brak wód gruntowych | Brak publicznych danych o zwierciadle dla działki | Torfy i doliny (Biebrza, Noteć, Odra): model zawyża suszę. Trzeba to oznaczyć (pkt d2) |
| SoilGrids 250 m zamiast mapy glebowo-rolniczej | Globalny, otwarty, z profilem 0–100 cm | Ta sama kategoria co IUNG tylko na 7 z 14 działek. Oficjalny raster IUNG jest dostępny (pkt d2) |
| Stałe daty faz | Brak daty siewu od rolnika | Można je zastąpić datami z krzywej NDVI z Sentinel-2 albo polem „data siewu” |
| Retencja zagłębień = min(pojemność, spływ z 30 mm) | Proste i możliwe do sprawdzenia; zakres C odpowiada CN 75–86 | Duże zlewnie poza oknem 60 m → wynik zaniżony |
| Zastawki: piętrzenie 0,5 m, zasięg 50 m, Sy 0,05–0,15 | Typowe wartości z praktyki drenażu regulowanego | Zastawka wymaga projektu i zgody zarządcy rowu; raport to mówi |

## (c) Wyniki testów nietypowych działek

Czasy to pierwsze zapytanie (zimna pamięć podręczna). Prawie zawsze ok. 26 s, bo teren czeka
pełny budżet 25 s. „IUNG kat.” to raster IUNG `Susza:katgl_landuse2024` w punkcie wewnątrz
działki: 1–4 to kategorie, 11 to las, 13 zabudowa, 14 nieużytki/komunikacja.

| # | Przypadek | Działka (pow.) | Uprawa, data | Czas | Moduły nie-ok | Werdykt / pewność | Kluczowe liczby | Kat. app / IUNG | Uwagi |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Wąski pas, Beskid Niski | 120510_2.0019.463 (3,1 ha; 83 × 653 m) | zboża ozime, 2019-06-20 | 26,5 s | teren pending | uwaga / średnia | woda 61 %, KBW +76 (mokro), ERA5-L −25 % | IV / 3 | „uwaga” przy 1 źródle „sucho” i 1 „mokro”; teren później: rów 73 m, spadek 10 % → 2 zastawki (bez sensu przy 10 %) |
| 2 | Wąski pas 15 m, Podkarpacie | 180205_2.0001.3013 (0,20 ha) | ziemniak, 2018-07-15 | 27,9 s | teren pending (> 1 h) | uwaga / średnia | woda 72 % (mokro), ERA5-L −16 % | IV / 4 | Teren nie powstał: WCS GUGiK nie odpowiedział w 200 s |
| 3 | Góry, Podhale | 121705_2.0502.11095/2 (0,93 ha) | zboża jare, **dziś** | 26,9 s | teren pending | brak / średnia | woda **100 % = „sucho”** (ranga 3/11) | IV / 3 | **Błąd remisów**: nagłówek „suszej niż zwykle wg modelu”, choć gleba pełna; EDO Warning |
| 4 | Torf, Biebrza | 200807_2.0019.622 (1,1 ha) | kukurydza kiszonka, 2019-07-10 | 26,4 s | – | niedobór / średnia | woda 52 % (ranga 3), SOC 6,4 %, AWC 122 | III / 2 | Przyczyna „gleba magazynuje mało wody” na glebie dolinowej z płytką wodą gruntową; satelita „mokro” (porównanie z 1 rokiem) |
| 5 | Pas 31 × 2767 m, Bagno Ławki | 200807_2.0131.1139/1 (7,8 ha; bbox 117 ha) | zboża ozime, 2018-05-25 | 27,4 s | teren pending (> 1 h) | **silny niedobór** / niska | WorldCover las 100 % | II / **14** | Zalecenie: nawodnić 7 364 m³ i „próchnica 0–0 m³” na działce nierolnej; NDVI w listopadzie tylko z 1 z 9 lat |
| 6 | Dolina Noteci | 300202_2.0013.577 (1,4 ha) | kukurydza ziarno, 2018-08-10 | 26,0 s | teren pending | silny niedobór / średnia | woda 15 %, KBW −118 (ranga 4 → „typowo”), NDMI 0,13 vs 0,36 (1 rok) | III / 11 | Data 2015-08-10 poprawnie odrzucona (422) |
| 7 | Piasek, Puszcza Kozienicka (pas 27 m) | 140701_2.0015.327/7 (1,5 ha) | zboża ozime, 2018-06-01 | 26,9 s | – | silny niedobór / średnia | KBW −205 (ranga 1), woda 10 % | II / **1** | Wiarygodne (2018); próg SMSR kat. I (1.IV–31.V) −132 mm przekroczony; satelita „mokro” vs 2017 |
| 8 | Piasek, Kurpie | 200709_2.0018.645 (28 ha) | ziemniak, 2019-06-25 | 27,9 s | – | silny niedobór / niska | woda 17 %, SOC 6,6 % | II / 2 | Zalecenie „próchnica” z efektem 0 m³ |
| 9 | Dolina Wisły, sad (Sandomierz) | 182002_2.0005.486 (0,52 ha) | drzewa owocowe, 2017-07-15 | 26,1 s | brak zdjęcia | silny niedobór / średnia | KBW −136 (ranga 2), EDO Alert | IV / 3 | Zgodne z EDO |
| 10 | Las | 140705_5.0003.469/2 (0,85 ha) | zboża ozime, dziś | 26,8 s | – | brak / niska | ostrzeżenie „nie wygląda na rolną” | III / 11 | Mimo ostrzeżenia zalecenia mulczu i odmiany |
| 11 | Miasto (Warszawa) | 146510_8.0502.1/3 (1,6 ha, droga) | warzywa, dziś | 26,0 s | gleba (brak SoilGrids → założenie) | brak / niska | zabudowa 100 % | – / 13 | Poprawny komunikat o braku gleby |
| 12 | Duża, 175 ha | 303108_2.0045.9/8 | rzepak, 2018-05-15 | 26,3 s | teren pending (> 1 h) | silny niedobór / średnia | 4/4 źródła sucho, woda 23 % | II / 2 | Nawadnianie 132 204 m³; terenu nie udało się policzyć |
| 13 | Duża PGR, **dokładnie 10 lat wstecz** | 321404_2.0022.70 (128 ha) | zboża ozime, 2016-11-21 | 26,5 s | teren pending | brak / średnia | poza sezonem | III / 3 | 2016-11-20 → 422 (granica poprawna) |
| 14 | Mała 0,05 ha | 181301_4.0001.495 | truskawki, 2020-05-20 | 26,1 s | – | silny niedobór / niska | woda 75 % < próg 80 % (p = 0,2) | IV / 4 | Dawka 13 mm „w 2–3 dawkach po 20–30 mm” |
| 15 | **Styczeń**, dolina Odry | 080101_1.0006.2/2 (14 ha) | kukurydza ziarno, 2021-01-15 | 26,0 s | brak zdjęć | uwaga / niska | KBW +46 mm (ranga 3 = „sucho”) | IV / 4 | „Uwaga” w styczniu przy dodatnim KBW |
| 16 | Kujawy, susza 2018 | 040704_2.0004.70/11 (6,2 ha) | zboża ozime, 2018-06-15 | 29,8 s | – | silny niedobór / średnia | KBW −180, woda 9 %, EDO Warning | II / 4 (punkt), 2 (inny punkt) | Satelita „mokro” (2017 inna uprawa: NDVI 0,37 vs 0,72) |
| 17 | Kujawy, 2017 | jw. | zboża ozime, 2017-06-15 | 25,8 s | brak zdjęcia | uwaga / średnia | woda 27 % < 45 % („cierpi”), KBW −56 (mokro) | II / 4 | Na lekkiej glebie model co roku w czerwcu pokazuje stres (średnia 31 %) |
| 18 | Kujawy, kukurydza 2019 | jw. | kukurydza ziarno, 2019-07-20 | 19,1 s | – | silny niedobór / średnia | KBW −198 (ranga 1) | II / 4 | Teren gotowy: 0 zagłębień, 0 rowów |
| 19 | Sad Grójec, **dziś** | 140605_4.0001.1230/2 (1,6 ha) | drzewa owocowe, dziś | 27,7 s | – | uwaga / **niska** | WorldCover „las 79 %” | III / 13 | **Fałszywe ostrzeżenie „nie wygląda na rolną”** w zagłębiu sadowniczym |
| 20 | Sad Grójec, 2019 | jw. | drzewa owocowe, 2019-08-01 | 25,4 s | – | silny niedobór / niska | KBW −219 (ranga 1), EDO Warning | III / 13 | Wiarygodne (2019) |
| 21 | Sad Łącko, 2022 | 121009_2.0004.1557/2 (0,10 ha) | drzewa owocowe, 2022-07-25 | 28,2 s | – | **niedobór** / niska | woda 63 % (> 50 %), KBW −64 | IV / 4 | **SMSR (gmina Łącko 2022): brak suszy dla drzew owocowych we wszystkich okresach.** Próg kat. IV −280 mm daleko |
| 22 | Kujawy, dziś | 040704_2.0004.70/11 | rzepak, dziś | 2,0 s | – | brak / średnia | NDVI 0,07 (goła gleba) vs 0,28 → NDMI „mokro” | II / 4 | NDMI na gołej glebie traktowany jak uwodnienie roślin |
| 23 | Środa Wlkp., wiosna 2025 | 302504_4.0004.1194 (5,4 ha) | burak, 2025-05-20 | 26,5 s | brak zdjęcia | uwaga / niska | woda 98 % („mokro”), ERA5-L −38 %, EDO Warning | II / 13 | SMSR gmina: brak suszy dla buraka; zgodne z „uwaga” |
| 24 | Piasek, burak | 200709_2.0018.645 | burak, 2019-07-15 | 1,9 s | – | silny niedobór / niska | 10 zagłębień, 2 rowy | II / 2 | Oczko 2,4 ha / 1,6 m na działce leśnej |
| 25 | Zły identyfikator | 999999_9.9999.1 | – | 3,0 s | – | 404 „Nie znaleziono działki” | – | – | OK |
| 26 | Wyszukiwanie | „Nowe Bystre 11095/2”, „Batkowo 70/11” | – | < 1 s | – | 1 wynik | – | – | OK; samo „Batkowo 70” zwraca 0 wyników |

Działka złożona z kilku poligonów: wśród 50 sprawdzonych działek ULDK nie było żadnej
(wszystkie `Polygon`). Kod działa na geometriach shapely (pole, rasteryzacja, maski) i obsługuje
`MultiPolygon` bez zmian. Brak testu na produkcji.

Teren (GUGiK WCS): ok. 1 h po pierwszym zapytaniu 6 z 14 działek nadal „pending”. Bezpośredni
test WCS w tym czasie: wycinek 0,05 km² → przekroczony czas po 200 s; 0,17 km² → 182 s.

Wiarygodność ocen dla znanych lat: susze 2018 (Kujawy, Kozienice, Krajenka) i 2019 (Kujawy,
Grójec, Noteć) wychodzą jako „silny niedobór”, zgodnie z EDO CDI w 6 z 10 przypadków „silnego niedoboru”. W wilgotnym
2017 r. Kujawy dają „uwaga”, a KBW jest „wilgotniej niż zwykle”. Rozbieżność z SMSR widać
w Łącku 2022 (pkt d1).

## (d) Znalezione błędy i ryzyka (od najważniejszych)

| # | Waga | Problem (dowód) | Proponowana poprawka (plik → zmiana) |
|---|---|---|---|
| 1 | **Krytyczna** | Werdykt nie stosuje kryterium SMSR (rozp. MRiRW, Dz.U. 2019 poz. 739). Łącko 2022: aplikacja „niedobór”, SMSR „brak suszy” we wszystkich okresach. Jury porówna z danymi referencyjnymi, najpewniej z SMSR | Nowy `assessment/smsr.py`: tabela progów KBW (14 upraw × 4 kategorie × 14 okresów; `susza.iung.pulawy.pl/progi/`); KBW za ostatni pełny okres sześciodekadowy w 21.III–30.IX. W `diagnosis._level`: przekroczenie progu SMSR → co najmniej „niedobór”; same anomalie względne → najwyżej „uwaga”. Dodatkowo moduł kontrolny jak EDO: `GET https://susza.iung.pulawy.pl/wykazy/{rok},{TERYT gminy}/` (lata 2020–2026; TERYT = 6 cyfr + typ, przy typie 4/5 użyć 3, np. 302504_4 → 3025043), wynik „+/-” dla uprawy i kategorii oraz % powierzchni gminy |
| 2 | **Wysoka** | Kategoria gleby z uziarnienia SoilGrids zgodna z mapą IUNG tylko w 7 z 14 przypadków (Kozienice: app II, IUNG 1; Wysowa: IV vs 3; Biebrza: III vs 2). Gleby organiczne nieoznaczone; PTF Saxtona i Rawlsa nie działa przy OM > 8 % | Nowy `soil/iung.py`: WMS GetFeatureInfo `https://sgeo.iung.pl/geoserver/Susza/wms`, warstwa `Susza:katgl_landuse2024` (`INFO_FORMAT=application/json`, pole `GRAY_INDEX`), w kilku punktach działki, dominanta. 1–4 → kategoria do progów SMSR; 5 → „gleba organiczna” (pomiń PTF, zalecenia: zastawki i utrzymanie wód gruntowych, nie próchnica); 11–14 → ostrzeżenie „nierolna”. SoilGrids zostaje dla AWC i jako zapas |
| 3 | **Wysoka** | Remisy w `compare`: `ordered.index(current)` daje najniższą rangę. Gleba pełna (100 %) → „sucho” (Podhale, listopad). Dotyczy zimy i dat po deszczach | `assessment/water_balance.py:compare` → ranga średnia przy remisach (`(n_less + (n_less + n_equal)) / 2`); `diagnosis._ranked` → „normal”, gdy \|value − normal\| < próg (woda 5 pp, KBW 10 mm, NDMI 0,05) |
| 4 | **Wysoka** | NDMI porównywany z 1–2 latami i inną uprawą lub gołą glebą. W suszy 2018 sygnał „mokro” (Kujawy, Kozienice, Biebrza) obniża pewność; listopad, goła gleba → „mokro” | `diagnosis.source_signals`: sygnał satelitarny tylko przy ≥ 3 latach porównania i NDVI ≥ 0,4 (zwarty łan) w bieżącym i porównywanych latach; dla zbóż po 1.07 (dojrzewanie) „nie dotyczy”. `satellite/sentinel.best_indices`: scena najbliższa tej samej dacie (± 10 dni), nie najnowsza z 20 dni |
| 5 | **Wysoka** | Sady oznaczane jako „nierolne” (WorldCover: sad = drzewa): Grójec, Łącko → ostrzeżenie „Sprawdź numer działki”, pewność „niska” | `assessment/diagnosis.land_warnings(land, crop)`: dla `drzewa_owocowe`, `krzewy_owocowe` (i `chmiel`) klasy 10 i 20 liczyć jako rolne; docelowo kod IUNG z pkt 2 (11/13/14) zamiast WorldCover |
| 6 | Średnia | Na działkach nierolnych pełne zalecenia: nawadnianie lasu 7 364 m³ (Ławki), mulcz na drodze w Warszawie | `assessment/recommendations.recommend`: przy `land.is_agricultural == False` zostaw tylko retencję (oczka, zastawki) i komunikat; bez nawadniania, mulczu i doboru odmian |
| 7 | Średnia | Zalecenie „Zwiększ próchnicę” z efektem 0–0 m³ (SOC 6–7 %: Ławki, Kurpie) | `recommendations._organic_matter`: `None`, gdy `mm < 1` albo SOC ≥ 3,5 % (wtedy pkt 2: gleba organiczna) |
| 8 | Średnia | Tekst nawadniania: „2–3 dawki po 20–30 mm” przy dawce 13 mm i 114 mm | `recommendations._irrigation`: `n = max(1, ceil(dose / 25))`, tekst „n dawek po ok. dose/n mm”; przy dawce > 60 mm uwaga, że to uzupełnienie całej strefy korzeni |
| 9 | Średnia | Teren „pending” bez końca: błąd zadania w tle jest tylko logowany, następne zapytanie startuje od nowa. GUGiK WCS odpowiadał po 180–200 s (Jasienica 0,2 ha i Ławki > 1 h). Limit 250 ha liczony z pola działki, a nie z prostokąta (Ławki: 7,8 ha działki, 117 ha prostokąta) | `background.py`: zapamiętuj wyjątek (np. 10 min) i zwracaj go w `run_within`/`shared_task`; `report.terrain_module` → `unavailable` z komunikatem. Limit z pola `geom.buffer(60).envelope`. Dla wąskich pasów pobieraj pasy wzdłuż bufora działki, nie cały prostokąt. Opcjonalnie zapas Copernicus DEM GLO-30 (Planetary Computer) z oznaczeniem „30 m, orientacyjnie” |
| 10 | Średnia | Wąskie pasy (15–31 m) a siatka 20 m Sentinel-2: piksele mieszane z sąsiadami (`all_touched`). Działka musi leżeć w całości w jednej scenie (`contains`), więc długi pas na granicy kafli traci lata (Ławki: 1 z 9 lat) | `satellite/sentinel.read_indices`: NDVI z B04/B08 na 10 m; liczba „czystych” pikseli w raporcie; < 5 czystych pikseli → sygnał „niepewny”. `search_scenes`: dopuść scenę z ≥ 95 % pokrycia działki |
| 11 | Niska | Gleba uśredniana po prostokącie działki (kręte pasy, duże działki) | `soil/soilgrids._coverage_mean`: maska geometrii działki (`all_touched=True`) |
| 12 | Niska | Wiosenna susza na uprawach jarych niewidoczna: zbiornik pełny po zimie (Środa 2025: 98 % przy ERA5-L −38 %) | Warstwa parowania (FAO-56 rozdz. 7, Ke) albo zbiornik dwuwarstwowy; minimum: przy różnicy > 25 % między modelem a ERA5-Land komunikat i pewność „średnia” |
| 13 | Niska | „Uwaga” przy równej liczbie sygnałów sucho i mokro (Wysowa 2019) | `diagnosis._level`: liczyć `dry − wet` zamiast samego `dry` |
| 14 | Niska | Parametry: kiszonka Kc_end 1,05 (kukurydza cukrowa); p bez korekty na ETc; truskawki p = 0,2 → prawie zawsze „stres” | `crop_params.py`: kiszonka Kc_end ≈ 0,6 (FAO-56 Tab. 12 przypis o zbiorze na zielono do sprawdzenia); w `run_root_zone` p = p_tab + 0,04(5 − ETc), w granicach 0,1–0,8 |
| 15 | Ryzyko operacyjne | Każda nowa komórka siatki to ok. 20 lat danych z Open-Meteo, czyli setki „wywołań” darmowego limitu. Przy równoległych testach jury może zadziałać przejście na NASA POWER (ET0 ok. 10 % niższe) | Rozgrzać pamięć podręczną dla siatki 0,1° na terenach rolnych (`warm_cache.py`). W raporcie pokazywać, które źródło pogody użyto (jest), i w README uzasadnić spójność porównań |

Wszystkie pierwsze zapytania trwały 19–30 s (teren czeka pełne 25 s). Mieści się to w 30 s, ale
na granicy; strumień SSE pokazuje postęp, więc w praktyce nie jest to problem.

### Stan poprawek (21.11.2026)

Poprawione punkty 1–9 i 13:

- Werdykt stosuje kryterium SMSR: progi z rozporządzenia, a od 2020 r. oficjalny wynik IUNG dla gminy. Łącko 2022 daje teraz „uwagę”, a nie „niedobór”.
- Kategoria gleby pochodzi z mapy IUNG; kod 5 oznacza glebę organiczną.
- Remisy w rankingu dostają środkową pozycję, a dochodzi minimalna różnica.
- NDMI porównujemy tylko przy co najmniej 3 latach i zwartym łanie.
- Sady nie są już oznaczane jako teren nierolny.
- Na terenie nierolnym zostają tylko zalecenia retencji.
- Nie ma już zalecenia próchnicy z efektem 0 m³.
- Liczba dawek nawadniania wynika z wielkości dawki.
- Błąd pobierania terenu jest zapamiętywany na 10 minut, a limit powierzchni liczymy z prostokąta pobierania.
- Sygnały „mokro” znoszą sygnały „sucho”.

Otwarte pozostają punkty 10–12, 14 i 15.

## (e) Ściąga do obrony: pytania jury o metody

| # | Pytanie | Krótka, uczciwa odpowiedź (źródło) |
|---|---|---|
| 1 | Skąd ewapotranspiracja? | FAO-56 Penman-Monteith (Allen i in. 1998, równ. 6) z reanalizy ERA5 (Open-Meteo); awaryjnie liczymy PM sami z NASA POWER, a Hargreaves (równ. 52) tylko tam, gdzie brak promieniowania. To standard cytowany w „Podstawach naukowych” |
| 2 | Czym różni się wasz KBW od SMSR IUNG? | Ta sama definicja (opad minus ewapotranspiracja, 60 dni = 6 dekad). SMSR używa ETP wg zmodyfikowanego Penmana (Doroszewski i Górski 1995) i danych stacyjnych, my ET0 FAO-56 z reanalizy. Kryterium prawne SMSR to progi KBW z rozp. MRiRW (Dz.U. 2019 poz. 739) dla uprawy i kategorii gleby (po wdrożeniu pkt d1 – stosujemy je) |
| 3 | Jak uwzględniacie uprawę? | Krzywa Kc, głębokość korzeni i frakcja p z FAO-56 (Tab. 12 i 22) dla 14 grup upraw SMSR; okres krytyczny i kalendarz ryzyka liczone dla uprawy. Ograniczenie: daty faz typowe, nie z pola |
| 4 | Skąd wiecie, ile wody trzyma gleba? | SoilGrids 2.0 (Poggio i in. 2021) → funkcja pedotransferowa Saxtona i Rawlsa (2006) z piasku, iłu i węgla, profil 0–100 cm; TAW = AWC × Zr (FAO-56 równ. 82). Kategoria podatności wg IUNG (WOD; mapa IUNG). SoilGrids ma 250 m, więc to szacunek, co raport mówi |
| 5 | Kiedy uprawa „cierpi z braku wody”? | Gdy zapas w strefie korzeni spada poniżej RAW = p·TAW, a współczynnik stresu Ks (FAO-56 równ. 84) jest < 1. „Silny stres” to Ks < 0,5 |
| 6 | Dlaczego porównujecie z 10 latami, a nie z normą klimatyczną? | Zadanie wymaga danych z 10 lat; porównanie tej samej metody z tym samym miejscem znosi błąd systematyczny reanalizy i SoilGrids. Świadomie: 10 lat to krótka baza (WMO zaleca 30 dla SPI), dlatego używamy rang, nie percentyli z rozkładu |
| 7 | Jak interpretujecie NDVI/NDMI? | NDVI (Tucker 1979) to wigor, NDMI (Gao 1996) to uwodnienie łanu. Zgodnie z „Podstawami” nie są używane samodzielnie: to jeden z głosów obok modelu, KBW i reanalizy. Ograniczenie: płodozmian zmienia uprawę między latami, dlatego porównujemy tylko przy zwartym łanie i ≥ 3 latach (pkt d4) |
| 8 | Jak podajecie niepewność? | Głosowanie niezależnych źródeł (model, KBW, ERA5-Land, Sentinel-2, IMGW) i poziom pewności; brak danych wymieniony wprost; zakresy (min–max) w efektach zaleceń; scenariusze z analogów pokazują rozrzut. Kontrola krzyżowa z EDO CDI (Cammalleri i in. 2021) |
| 9 | Skąd lokalizacje oczek i mokradeł? | NMT LIDAR GUGiK 1 m → 2 m, wypełnianie zagłębień algorytmem priority-flood (Barnes i in. 2014), kierunki D8. Zlewnia każdego zagłębienia z D8; woda zatrzymana = min(pojemność, spływ z deszczu 30 mm). To działania NWRM (KE 2014, 2015): oczka, mokradła |
| 10 | Skąd współczynnik spływu 0,05–0,25? | Dla deszczu 30 mm odpowiada metodzie SCS-CN z CN ≈ 75–86 (USDA-NRCS NEH-630 rozdz. 10), typowej dla gruntów ornych na glebach B–C. Podajemy zakres, bo nie znamy stanu uprawy |
| 11 | Jak rozmieszczacie zastawki? | Odstęp = wysokość piętrzenia / spadek rowu z NMT, tak by cofka sięgała następnej zastawki (zasada drenażu regulowanego, Skaggs i in. 2012). Efekt w glebie = pas 2 × 50 m × średnie podniesienie × odsączalność 0,05–0,15 (Johnson 1967). To szacunek do rozmowy ze spółką wodną, nie projekt |
| 12 | Ile wody da próchnica? | Saxton i Rawls: +1 % materii organicznej w warstwie ornej to zwykle 1–4 mm wody dostępnej. To ten sam rząd co metaanaliza Minasny i McBratney 2018 (+1,16 mm/100 mm na +1 % C). Mówimy wprost, że efekt jest mały, a próchnica działa głównie przez infiltrację i strukturę |
| 13 | Dlaczego nawadnianie jest na końcu? | Kolejność z „Podstaw naukowych” KOWR i NWRM: retencja → agrotechnika → nawadnianie. Nawadnianie proponujemy tylko, gdy zapas < RAW; dawka = niedobór Dr (FAO-56 rozdz. 8) |
| 14 | Co z torfami, sadami, wąskimi pasami? | Torfy: model nie zna wód gruntowych, więc oznaczamy glebę organiczną (mapa IUNG, kod 5) i zalecamy piętrzenie zamiast próchnicy. Sady: Kc i p z FAO-56 dla jabłoni, kategoria z IUNG. Wąskie pasy: Sentinel-2 ma piksel 10–20 m, więc pokazujemy liczbę czystych pikseli i obniżamy pewność |
| 15 | Jak sprawdziliście wyniki? | Znane susze 2018 i 2019 dają „silny niedobór”, wilgotny 2017 – nie. Zgodność z EDO CDI w 6 z 10 przypadków „silnego niedoboru”. Porównanie z tabelami SMSR dla gmin (2020+). Test 26 nietypowych przypadków (ten dokument). 69 testów jednostkowych (m.in. przykład FAO-56 dla promieniowania) |

### Źródła (zweryfikowane)

- Allen R.G., Pereira L.S., Raes D., Smith M. 1998. *Crop evapotranspiration*. FAO Irrigation and Drainage Paper 56. (W „Podstawach” jako Rev. 1, 2025; tego wydania nie udało się zweryfikować.)
- Pereira L.S. i in. 2021. Standard single and basal crop coefficients for field crops. *Agric. Water Manage.* 243:106466.
- Doroszewski A. i in. 2012. *Podstawy Systemu Monitoringu Suszy Rolniczej*. IUNG-PIB; `susza.iung.pulawy.pl` (progi, kategorie, tabele gmin).
- Rozporządzenie MRiRW z 11.04.2019 w sprawie wartości klimatycznego bilansu wodnego dla poszczególnych gatunków roślin uprawnych i gleb, Dz.U. 2019 poz. 739.
- Saxton K.E., Rawls W.J. 2006. *Soil Sci. Soc. Am. J.* 70:1569–1578.
- Poggio L. i in. 2021. SoilGrids 2.0. *SOIL* 7:217–240.
- Minasny B., McBratney A.B. 2018. Limited effect of organic matter on soil available water capacity. *Eur. J. Soil Sci.* 69:39–47.
- Minasny B. i in. 2017. Soil carbon 4 per mille. *Geoderma* 292:59–86.
- Barnes R., Lehman C., Mulla D. 2014. Priority-flood. *Computers & Geosciences* 62:117–127.
- Gao B.-C. 1996. NDWI. *Remote Sens. Environ.* 58:257–266; Tucker C.J. 1979. *Remote Sens. Environ.* 8:127–150.
- Muñoz-Sabater J. i in. 2021. ERA5-Land. *Earth Syst. Sci. Data* 13:4349–4383.
- Cammalleri C. i in. 2021. A revision of the Combined Drought Indicator (CDI) used in EDO. *NHESS* 21:481–495.
- European Commission 2014/2015. NWRM Policy Document; Guide to NWRM selection, design and implementation.
- USDA-NRCS. National Engineering Handbook, Part 630, Chapter 10 (Estimation of direct runoff).
