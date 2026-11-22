# Promo video – production handoff

Goal: a demo/promo video of HydroSoil, **max 2:00** (the contest allows 3:00), 16:9 1920×1080,
Polish AI voice-over + music. It is built in code with **Claude Code + Remotion**, and the screen
clips are recorded automatically with **Playwright** against https://hydrosoil.kodlab.pl.

Existing long script (3:00, source of truth for scenes and test links): [`video-script.md`](video-script.md).

## Decisions already made

| Topic | Decision |
|---|---|
| Format | 16:9 1920×1080, 30 fps, single version (no 9:16) |
| Length | ≤ 2:00 |
| Sound | Polish voice-over from ElevenLabs + licensed background music (ducked under voice) |
| Clips | Recorded by a Playwright script (devDependency of the video project), not by hand |
| Account scene | Existing test account with 3–4 saved parcels; credentials via `.env`, never committed |
| Project location | Separate folder **outside this repo**, e.g. `~/Documents/hacknation-video` |
| Model | Claude Opus for scene planning and animation; Sonnet is enough for small fixes |

## Message and must-show features

One-line message: **„W 30 sekund rolnik wie, czy brakuje mu wody, dlaczego, i gdzie dokładnie na swoim polu ile wody może zatrzymać.”**

Show, in order of importance:

1. **„Puść ulewę 30 mm”**: „Dziś” vs „Z planem”, m³ counters.
2. **„Rzeźba terenu”**: LIDAR 1 m hillshade, hollows, flow paths, ditches, weirs.
3. **Science + free, trustworthy data → deterministic recommendations**: no AI/ML, FAO-56,
   Saxton & Rawls, IUNG SMSR, LIDAR GUGiK, source "votes", EDO agreement, links + licences.
4. **Login → „Moje działki”** with properly named parcels, „Analiza zbiorcza”.
5. Search by **address**, not only parcel ID.
6. Analysis for **any date up to 10 years back** (e.g. 20.07.2019 drought).

The jury scores (Regulamin §3.4): practical value 25%, data/science correctness 25%,
innovation 20%, ease of use 15%, working prototype 15%. The video must also show
(Pełna treść 3–4): parcel ID or map → crop + date → water status + causes →
retention/agrotech/irrigation recommendations justified by data → date, sources and limitations.

## Scene plan (≤ 2:00)

| Time | Scene | Clip / visual |
|---|---|---|
| 0:00–0:05 | Hook: rain animation on the parcel, water stays on the field | clip `ulewa` (Z planem), zoomed |
| 0:05–0:12 | Problem + message | kinetic title on map of Poland |
| 0:12–0:27 | Input: type an **address**, pick parcel, crop „Kukurydza na ziarno”, date 20.07.2019, „Analizuj działkę”, sources tick off | clip `input` |
| 0:27–0:42 | Verdict „Silny niedobór wody”, soil water tank, source votes, causes in mm | clip `verdict` |
| 0:42–0:58 | **Rzeźba terenu**: LIDAR micro-relief, hollows, ditches, weirs | clip `relief` |
| 0:58–1:15 | **Puść ulewę 30 mm**: „Dziś” then „Z planem”, counters | clip `ulewa` |
| 1:15–1:30 | Recommendations (retention first, irrigation last with m³, cost, permit) | clip `recommendations` |
| 1:30–1:42 | Science & data: method/source cards, „bez AI, deterministycznie”, EDO „zgodne” | Remotion cards + clip `evidence` |
| 1:42–1:52 | Login → „Moje działki”, „Analiza zbiorcza” | clip `account` |
| 1:52–2:00 | PDF report flash, logo, claim, URL hydrosoil.kodlab.pl | clip `pdf` + end card |

Test links (warm the cache by opening each once before recording):

- A: `https://hydrosoil.kodlab.pl/#p=040706_5.0016.51%2F1&c=zboza_ozime&d=2025-06-15`
- B: `https://hydrosoil.kodlab.pl/#p=040706_5.0016.51%2F1&c=kukurydza_ziarno&d=2019-07-20`
- C: `https://hydrosoil.kodlab.pl/#p=061704_2.0003.2661&c=zboza_ozime&d=<today>`

## Voice-over draft (PL, ~2:00 at a calm pace, ~260 words)

Adjust timings after generating audio; scenes follow the audio, not the other way round.

1. „Ulewa. Trzydzieści milimetrów. Pytanie brzmi: ile tej wody zostanie na Twoim polu?”
2. „HydroSoil w trzydzieści sekund mówi rolnikowi, czy brakuje mu wody, dlaczego, i gdzie dokładnie na swoim polu może ją zatrzymać.”
3. „Wpisuję adres albo numer działki, wybieram uprawę i datę, nawet dziesięć lat wstecz. Na żywo widać, co znalazło każde publiczne źródło danych.”
4. „Lipiec 2019: silny niedobór wody. Zbiornik pokazuje, ile wody zostało w strefie korzeni. Model gleby, bilans opadów i reanaliza wilgotności głosują osobno i wszystkie wskazują suszę. Przyczyny widać w milimetrach.”
5. „Nasz wyróżnik: rzeźba terenu z lotniczego skanowania LIDAR, z dokładnością do metra. Widać niecki, bruzdy i rowy, których nie ma na żadnej mapie, i drogi, którymi ucieka woda.”
6. „Puszczam ulewę. Dziś woda spływa do rowów i ucieka z pola. Z planem, czyli z zastawkami i oczkami w zagłębieniach, ta sama ulewa zostaje na działce. Liczniki pokazują ile, w metrach sześciennych.”
7. „Plan zaczyna się od retencji. Nawadnianie jest na końcu, z ilością wody, kosztem i formalnościami. Każde zalecenie wynika z danych tej działki.”
8. „Bez sztucznej inteligencji. Metody FAO i IUNG, dane LIDAR, satelitarne i meteorologiczne, wszystkie publiczne i darmowe. Każda liczba jest powtarzalna i ma podane źródło.”
9. „Po zalogowaniu rolnik ma swoje działki pod własnymi nazwami i może przeanalizować je wszystkie naraz.”
10. „Raport z źródłami i ograniczeniami zapisze jako PDF. HydroSoil: zatrzymaj wodę na swoim polu. hydrosoil.kodlab.pl”

## Steps

### 1. Accounts and assets (human)

| # | Item | Notes |
|---|---|---|
| 1 | ElevenLabs account | Student plan (GitHub Student Pack offer). Pick a Polish-capable voice, model *Multilingual v2* or newer. Either generate `vo/01.mp3`…`vo/10.mp3` per paragraph in the web UI, or put `ELEVENLABS_API_KEY` in `.env` and let Claude call the API |
| 2 | Music | Licensed track (e.g. YouTube Audio Library, Pixabay Music, Artlist). Note its **BPM**. Calm/inspiring, no vocals |
| 3 | Test account | Login + password with 3–4 saved, **properly named** parcels (e.g. A, C, `120206_2.0008.131`) |

### 2. Project setup

```sh
cd ~/Documents
npx create-video@latest --yes --blank hacknation-video   # do not pass --skills unless your setup allows it
cd hacknation-video
```

Install the Remotion agent skills the way your own setup allows:

- plain: `npx remotion skills add` (or `npx skills add remotion-dev/skills`)
- as a Claude Code plugin: `git-subdir` entry for `remotion-dev/skills` → path
  `skills/remotion-best-practices` (this router skill already contains all other Remotion skills)

Create `.env` (add to `.gitignore`):

```
HYDROSOIL_LOGIN=...
HYDROSOIL_PASSWORD=...
ELEVENLABS_API_KEY=...   # optional
```

Copy brand assets from this repo into `public/brand/`: `frontend/public/` favicon/logo and the
colour tokens + font from `frontend/src/styles/`. Copy `frontend/src/ux_form.png`, `ux_print.png`
if useful.

### 3. Project `CLAUDE.md` (paste into the video project)

```markdown
# HydroSoil promo video – rules

## Format
- 16:9 1920×1080, 30 fps, total ≤ 120 s
- Scene timing follows the voice-over audio in public/vo/

## Structure
1. Hook (0–5 s): the rain simulation keeping water on the field, no logo at the start
2. Problem + one-line message
3. Features, one idea per scene: input (address, date up to 10 years back) → verdict → LIDAR relief → rain simulation → recommendations → science & data → account
4. Logo + tagline + URL (final 5–8 s)

## Motion
- All entrances and exits use spring(), never linear easing or CSS transitions
- The camera is always moving: slow push-in or parallax on UI clips, never a static frame
- Zoom into the element the voice-over talks about; dim or blur the rest
- UI clips sit in a browser frame on a floating panel with a soft shadow
- Major cuts land on music beats (BPM in public/music/README)

## Typography
- Max 5–7 words on screen, high contrast, one font from public/brand
- Short kinetic captions reinforce the voice-over; they do not replace it
- 10% safe zone

## Audio
- Voice-over on top; music ducked to about −18 dB under speech, louder in hook and end card

## Brand and truth
- Colours and fonts only from public/brand
- Only real app screens and real numbers from the recordings; no invented data, logos or testimonials
```

### 4. Recording clips with Playwright

Prompt for Claude Code in the video project:

> Add Playwright as a devDependency. Write `scripts/record.ts` that records each clip from the
> scene plan in `video-production.md` (copy it into the project) as a separate 1920×1080 video
> using `recordVideo`, with deterministic waits for UI states instead of sleeps, and slow,
> human-like typing. Use test links A/B/C, warm them first. Log in with credentials from `.env`
> for the account clip. Convert the webm output to constant-frame-rate 30 fps H.264 mp4
> (`ffmpeg -i in.webm -r 30 -c:v libx264 -crf 16 -pix_fmt yuv420p out.mp4`) into
> `public/clips/<name>.mp4`.

Check every clip by eye. Re-record any clip where a section was still "pending".

### 5. Build the video

Prompt:

> Using the Remotion skills and CLAUDE.md, build the composition: scene plan from
> `video-production.md`, voice-over from `public/vo/`, music from `public/music/`, clips from
> `public/clips/`. First list each clip's useful timestamps, then a storyboard, then implement
> scene by scene. Open Remotion Studio for preview.

Iterate scene by scene in Studio (`npx remotion studio`).

### 6. Render and deliver

```sh
npx remotion render <CompositionId> out/hydrosoil.mp4
```

- Check: ≤ 2:00, audio levels, nothing "pending" on screen, the URL is readable.
- Put the final file (or a link to it) where the submission expects it. The film is a required
  submission element (Pełna treść 4.1). Update README „Materiały” with the link.
