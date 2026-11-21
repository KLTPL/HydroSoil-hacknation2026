# Spływ

Zobacz, dokąd ucieka woda z Twojej działki, i zatrzymaj ją.

HackNation 2026, zadanie KOWR „Zatrzymaj wodę, chroń plony”.
Zespół: _do uzupełnienia_

**Działająca wersja:** https://woda.kodlab.pl · przykładowy raport:
https://woda.kodlab.pl/#p=040706_5.0016.51%2F1&c=zboza_ozime&d=2025-06-15

Rolnik wpisuje numer działki ewidencyjnej (albo klika na mapie lub używa GPS), wybiera uprawę
i datę analizy (dziś lub do 10 lat wstecz). W około 30 sekund dostaje raport, który
odpowiada na trzy pytania:

1. **Czy na mojej działce brakuje wody i na ile jest to nietypowe?** Klimatyczny bilans
   wodny i model wody w strefie korzeni dla wybranej uprawy, porównane z tym samym dniem
   w 10 poprzednich latach. Ocenę sprawdzają niezależnie: uwodnienie roślin z satelity
   i wilgotność gleby z reanalizy.
2. **Dlaczego?** Przyczyny wyrażone w milimetrach wody: brak opadów, większe parowanie, mała
   pojemność wodna gleby, mało próchnicy, spływ wody z pola, susza hydrologiczna.
3. **Co mogę zrobić na tej działce?** Zalecenia z ilością zatrzymanej wody (m³),
   uzasadnieniem liczbami, terminem, kosztem i formalnościami. Wyróżnik: **mapa retencji
   z lotniczego skanowania LIDAR (1 m)**. Pokazuje zagłębienia terenu, w których można
   zatrzymać wodę, oraz **rowy wykryte w modelu terenu z planem zastawek**, rozmieszczonych
   według spadku rowu.

Raport można wydrukować lub zapisać jako PDF. Zawiera wszystkie źródła danych z licencją i datą
pobrania, a także ograniczenia i brakujące dane.

Materiały zgłoszenia:
- prezentacja: `presentation/splyw-prezentacja.pdf` (źródło: `presentation/slides.html`);
- scenariusz filmu: `presentation/video-script.md`;
- przykładowe raporty wygenerowane przez działającą aplikację, w katalogu `reports/`:
  - Kujawy, czerwiec 2025,
  - Kujawy, susza w lipcu 2019,
  - Lubelskie, dziś, z aktywnymi ostrzeżeniami IMGW.

---

## 1. Instrukcja uruchomienia

**Bez instalacji:** otwórz https://woda.kodlab.pl w dowolnej aktualnej przeglądarce (Chrome,
Firefox, Edge, Safari, Opera), na komputerze lub telefonie.

Lokalnie, w Dockerze:

```sh
docker compose up --build        # http://localhost:8080
```

Tryb deweloperski:

```sh
cd backend && uv run uvicorn retencja_api.api:app --reload   # API na :8000
cd frontend && pnpm install && pnpm dev                      # UI na :5173, przekierowuje /api
```

Produkcja (HTTPS przez Caddy; domenę ustawia się w `deploy/Caddyfile`):

```sh
docker compose -f docker-compose.yml -f deploy/compose.prod.yml up -d --build
```

Link otwierający działkę i od razu uruchamiający analizę:
`/#p=<id działki>&c=<id uprawy>&d=<RRRR-MM-DD>`. Identyfikatory upraw: `GET /api/crops`.

Opcjonalnie: przed pokazem można policzyć z góry analizę terenu dla działek demonstracyjnych,
żeby wynik pojawiał się od razu:

```sh
cd backend && uv run python -m retencja_api.warm_cache [id_działki ...]
```

## 2. Podstawowe funkcjonalności

| Krok | Co dostaje rolnik |
|---|---|
| Działka | Wyszukiwanie po pełnym identyfikatorze (`040706_5.0016.51/1`) lub obrębie i numerze (`Karczyn 51/1`); kliknięcie na mapie; GPS. Granica działki na ortofotomapie z nakładką ewidencyjną. |
| Dane wejściowe | Uprawa (14 grup upraw z monitoringu suszy IUNG) i data analizy (od dziś do 10 lat wstecz). |
| Postęp analizy | Zamiast samego wskaźnika ładowania lista źródeł danych odhaczana na żywo (strumień SSE), z tym, co każde źródło znalazło, i czasem pobrania. |
| Ocena | Werdykt w 4 stopniach: brak / uwaga / niedobór / silny niedobór. Wskaźnik „zbiornika” wody w strefie korzeni z progiem stresu uprawy i poziomem typowym dla tej daty. Zdanie oddziela stan uprawy dziś od porównania z 10 latami. „Głosowanie źródeł”: każde źródło (model wody w glebie, KBW, reanaliza, NDMI z satelity, IMGW) mówi osobno: suszej / typowo / wilgotniej / brak danych. Do tego poziom wiarygodności, niższy, gdy źródła się nie zgadzają. |
| Przyczyny | Uszeregowane, w mm: brak opadów, większe parowanie, słaba gleba, próchnica, spływ, susza hydrologiczna. |
| Zalecenia | W kolejności z „Podstaw naukowych” KOWR: najpierw retencja, potem gleba i uprawa, nawadnianie na końcu (tylko gdy uprawa cierpi na stres wodny). Zastawki na rowach, oczka wodne i podmokłe łąki w zagłębieniach, próchnica, mulcz i uprawa bez orki, odmiana i termin siewu. Każde z efektem w m³, uzasadnieniem danymi, terminem, kosztem i formalnościami. |
| Mapa retencji | Zagłębienia (oczko wodne / podmokła łąka) z numerami, pojemnością, zlewnią i ilością wody zatrzymanej z deszczu obliczeniowego. Rowy (LIDAR + OpenStreetMap) z proponowanymi zastawkami. Legenda. |
| Rzeźba terenu | Przełącznik podkładu „Zdjęcie / Rzeźba terenu”: cieniowana mikrorzeźba z LIDAR (wysokość względem otoczenia ±kilkadziesiąt cm) i drogi spływu wody. Widać niecki, bruzdy i rowy, których nie widać na zdjęciu. |
| Symulacja ulewy | Przycisk „Puść ulewę 30 mm”: animacja deszczu spływającego po drogach spływu z LIDAR do niecek i poza działkę, z licznikami: ile spada, ile spływa, ile zatrzyma plan (oczka, obniżenia, zastawki). Wariant „Dziś / Z planem”. Objętości pochodzą z analizy; animacja tylko je ilustruje. Przy ustawieniu „ogranicz ruch” pokazuje od razu stan końcowy. |
| Co jeśli | Scenariusze na 30 dni od daty analizy: bez deszczu, sucho / typowo / mokro (pogoda tych samych dni z lat poprzednich), nawadnianie teraz, +1 % próchnicy. Dla każdego: kiedy zacznie się silny stres, ile dni potrwa, ile wody zostanie w glebie, jaka dawka ją uzupełni. |
| Porównanie z EDO | Klasa wskaźnika CDI Europejskiego Obserwatorium Suszy dla tego miejsca i dekady oraz informacja, czy zgadza się z naszą oceną. |
| Kalendarz ryzyka | W ilu z ostatnich 10 lat uprawa miała co najmniej 15 dni silnego stresu wodnego, osobno dla każdego miesiąca od kwietnia do września. |
| Raport | Druk i zapis do PDF (A4, mapa działki, źródła z adresami); link do udostępnienia. |
| Rzetelność | Każde źródło z licencją i datą pobrania; brakujące dane opisane wprost; ostrzeżenie, gdy działka nie jest rolna (ESA WorldCover). |

## 3. Architektura

```
Przeglądarka (React + MapLibre)  ──HTTPS──>  Caddy  ──>  nginx (statyczny UI, proxy /api)
                                                          │
                                                          └─>  backend FastAPI (Python)
                                                                ├─ działka: ULDK GUGiK
                                                                ├─ moduły liczone równolegle, każdy z limitem czasu:
                                                                │   woda      Open-Meteo / NASA POWER → KBW + bilans wody w glebie FAO-56
                                                                │   gleba     SoilGrids WCS → uziarnienie, kategoria IUNG, pojemność wodna
                                                                │   satelita  Sentinel-2 L2A (Planetary Computer STAC + COG) → NDVI/NDMI
                                                                │   hydro     API ostrzeżeń IMGW
                                                                │   pokrycie  ESA WorldCover → czy to grunt rolny
                                                                │   EDO       CDI (WCS Copernicus EMS) → niezależne porównanie
                                                                │   teren     NMT WCS (LIDAR) → zagłębienia, zlewnie, rowy, zastawki
                                                                ├─ diagnoza i zalecenia (czyste funkcje na wynikach modułów)
                                                                └─ pamięć podręczna w plikach (odpowiedzi i analizy)
```

- Każdy moduł zwraca stan `ok | pending | unavailable` z wyjaśnieniem dla rolnika, źródłami
  i czasem trwania. Awaria jednego źródła nie psuje raportu: trafia ono do listy brakujących
  danych.
- Wolne moduły (teren, satelita) mają 25 s. Jeśli nie zdążą, raport i tak się pojawia, a sekcja
  jest oznaczona „w toku”. Obliczenie trwa dalej w tle, a przeglądarka sama pobiera wynik, gdy
  jest gotowy.
- Bez bazy danych i bez kont użytkowników; wyniki są zapisywane w plikach.

Kod: `backend/src/retencja_api/` (`api.py`, `report.py`, `modules.py`, `assessment/`,
`meteo/`, `soil/`, `satellite/`, `hydro/`, `landcover/`, `terrain/`) oraz `frontend/src/`.

### Metody

| Temat | Metoda |
|---|---|
| Klimatyczny bilans wodny (KBW) | Opad minus ewapotranspiracja wskaźnikowa ET0 (FAO-56) z 60 dni, czyli sześciu dekad, jak w Systemie Monitoringu Suszy Rolniczej IUNG. |
| Woda w glebie | Dobowy bilans wody w strefie korzeni metodą FAO-56 z pojedynczym współczynnikiem uprawowym (Allen i in.). Dla każdej uprawy: krzywa Kc z typowymi w Polsce terminami faz, głębokość korzeni i współczynnik p. Całkowita woda dostępna = pojemność wodna × głębokość korzeni. Liczony jest też współczynnik stresu Ks. Symulacja startuje w listopadzie roku poprzedzającego najstarszy porównywany rok. |
| Pojemność wodna gleby | Funkcja pedotransferowa Saxtona i Rawlsa (2006) z zawartości piasku, iłu i węgla organicznego (SoilGrids), 0–100 cm. |
| Kategoria gleby IUNG | Przybliżenie z uziarnienia: od I (piasek luźny i słabogliniasty) do IV (glina średnia i ciężka, ił). |
| Werdykt | Bezwzględny stres uprawy (woda dostępna poniżej progu 1 − p), stopniowany liczbą niezależnych sygnałów suszy: model wody w glebie, KBW, wilgotność gleby z reanalizy (ERA5-Land lub MERRA-2), NDMI z satelity. „Sucho” oznacza: wśród 3 najsuchszych z ok. 11 lat albo co najmniej 15 % poniżej średniej. |
| Silny stres / kalendarz ryzyka | Ks < 0,5; miesiąc liczy się jako suchy przy co najmniej 15 takich dniach. Próg dobrano tak, by wyróżniały się znane susze 2015, 2018 i 2019. |
| Satelita | Sentinel-2 L2A: najnowsze zdjęcie z 20 dni przed datą, na którym co najmniej 60 % działki jest bez chmur (maska SCL). To samo okno w każdym wcześniejszym roku od 2017. NDVI = (B08−B04)/(B08+B04), NDMI = (B08−B11)/(B08+B11), siatka 20 m, z korektą przesunięcia BOA. |
| Zagłębienia | Wypełnianie zagłębień metodą priority-flood (Barnes i in. 2014) na NMT LIDAR 1 m przepróbkowanym do 2 m, kierunki spływu D8. Zagłębienia o głębokości co najmniej 0,15 m i powierzchni co najmniej 300 m², w co najmniej 30 % na działce. Zatrzymana woda = min(pojemność, zlewnia × 30 mm × współczynnik spływu 0,05–0,25). |
| Drogi spływu | Akumulacja przepływu D8 na powierzchni po wypełnieniu zagłębień; linie tam, gdzie spływa woda z co najmniej 800 m². Sieć dzielona przy połączeniach; linia kończy się w niecce (wypełnienie > 0,1 m) albo poza obszarem analizy. |
| Rzeźba terenu (obraz) | Wysokość minus średnia z okna 80 m (rzeźba lokalna), skala barw do 97. percentyla, przemnożona przez cieniowanie wielokierunkowe z przewyższeniem 3×. PNG liczony z tego samego NMT co analiza. |
| Rowy | Komórki leżące co najmniej 0,25 m poniżej średniej z otoczenia 20 m, do których spływa woda z co najmniej 0,2 ha, prowadzone w dół spływu (D8) w linie. Gdy działa OpenStreetMap, dochodzą zapisane tam cieki. |
| Zastawki | Piętrzenie 0,5 m; odstęp = piętrzenie / spadek rowu (co najmniej 50 m), tak by cofka sięgała do następnej zastawki. Woda zatrzymana w rowie plus podniesienie wód gruntowych w pasie 2 × 50 m (średnio 0,25 m × odsączalność 0,05–0,15). |
| Efekty zaleceń | Nawadnianie: uzupełnienie niedoboru w strefie korzeni. Mulcz: 25–50 % parowania z gołej gleby (Kc 0,3 × ET0 od siewu do zwarcia łanu, średnia z 10 lat). Próchnica: +0,5–1 % w warstwie ornej 0,3 m według Saxtona i Rawlsa. |

## 4. Źródła i zakres danych

| Dane | Źródło | Rozdzielczość / okres | Dostęp |
|---|---|---|---|
| Działki (identyfikator, geometria, jednostki) | ULDK, GUGiK | ewidencyjna, aktualna | API, bez klucza |
| Nakładka ewidencyjna, ortofotomapa | KIEG WMS, ORTO WMS Geoportalu (GUGiK) | — | WMS, bez klucza |
| Teren | NMT GRID1, GUGiK (LIDAR) | 1 m, przepróbkowany do 2 m; prostokąt działki + 60 m | WCS, bez klucza |
| Pogoda (podstawowe źródło) | Open-Meteo Historical Weather API (ERA5, ERA5-Land, ECMWF IFS) | ok. 10 km (komórka 0,1°); dobowo; od daty analizy − 11 lat do daty analizy | API, bez klucza |
| Pogoda (zapasowe źródło) | NASA POWER (MERRA-2) | ok. 50 km; dobowo; ten sam okres | API, bez klucza |
| Gleba | SoilGrids 2.0, ISRIC | 250 m; 0–100 cm w 5 warstwach | WCS, bez klucza |
| Satelita | Copernicus Sentinel-2 L2A przez Microsoft Planetary Computer | 10–20 m; od 2017 do daty analizy | STAC + COG, anonimowy token SAS |
| Pokrycie terenu | ESA WorldCover 2021 przez Planetary Computer | 10 m; 2021 | STAC + COG |
| Susza hydrologiczna | IMGW-PIB, API danych publicznych, `warningshydro` | województwo / zlewnia; tylko bieżące | API, bez klucza |
| Wskaźnik suszy do porównania | Europejskie Obserwatorium Suszy (EDO, Copernicus EMS), Combined Drought Indicator v4.1 | ok. 5 km (1/24°); co dekadę; od 2012 | WCS, bez klucza |
| Rowy (uzupełniająco) | OpenStreetMap przez Overpass API | — | API, bez klucza |

## 5. Dane pobierane na bieżąco i pobrane wcześniej

**Wszystkie wyniki i zalecenia aplikacja liczy w chwili zapytania** z powyższych danych. Nie ma
z góry przygotowanych zaleceń ani dołączonych zbiorów danych.

Pobrane dane są zapisywane w pamięci podręcznej serwera, żeby kolejne zapytania były szybkie
i nie wyczerpywały darmowych limitów. Każdy raport podaje przy każdym źródle, czy dane były
**„pobrane teraz”**, czy pochodzą **„z pamięci podręcznej”**, wraz z datą pierwotnego pobrania.

| Dane | Zasada zapisu w pamięci podręcznej |
|---|---|
| Działka (ULDK) | Zapisywana według identyfikatora działki. |
| Analiza terenu (NMT) | Zapisywana dla działki i wersji algorytmu; teren nie zależy od daty analizy. |
| Historia pogody | Open-Meteo: jedna historia od 2005 r. dla komórki 0,1°, odświeżana co miesiąc i wspólna dla wszystkich dat analizy; dni od końca ostatniego zamkniętego miesiąca zawsze pobierane na bieżąco. Po odmowie z powodu limitu (HTTP 429) aplikacja przez godzinę od razu korzysta z NASA POWER. |
| Wskaźnik CDI (EDO) | Mapy starsze niż 60 dni zapisywane dla punktu i dekady; nowsze pobierane na bieżąco. |
| Gleba, pokrycie terenu | Zapisywane według obszaru działki (dane się nie zmieniają). |
| Wskaźniki Sentinel-2 | Wcześniejsze lata zapisywane dla działki i daty (archiwum się nie zmienia); bieżący miesiąc zawsze pobierany na bieżąco. |
| Ostrzeżenia IMGW | Zawsze pobierane na bieżąco. |

Działki demonstracyjne przygotowano 21.11.2026 skryptem `warm_cache` (tylko analiza terenu).

## 6. Biblioteki, komponenty, usługi i narzędzia AI

| Komponent | Wersja | Licencja | Zastosowanie |
|---|---|---|---|
| Python | 3.12 | PSF | środowisko backendu |
| FastAPI | 0.165 | MIT | API HTTP |
| Pydantic | 2.14 | MIT | modele danych |
| Uvicorn | 0.54 | BSD-3-Clause | serwer ASGI |
| HTTPX | 0.28 | BSD-3-Clause | klient HTTP |
| NumPy | 2.5 | BSD-3-Clause | obliczenia na siatkach |
| Rasterio (z GDAL) | 1.5 | BSD-3-Clause (GDAL: MIT) | odczyt GeoTIFF / COG, rasteryzacja |
| Shapely | 2.2 | BSD-3-Clause | geometria |
| pyproj (z PROJ) | 3.8 | MIT | transformacje współrzędnych |
| affine | 3.0 | BSD-3-Clause | transformacje rastrów |
| pytest, pytest-asyncio, Ruff | 9.2, 1.5, 0.17 | MIT | testy, lint (tylko w trakcie tworzenia) |
| React, React DOM | 19.3 | MIT | interfejs |
| MapLibre GL JS | 6.19 | BSD-3-Clause | mapa |
| Vite, TypeScript, oxlint | 8.3, 7.0, 1.90 | MIT, Apache-2.0, MIT | budowanie, lint (tylko w trakcie tworzenia) |
| nginx | 1.29 | BSD-2-Clause | pliki statyczne, proxy API |
| Caddy | 2.10 | Apache-2.0 | HTTPS (Let's Encrypt) |
| Docker / Docker Compose | — | Apache-2.0 | konteneryzacja |
| Oracle Cloud Always Free (Ampere A1, 4 OCPU / 24 GB) | — | darmowy plan | hosting |

Usługi zewnętrzne: patrz punkt 4 (wszystkie bezpłatne, bez kluczy API).

**Narzędzia AI.** Kod, testy i dokumentację napisano z pomocą **Claude Code (Anthropic, model
Claude Opus)** jako asystenta programisty, pod kierunkiem i z weryfikacją zespołu. Działająca
aplikacja **nie używa żadnego modelu AI ani uczenia maszynowego**. Każda liczba w raporcie
wynika z deterministycznych, opisanych obliczeń (punkt 3) na danych źródłowych. Wyniki są więc
powtarzalne i możliwe do wyjaśnienia.

## 7. Licencje i warunki korzystania

| Dane / usługa | Warunki |
|---|---|
| GUGiK (ULDK, NMT, ortofotomapa, KIEG) | Bezpłatne, art. 40a ustawy Prawo geodezyjne i kartograficzne. |
| Open-Meteo | Dane CC BY 4.0; darmowe API do użytku niekomercyjnego. Do użytku komercyjnego: płatny plan API albo zapasowe źródło NASA POWER. |
| NASA POWER | Dane publiczne NASA, bez ograniczeń; prośba o podanie źródła. |
| SoilGrids (ISRIC) | CC BY 4.0. |
| Copernicus Sentinel-2 | Bezpłatne, pełne i otwarte (rozporządzenie UE 1159/2013); „Zawiera zmodyfikowane dane Copernicus Sentinel”. |
| Microsoft Planetary Computer | Bezpłatny dostęp; dane na licencjach poszczególnych zbiorów. |
| ESA WorldCover | CC BY 4.0, © ESA WorldCover project. |
| Dane publiczne IMGW-PIB | Bezpłatne; wymagane podanie źródła („Źródłem danych jest IMGW-PIB”). |
| EDO (Copernicus EMS) | Dane Copernicus: bezpłatne i otwarte (rozp. UE 1159/2013); wymagane podanie źródła. |
| OpenStreetMap | ODbL, © współtwórcy OpenStreetMap. |
| Kod | Napisany w trakcie wydarzenia. Wszystkie zależności mają liberalne licencje open source (punkt 6), zgodne z korzystaniem z rozwiązania przez KOWR. |

## 8. Znane ograniczenia

- **Pogoda pochodzi z reanalizy w siatce** (ok. 10 km Open-Meteo, ok. 50 km NASA POWER), a nie ze
  stacji na polu. Lokalne burze mogą zostać pominięte.
- **Darmowy limit Open-Meteo jest liczony dla adresu IP na dobę.** Po jego przekroczeniu
  aplikacja sama przechodzi na NASA POWER. ET0 z NASA POWER (własne obliczenie FAO-56) jest
  o ok. 10 % niższe niż z Open-Meteo. Porównanie z wcześniejszymi latami pozostaje spójne, bo
  obie strony porównania pochodzą z tego samego źródła.
- **Gleba jest modelowana** (SoilGrids, 250 m), a nie badana w terenie. Kategoria IUNG to
  przybliżenie z uziarnienia, nie oficjalna mapa podatności gleb na suszę.
- **Model wody w glebie** nie uwzględnia wód gruntowych, drenowania ani nawadniania. Korzysta
  z typowych terminów faz, a nie z rzeczywistej daty siewu.
- **Progi suszy przybliżają metodę IUNG.** Nie są oficjalnym komunikatem SMSR. Skalibrowano je
  na znanych latach suszy i sprawdzono na niewielkiej liczbie działek.
- **Teren:** usługa WCS GUGiK potrzebuje ok. 10 s plus 20–40 s na każdy km², a przy dużym
  obciążeniu znacznie dłużej. Dla działek większych niż kilka hektarów teren może pojawić się
  po raporcie (strona uzupełni się sama). Dla działek powyżej 250 ha analiza terenu jest
  pomijana. NMT pochodzi z krajowego skanowania, a nie z bieżącego stanu terenu.
- **Wykrywanie rowów** może też zaznaczać naturalne bruzdy spływu albo rowy przydrożne. Odstęp
  zastawek i efekt dla wód gruntowych liczone są z typowymi wartościami (piętrzenie 0,5 m,
  zasięg 50 m, odsączalność 0,05–0,15).
- **Sentinel-2** wymaga w miarę bezchmurnego zdjęcia z 20 dni przed datą. W przeciwnym razie ten
  rok jest wymieniony jako brakujący.
- **Ostrzeżenia hydrologiczne IMGW** są dostępne tylko dla bieżącego dnia (bez archiwum)
  i dopasowywane według województwa.
- **Scenariusze „co jeśli”** powtarzają pogodę z poprzednich lat, a nie prognozę. Pokazują
  zakres możliwych sytuacji, nie przewidują pogody.
- **CDI z EDO** ma siatkę ok. 5 km i opisuje region, a nie konkretną uprawę. JRC zaleca
  ostrożność przy jego interpretacji od połowy maja 2025 r. (niepewne dane o wilgotności gleby);
  raport to zaznacza.
- **Pokrycie terenu** (sprawdzenie, czy działka jest rolna) pochodzi z 2021 roku.
- **Formalności** w zaleceniach (zgłoszenie wodnoprawne, zarządca rowu) to ogólne wskazówki, a nie
  porada prawna.

## 9. Weryfikacja wyników i zaleceń

- **Niezależne porównania w każdym raporcie.** Model wody w glebie zestawiany jest
  z wilgotnością gleby z reanalizy (ERA5-Land lub MERRA-2) i z NDMI z Sentinel-2 dla tej samej
  daty i historii. Zgodność podnosi, a rozbieżność obniża podaną wiarygodność. Do tego
  porównanie ze wskaźnikiem CDI Europejskiego Obserwatorium Suszy (EDO). Przykład: działka
  z Kujaw w lipcu 2019 r. to u nas „silny niedobór”, a w EDO klasa „Warning”.
- **Porównanie z 10 wcześniejszymi latami** zamiast samych progów bezwzględnych. Błędy
  systematyczne modelu się znoszą, a rolnik może sprawdzić na wykresach lata, które pamięta
  (np. 2018, 2019).
- **Kalibracja.** Próg silnego stresu ustawiono tak, by wyróżniały się znane susze 2015, 2018
  i 2019, a mokry rok 2017 nie (sprawdzone na działce z Kujaw).
- **Kontrole wyrywkowe:**
  - rowy i zagłębienia porównane z ortofotomapą;
  - ET0 z NASA POWER a z Open-Meteo: korelacja 0,98;
  - suchą wiosnę 2025 z Sentinel-2 (NDMI najniższe z 8 lat) zestawiono ze znaną suszą 2025;
  - działka z Kujaw w lipcu 2019 daje „silny niedobór”;
  - próba na 10 działkach z różnych regionów, upraw i dat (2019–2026): wszystkie raporty
    kompletne, pierwsza odpowiedź w 4–13 s.
- **Testy automatyczne** (`cd backend && uv run pytest`, 59 testów):
  - promieniowanie FAO-56 sprawdzone na przykładzie z podręcznika FAO;
  - wiarygodność wyników Penmana-Monteitha;
  - zachowanie bilansu wody w glebie;
  - szeregowanie lat;
  - funkcja pedotransferowa i kategorie gleb;
  - wypełnianie zagłębień i objętości retencji;
  - wykrywanie rowów i odstępy zastawek na sztucznym terenie;
  - zalecenia i scenariusze „co jeśli”;
  - pamięć podręczna i limit Open-Meteo;
  - działanie raportu przy awarii źródeł.
- **Identyfikowalność.** Każde źródło jest w raporcie podlinkowane z licencją i datą pobrania,
  więc każde dane wejściowe można sprawdzić ręcznie.

Sprawdzenie:

```sh
cd backend && uv run pytest && uv run ruff check .
cd frontend && pnpm build && pnpm lint
```

## Skalowalność i koszty

- **Limity i dostępność źródeł:**
  - wszystkie odpowiedzi źródeł są zapisywane w pamięci podręcznej (dane stałe dla działki,
    pogoda dla komórki 0,1°, archiwalne zdjęcia dla działki i daty);
  - przy awarii pogoda przechodzi na NASA POWER, a rowy na samo wykrywanie z LIDAR;
  - wolne moduły mają limit czasu i kończą się w tle;
  - równoległe zapytania o tę samą działkę współdzielą jedno obliczenie.
- **W skali kraju:**
  - analizę terenu (najwolniejszą część, niezależną od daty) liczyć z góry dla wszystkich
    działek rolnych, z krajowych arkuszy NMT zamiast WCS;
  - pogodę i bilans wody liczyć raz dziennie na siatce dla całej Polski (kilka tysięcy komórek);
  - wyniki trzymać w PostGIS lub magazynie obiektów;
  - uruchomić kilka bezstanowych instancji backendu za load balancerem.
- **Koszty:**
  - prototyp działa na Oracle Cloud Always Free (0 zł);
  - usługa krajowa potrzebowałaby komercyjnej licencji na dane pogodowe (API Open-Meteo od
    ok. 30 €/mies.) albo własnego przetwarzania ERA5-Land z Copernicus CDS (bezpłatnie);
  - do tego 2–4 maszyny w chmurze i miejsce na wyniki analizy terenu: rzędu kilkuset zł
    miesięcznie;
  - pozostałe źródła danych są bezpłatne.

## Bezpieczeństwo i prywatność

- Bez kont i bez zbierania danych osobowych; numer działki to publiczna informacja ewidencyjna.
- Tylko HTTPS (HTTP przekierowuje na HTTPS). Dane wejściowe są sprawdzane (długość
  identyfikatora, zakres dat, znane uprawy), a wywołania usług zewnętrznych tylko odczytują dane.
- Przeglądarka pyta o lokalizację tylko po kliknięciu przycisku GPS. Pozycja służy wyłącznie do
  znalezienia działki. Aplikacja jej nie zapisuje (pojawia się jedynie w rotowanym logu dostępu
  serwera).
