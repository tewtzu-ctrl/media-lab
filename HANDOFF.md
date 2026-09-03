# HANDOFF

**Sesiune:** 2026-09-03 (prima sesiune a proiectului — repo creat de la zero)

**Repo:** https://github.com/tewtzu-ctrl/media-lab (public)

## Ramuri

`main`, `dev` și `feat/local-media-pipeline` — toate la același commit, fiindcă
aceasta e prima sesiune și nu există istoric anterior care să le diferențieze.
Fluxul de acum înainte: lucrezi pe o ramură `feat/*`, o îmbini în `dev`, iar
`dev` ajunge în `main` doar când suita e verde.

## Unde am rămas

`media-lab` e complet și funcțional: 8 comenzi, pipeline cap-coadă, validat pe
material real (clipul `punto.mp4`), nu doar sintetic. Toți pașii 0-7 din
`PLAN.md` sunt implementați, testați și commiși. Code review-ul de sesiune a
fost făcut și **toate constatările au fost reparate** în aceeași sesiune.

## De la ultima închidere

A fost creat skill-ul global `verify-render` (vezi „Unelte" mai jos), trimis la
review, și **reparat**: reviewerul a găsit 2 probleme critice și 4 majore, toate
reproduse și confirmate de mine, toate reparate și retestate în aceeași sesiune.
Nimic din codul `media-lab` nu s-a schimbat. Suita: 144 teste, exit 0, 92%
coverage. `work/` a fost golit (426 MB); `in/` și `out/` sunt intacte.

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

**Niciuna.** Două runde de review, ambele complet rezolvate:

- Runda 1, pe `media-lab`: 12 constatări ale agentului + 6 ale mele, toate reparate.
- Runda 2, pe scriptul skill-ului `verify-render`: 2 critice (traceback necapturat
  la binar neexecutabil; injecție în filtergraph prin `--frame-over`, cu citire
  arbitrară de fișiere locale prin `movie=`) și 4 majore (cadru fantomă raportat
  ca `ok`, `--check-matte` mințind pe fișiere fără alpha, cover art tratat ca
  video, prag de octeți nedocumentat). Toate reproduse, reparate și retestate.
  `bandit` pe script și pe `src/`: doar B404/B603, informaționale.

Din runda 1, două puncte unde am decis altfel decât agentul, cu motivul:

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
- **Skill-ul `verify-render`** (`~/.claude/skills/verify-render/`) — creat în
  această sesiune, tocmai fiindcă scrisesem verificarea manual de vreo șase ori.
  Rulează oriunde, fără instalare, iese cu 0/1 ca să poată bloca un pipeline:
  `python3 ~/.claude/skills/verify-render/scripts/verify_render.py out/final.mp4 \
  --ffmpeg-dir ./bin --duration 6.43 --aspect 9:16 --expect-audio`
  Pentru cutout-uri: `--expect-alpha --check-matte --frame-over magenta`.
  Încapsulează cele trei capcane de mai sus, deci nu le mai redescoperim.

## Întrebări pentru tine

1. Intră E1-E4 în scop? (subtitrări Whisper, separare voce/muzică, upscale,
   loturi de imagini)
2. Ștergem `out/` și `work/` (462 MB de randări de test)?
3. Vrei o comandă `media-lab clean`?
4. Urcăm repo-ul pe GitHub? Până acum am lucrat doar local, cum ai cerut.
5. Pentru clipuri unde persoana ține o placă sau un produs: modelul actual taie
   obiectul. Vrei să investighez o soluție (extra `object-matte` de pe dev tip,
   sau alt model)?
