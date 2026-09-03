# PLAN.md — media-lab

Local video/photo editing pipeline for short social clips, built as a typed
wrapper over Kinocut (`kino` CLI). Every render is verified before it is
reported as done.

Working contract: see [REGULI.md](./REGULI.md).

---

## Decizii luate (confirmate de Teo, 2026-09-03)

| Subiect | Decizie |
|---|---|
| Formă proiect | Wrapper propriu peste kinocut, cu teste |
| ffmpeg | Binar static local în `bin/`, NU global |
| Python | 3.12.13 via uv, `.venv` în proiect (`upscale` cere ≤3.12) |
| Module kinocut | bază + `hyperframes` + `image` + `transcribe` + `stems` + `upscale` |
| Interfață unelte | CLI `kino` apelat prin subprocess, NU server MCP |
| Kinocut pinuit la | `1.15.1` |
| hyperframes pinuit la | `0.8.27` |

---

## Ce NU intră în scop (explicit)

- Orice serviciu cloud, API extern, upload sau deploy.
- `video_body_swap` și orice funcție de tip deepfake — nu o expunem în wrapper.
- Generare video AI (text-to-video). Nu rulează util pe 8 GB.
- Decupat OBIECTE (`birefnet-general`). Cere extra `object-matte`, care —
  verificat în docs/PRODUCT_MATTE.md — NU e în pip 1.15.0 publicat, doar pe dev
  tip. Decupăm doar PERSOANE (`u2net_human_seg`).
- Editor grafic / UI. Totul e CLI, condus din chat.
- Server MCP. Decis: CLI.

---

## Nume de comenzi CLI — VERIFICATE (2026-09-03, kinocut 1.15.1)

Rulat `kino --help` pe instalarea reala. 167 comenzi disponibile.
Numele deduse in planul initial, confirmate sau corectate:

| Ce credeam | Real | Stare |
|---|---|---|
| `hyperframes-remove-background` | `hyperframes-remove-background` | confirmat |
| `composite-layers` | `composite-layers` | confirmat |
| `resize` | `resize` | confirmat |
| `filter` | `filter` | confirmat |
| `repurpose` | `repurpose` | confirmat |
| `duck-audio` | **`audio-bed`** | CORECTAT - o singura comanda face ducking + normalizare loudness |
| `release-checkpoint` | **`video-quality-check`** / `video-publish-gate` | CORECTAT - nu exista sub numele presupus |
| `quality-check` | **`video-quality-check`** | CORECTAT |

Alte comenzi confirmate, folosite de pasii de mai jos: `info`, `trim`, `merge`,
`chroma-key`, `add-audio`, `normalize-audio`, `extract-frame`, `color-grade`,
`thumbnail`, `effect-vignette`, `effect-glow`, `effect-noise`,
`video-ai-color-grade`, `image-edit`, `still-grade`, `still-gate`,
`still-package`, `doctor`.

Modele de decupare confirmate prin `kino --format json
hyperframes-remove-background --info`:
- `u2net_human_seg` (implicit, backend hyperframes) - PERSOANE, disponibil acum
- `birefnet-general` (backend kinocut-onnx) - obiecte, cere extra `object-matte`, in afara scopului

---

## Ordinea de implementare

Pasul 0 e prerechizit pentru tot. Pasul 1 e fundația pe care se sprijină
pașii 2-7. Pașii 2-6 sunt independenți între ei și pot fi reordonați.
Pasul 7 depinde de 2-6.

---

## Pas 0 — Setup mediu (FAZA 3)

**Depinde de:** nimic.

**Ce se face:**
- `bin/` — ffmpeg + ffprobe static (Apple Silicon), versiune notată în README
- `.venv` via `uv`, Python 3.12.13
- `pyproject.toml` — kinocut==1.15.1 cu extras, ruff, mypy, pytest, pytest-cov
- `uv.lock` commis
- `node_modules/` local — `hyperframes@0.8.27`, plus `package.json`/`package-lock.json`
- `.gitignore` — `.venv`, `node_modules`, `bin/`, `in/`, `out/`, `.env`, `__pycache__`, `.pytest_cache`
- `.env.example` — documentat, cu toate cheile
- `Makefile` — `setup`, `test`, `lint`, `typecheck`, `check`
- `git init` + primul commit

**Fișiere atinse:** `pyproject.toml`, `uv.lock`, `package.json`, `package-lock.json`,
`.gitignore`, `.env.example`, `Makefile`, `bin/`, `README.md`

**Teste:** `tests/test_setup.py` — un test trivial care trece, ca să confirm că
infrastructura de test funcționează (cerut de 3.5).

**Notă onestă despre secrete:** proiectul e 100% local și nu are nicio cheie
API. `.env` va conține doar căi și praguri (`MEDIA_LAB_FFMPEG_DIR`,
`MEDIA_LAB_IN_DIR`, `MEDIA_LAB_OUT_DIR`, `MEDIA_LAB_KINO_TIMEOUT_S`,
`MCP_VIDEO_HYPERFRAMES_COMMAND`). Nu inventez secrete ca să bifez regula 0.6.

**Verificare (rulat efectiv):** `ffmpeg -version`, `kino --version`,
`npx hyperframes --version`, `make check`.

---

## Pas 1 — Schelet: config, runner kino, verificare

**Depinde de:** Pas 0.

**Ce se face:**
- `src/media_lab/config.py` — citește env, validează LA PORNIRE, crapă explicit
  dacă lipsește ffmpeg sau kino. Valori implicite sensibile.
- `src/media_lab/kino.py` — un singur loc care apelează `kino` prin subprocess:
  timeout, cod de ieșire, stderr capturat, erori tipizate. Nicio comandă `kino`
  nu se apelează din altă parte.
- `src/media_lab/verify.py` — după fiecare randare: ffprobe pe output
  (durată, rezoluție, fps, prezență audio, canal alpha) + extras un cadru
  pentru inspecție vizuală. Ridică eroare dacă output-ul nu respectă
  așteptările. **Ăsta e stratul anti-rateuri.**
- `src/media_lab/paths.py` — non-distructiv: sursele din `in/` nu se ating
  NICIODATĂ, tot se scrie în `out/`. Refuză să scrie peste un fișier existent
  fără `--force`.
- `src/media_lab/cli.py` — entry point, deocamdată doar `media-lab doctor`

**Fișiere atinse:** cele de mai sus + `tests/`

**Teste:** config lipsă/invalid; kino inexistent; timeout; ffprobe pe fișier
corupt; refuz de suprascriere; refuz de scriere în `in/`.

**Livrabil:** `media-lab doctor` raportează starea reală a mediului.

---

## Pas 2 — `cutout`: decupat persoana de pe fundal

**Depinde de:** Pas 1.

**Ce se face:** `src/media_lab/recipes/cutout.py` — wrapper peste
`kino hyperframes-remove-background` (model `u2net_human_seg`). Merge pe video
și pe imagini. Output cu alpha păstrat.

**Teste:** clip sintetic scurt generat cu ffmpeg lavfi; verificare că output-ul
are canal alpha; input inexistent; input fără persoană (comportament declarat,
nu ascuns); format neacceptat.

**Livrabil:** `media-lab cutout in/clip.mp4 -o out/cutout.webm`

---

## Pas 3 — `backdrop`: fundal nou + compositing

**Depinde de:** Pas 2.

**Ce se face:** `src/media_lab/recipes/backdrop.py` — construiește spec-ul de
layere și apelează `kino composite-layers`. Fundal imagine sau video.
Validează că fundalul și subiectul au rezoluții compatibile; nu redimensionează
tăcut, ci raportează.

**Teste:** fundal imagine; fundal video mai scurt decât subiectul; rezoluții
diferite; fundal lipsă.

**Livrabil:** `media-lab backdrop out/cutout.webm --bg in/bg.jpg -o out/composed.mp4`

---

## Pas 4 — `filters`: filtre și color grading

**Depinde de:** Pas 1.

**Ce se face:** `src/media_lab/recipes/filters.py` — set restrâns de filtre
expuse controlat, cu parametri validați și limitați (nu pasăm valori brute în
ffmpeg). Include vignette, grain, glow, saturație, contrast, color grade.

**Teste:** parametru în afara intervalului; filtru inexistent; lanț de 2 filtre;
input fără video stream.

**Livrabil:** `media-lab filter out/composed.mp4 --preset warm -o out/graded.mp4`

---

## Pas 5 — `music`: muzică de fundal cu ducking

**Depinde de:** Pas 1.

**Ce se face:** `src/media_lab/recipes/audio_bed.py` — muzica coboară automat
sub voce (sidechain ducking), normalizare EBU R128. Verifică LUFS-ul final cu
ffprobe/loudnorm și raportează valoarea reală.

**Teste:** video fără pistă audio; muzică mai scurtă decât clipul (loop);
muzică mai lungă (trim + fade); LUFS țintă atins.

**Livrabil:** `media-lab music out/graded.mp4 --track in/song.mp3 -o out/mixed.mp4`

---

## Pas 6 — `short`: export vertical 9:16 + quality gate

**Depinde de:** Pas 1.

**Ce se face:** `src/media_lab/recipes/to_short.py` — reîncadrare 9:16,
export, apoi quality gate înainte de a declara gata (luminozitate, contrast,
nivel audio, thumbnail).

**Teste:** sursă 16:9; sursă deja verticală; sursă pătrată; clip care pică
quality gate-ul (trebuie să RAPORTEZE, nu să treacă tăcut).

**Livrabil:** `media-lab short out/mixed.mp4 -o out/final_9x16.mp4`

---

## Pas 7 — `pipeline`: fluxul complet într-o comandă

**Depinde de:** Pașii 2-6.

**Ce se face:** `src/media_lab/pipeline.py` — înlănțuie cutout → backdrop →
filter → music → short. Fișiere intermediare într-un folder de lucru,
păstrate pentru inspecție. Dacă un pas pică, se oprește și raportează exact
unde, fără să șteargă ce s-a produs până acolo.

**Teste:** flux complet pe clip sintetic; eșec la pasul 3 din 5 (oprire curată);
reluare; verificare că `in/` a rămas neatins.

**Livrabil:**
`media-lab pipeline in/clip.mp4 --bg in/bg.jpg --track in/song.mp3 -o out/`

---

## Extensii — NU intră în scop până nu le confirmi

Ai instalat modulele, dar nu mi-ai cerut comenzi pentru ele. Le las în afara
planului până zici tu:

- **E1 — `subtitles`**: transcriere Whisper + subtitrări arse (modul `transcribe`)
- **E2 — `stems`**: separare voce/muzică (modul `stems`)
- **E3 — `upscale`**: mărire AI (modul `upscale`)
- **E4 — `photo`**: procesare pe loturi de imagini

---

## Definiția de „terminat" pentru fiecare pas

1. Implementare completă, fără stub-uri
2. Teste: happy path + minim 2 cazuri limită + 1 caz de eroare
3. `make check` verde (pytest + ruff + mypy), coverage ≥ 80%
4. Rezultatul real al rulării, lipit în raport
5. Commit atomic `feat:` / `fix:` / `chore:`
6. Raport: ce am făcut / ce am rulat / rezultatul real / ce urmează
