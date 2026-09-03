# HANDOFF

**Sesiune:** 2026-09-03 (prima sesiune a proiectului — repo creat de la zero)

## Unde am rămas

`media-lab` e complet și funcțional: 8 comenzi, pipeline cap-coadă, validat pe
material real (clipul `punto.mp4`), nu doar sintetic. Toți pașii 0-7 din
`PLAN.md` sunt implementați, testați și commiși. Code review-ul de sesiune a
fost făcut și **toate constatările au fost reparate** în aceeași sesiune.

## Următorul pas exact

Nu există un pas obligatoriu — proiectul e într-o stare stabilă. Prima acțiune
depinde de ce alegi din „Întrebări":

- Dacă vrei subtitrări: `src/media_lab/recipes/subtitles.py`, funcție nouă
  `burn_subtitles(...)`, peste `kino video-ai-transcribe` + `kino subtitles`.
  Modulul `transcribe` e deja instalat. E pasul E1 din `PLAN.md`.
- Dacă vrei curățenie automată: comandă nouă `clean` în `src/media_lab/cli.py`,
  care golește `work/` (nu `out/`, nu `in/`).

## Ce e blocat

Nimic tehnic. Două lucruri așteaptă o decizie de-a ta:

1. Dacă extensiile E1-E4 din `PLAN.md` (subtitrări, separare audio, upscale,
   loturi de imagini) intră în scop. Modulele sunt instalate, comenzile nu
   există.
2. Dacă ștergem materialul de lucru: `out/` (236 MB) și `work/` (226 MB) conțin
   randări de test din această sesiune. Sunt gitignorate. Nu am șters nimic.

## Din review — probleme rămase nereparate

**Niciuna.** Toate cele 12 constatări ale agentului de review și cele 6 ale mele
au fost reparate în această sesiune, la cererea ta explicită. Două puncte unde
am decis altfel decât agentul, cu motivul:

- `filters.py` (314 linii) — agentul nu a semnalat, eu da. La recitire, 314 e în
  intervalul normal din `coding-style.md` (200-400). Nu am mai spart fișierul;
  o refactorizare cosmetică ar fi introdus risc fără câștig.
- `_ensure_within_bounds` din `filters.py` — agentul cerea unificarea cu
  `validation.check_range`. Am refuzat: aceea validează parametri *interni* ai
  catalogului de look-uri (eroare de programator), nu input de la utilizator, iar
  mesajul ei numește look-ul vinovat. Unificarea ar fi pierdut informație. Motivul
  e scris în docstring.

## Capcane

- **`kino audio-bed` nu merge pe macOS** (cere `os.memfd_create`, API Linux). Nu
  încerca să-l folosești; ducking-ul e implementat în `recipes/audio_bed.py` cu
  ffmpeg. La fel e afectat `body-swap`, care oricum e în afara scopului.
- **Compositorul kinocut plafonează la 25 fps** dar etichetează cu fps-ul cerut.
  `backdrop.py` plafonează canvas-ul; nu scoate plafonul fără să verifici că
  bug-ul upstream s-a rezolvat, altfel clipurile ies scurtate.
- **Cutout-urile video trebuie să fie `.mov`** (ProRes 4444). Pe `.webm`, alpha
  există dar compositorul kinocut nu-l citește și compune subiectul ca dreptunghi
  opac — rezultat greșit care arată plauzibil.
- **`bin/` nu e în git.** După un clone: `./scripts/fetch-ffmpeg.sh` înainte de
  orice.
- **Suita durează câteva minute** — face randări reale cu ProRes. Nu o rula în
  foreground cu timeout scurt.
- ProRes umple `work/` repede: ~214 MB per 6 secunde de material.

## Unelte utile pe proiectul ăsta

- `kino --help` și `kino <comanda> --help` — sursa de adevăr pentru flaguri.
  Numele deduse din uneltele MCP nu corespund întotdeauna (`duck-audio` nu
  există, e `audio-bed`).
- Agentul `python-reviewer` — a găsit 6 probleme majore reale pe care review-ul
  meu manual nu le prinsese. Merită rulat la fiecare sesiune de review.
- Agentul `python-pro` — bun pentru rețete independente scrise în paralel, cu
  condiția să primească flagurile CLI verificate în brief.
- `ffprobe -show_streams` cu `alphaextract,signalstats` — singurul mod onest de
  a verifica dacă un matte chiar există.

## Întrebări pentru tine

1. Intră E1-E4 în scop? (subtitrări Whisper, separare voce/muzică, upscale,
   loturi de imagini)
2. Ștergem `out/` și `work/` (462 MB de randări de test)?
3. Vrei o comandă `media-lab clean`?
4. Urcăm repo-ul pe GitHub? Până acum am lucrat doar local, cum ai cerut.
5. Pentru clipuri unde persoana ține o placă sau un produs: modelul actual taie
   obiectul. Vrei să investighez o soluție (extra `object-matte` de pe dev tip,
   sau alt model)?
