# Spływ

Zobacz, dokąd ucieka woda z Twojej działki, i zatrzymaj ją.

HackNation 2026 · zadanie KOWR „Zatrzymaj wodę, chroń plony” · zespół Cyberodporni

**Działająca wersja: https://splyw.kodlab.pl** (bez instalacji, każda przeglądarka, także telefon)
· [przykładowy raport](https://splyw.kodlab.pl/#p=040706_5.0016.51%2F1&c=zboza_ozime&d=2025-06-15)

## Co robi

Rolnik podaje numer działki (albo klika na mapie lub używa GPS), uprawę i datę (dziś lub do
10 lat wstecz). W ok. 30 s dostaje raport z odpowiedzią na trzy pytania:

1. **Czy brakuje wody i na ile to nietypowe?** Werdykt w 4 stopniach, porównanie z tym samym
   dniem w 10 poprzednich latach, „głosowanie” niezależnych źródeł.
2. **Dlaczego?** Przyczyny w mm wody: brak opadów, parowanie, słaba gleba, mało próchnicy,
   spływ, susza hydrologiczna.
3. **Co zrobić na tej działce?** Zalecenia z efektem w m³, terminem, kosztem i formalnościami.
   **Wyróżnik: mapa retencji z LIDAR (1 m)**: zagłębienia na oczka wodne i podmokłe łąki oraz
   rowy wykryte w modelu terenu z planem zastawek.

Do tego: symulacja ulewy 30 mm, scenariusze „co jeśli” na 30 dni, kalendarz ryzyka suszy,
raport PDF, opcjonalne konto (moje działki, analiza zbiorcza, archiwum raportów).

## Dlaczego to działa

Metody z „Podstaw naukowych” KOWR. **Aplikacja nie używa AI ani uczenia maszynowego**: każda
liczba to opisane, deterministyczne obliczenie na publicznych danych, powtarzalne
i wyjaśnialne. Wszystko liczone w chwili zapytania.

| Pytanie | Metoda | Dane |
|---|---|---|
| Ile wody ma uprawa? | Dobowy bilans wody w strefie korzeni FAO-56 (Allen i in.): krzywa Kc, głębokość korzeni i współczynnik stresu Ks dla wybranej uprawy | Open-Meteo (ERA5), zapasowo NASA POWER |
| Ile wody utrzyma gleba? | Funkcja pedotransferowa Saxtona i Rawlsa (2006) z piasku, iłu i węgla organicznego | SoilGrids 250 m, mapa kategorii gleb IUNG |
| Czy to susza rolnicza? | Oficjalne kryterium SMSR IUNG: KBW (opad − ET0) z sześciu dekad poniżej progu dla uprawy i gleby (Dz.U. 2019 poz. 739); od 2020 r. tabela IUNG dla gminy | IUNG-PIB |
| Czy to nietypowe? | Ten sam dzień w ok. 11 latach; błędy systematyczne modelu się znoszą | jw. |
| Czy źródła się zgadzają? | Osobne „głosy”: model gleby, KBW, wilgotność z reanalizy, NDMI z satelity, ostrzeżenia IMGW; rozbieżność obniża wiarygodność. Do tego porównanie z CDI Europejskiego Obserwatorium Suszy | ERA5-Land, Sentinel-2, IMGW, EDO |
| Gdzie zatrzymać wodę? | Priority-flood (Barnes i in. 2014): zagłębienia ≥ 0,15 m i ≥ 300 m² z pojemnością, zlewnią i wodą zatrzymaną z deszczu 30 mm | NMT LIDAR GUGiK 1 m |
| Gdzie zastawki? | Rowy z modelu terenu (+ OpenStreetMap); piętrzenie 0,5 m, odstęp = piętrzenie / spadek rowu, by cofka sięgała następnej zastawki | jw. |
| Co zalecić? | Kolejność KOWR: retencja → gleba i uprawa → nawadnianie (tylko przy stresie). Zalecenie pojawia się tylko, gdy wynika z danych działki (spadek, rowy, gleba, kształt, uprawa) | wszystkie powyżej |

Parametry wszystkich metod: [dokumentacja techniczna](docs/dokumentacja-techniczna.md#metody).

## Weryfikacja

- Kujawy, lipiec 2019: u nas „silny niedobór”, w EDO klasa „Warning”.
- Próg silnego stresu wyróżnia znane susze 2015, 2018 i 2019, a mokry rok 2017 nie.
- Rowy i zagłębienia sprawdzone z ortofotomapą; ET0 z NASA POWER i Open-Meteo: korelacja 0,98.
- 10 działek z różnych regionów, upraw i dat (2019–2026): wszystkie raporty kompletne, pierwsza
  odpowiedź w 4–13 s.
- 125 testów automatycznych (m.in. FAO-56 na przykładzie z podręcznika FAO, bilans wody,
  wypełnianie zagłębień, odstępy zastawek).
- Każde źródło w raporcie podlinkowane z licencją i datą pobrania.

## Najważniejsze ograniczenia

- Pogoda z reanalizy (ok. 10 km), nie ze stacji na polu: lokalne burze mogą umknąć.
- Gleba modelowana (250 m), nie badana w terenie.
- Model wody nie uwzględnia wód gruntowych, drenowania ani rzeczywistej daty siewu.
- Wykrywanie rowów może zaznaczyć też naturalne bruzdy lub rowy przydrożne.

[Pełna lista ograniczeń](docs/dokumentacja-techniczna.md#8-znane-ograniczenia)

## Uruchomienie lokalne

```sh
docker compose up --build   # http://localhost:8080
```

## Materiały

- Prezentacja: [`presentation/splyw-prezentacja.pdf`](presentation/splyw-prezentacja.pdf)
- Scenariusz filmu: [`presentation/video-script.md`](presentation/video-script.md)
- Raporty z aplikacji: [`reports/`](reports/) (Kujawy 06.2025, Kujawy susza 07.2019,
  Lubelskie dziś z ostrzeżeniami IMGW)
- **[Dokumentacja techniczna](docs/dokumentacja-techniczna.md)**: pełne punkty 1–9 regulaminu
  (architektura, źródła i zakresy danych, dane bieżące i z pamięci podręcznej z datami,
  biblioteki i narzędzia AI, licencje, ograniczenia, weryfikacja), skalowalność, bezpieczeństwo.
