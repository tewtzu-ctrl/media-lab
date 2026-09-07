# Plan aprobat — editare videoclip punto.mp4

Status: APROBAT, GATA DE EXECUȚIE. Nicio randare încă rulată. Citește tot
înainte să continui — conversația anterioară care a construit acest plan e
închisă, tot ce contează e scris aici.

Sursa originală: `/Users/teodorfotciuc/Downloads/videoclip punto.mp4`
(NU se atinge niciodată). Copie de lucru deja făcută:
`~/dev/media-lab/in/punto-source.mp4`.

Protocolul de sesiune video (regulile 1-8, furnizate de Teo) se aplică
integral — vezi rezumatul deciziilor mai jos, care înlocuiește nevoia de
a mai pune aceleași întrebări.

---

## Inventarul sursei (deja făcut, nu-l repeta)

| | |
|---|---|
| Container | MOV/MP4 |
| Video | H.264 Baseline, level 3.1, 8-bit, 4:2:0 |
| Rezoluție | 720×1280, verticală, SAR/DAR nespecificate |
| Framerate | 30 fps CONSTANT (confirmat) |
| Culoare | BT.709, progresiv |
| Bitrate video | ~1.87 Mbps |
| GOP | 7 I, 186 P, zero B-frames |
| Audio | AAC-LC, 44.1kHz, stereo, ~63kbps, -25.6 LUFS integrat |
| Durată | 6.433333s exact, 193 cadre video, 279 cadre audio |
| Rotație | fără |

**Ce limitează calitatea: sursa**, categoric. H.264 Baseline, fără B-frames,
fără CABAC. Niciun export nu recuperează detaliu absent din sursă.

---

## Deciziile luate (3 runde de întrebări, toate rezolvate)

1. **Fundaluri**: 6 locații, schimbate la fiecare ~1 secundă, distribuite
   UNIFORM (6.433333s ÷ 6 = 1.072222s fiecare, nu exact 1s + rest).
2. **Corectare corp**: SĂRITĂ complet azi (dorința #3 din cererea inițială).
   Nu există unealtă instalată pentru asta.
3. **Audio**: eliminat COMPLET — fără pistă audio deloc în livrarea finală.
4. **Calitate**: țintă 2160×3840 (portret, NU 3840×2160 landscape — sursa e
   verticală, am întrebat explicit, s-a confirmat portret), 60fps prin
   interpolare de cadre. FĂRĂ upscale AI (kino video-ai-upscale e stricat,
   vezi bug-uri de mai jos) — doar scalare Lanczos în ffmpeg.
5. **Livrare**: un singur fișier (nu master+delivery separat, e un test).
6. **Body correction / AI-look**: risc semnalat explicit lui Teo — subiectul
   se mișcă continuu într-un singur parc static; schimbarea fundalului la
   fiecare secundă va arăta probabil ca un compositing, indiferent de
   execuție. Teo a acceptat riscul (a zis explicit "e doar un test").

### Reperele exacte pentru cele 6 locații (confirmate de Teo)
1. Times Square (dat direct)
2. Tower Bridge, Londra (NU podul propriu-zis "London Bridge")
3. Shanghai — The Bund / skyline (NU Marele Zid, NU Beijing)
4. Shibuya Crossing, Tokyo (NU Tokyo Tower, NU Shinjuku)
5. Arcul de Triumf, București (dat direct) — POZĂ STATICĂ, nu video (vezi
   mai jos de ce)
6. Deșert — dune de nisip stil Sahara (presupunere neconfirmată explicit,
   dar necontrazisă)

---

## Sursele descărcate (deja pe disc, verificate cu curl, licență Pixabay
## Content License — gratuit, fără atribuire, uz comercial permis)

Toate în `~/dev/media-lab/in/backgrounds/`:

| Fișier | Locație | Rezoluție | FPS | Durată |
|---|---|---|---|---|
| `01-times-square.mp4` | Times Square | 2160×3840 (potrivire EXACTĂ cu canvas-ul țintă) | 30 | 17.1s |
| `02-tower-bridge.mp4` | Tower Bridge, Londra | 3840×2160 | 25 | 25.6s |
| `03-shanghai-bund.mp4` | Shanghai, The Bund | 2160×1440 | 30 | 12.2s |
| `04-shibuya.mp4` | Shibuya Crossing | 1920×1080 | 30 | 20.3s |
| `05-bucharest-arch.jpg` | Arcul de Triumf | 1280×891 (JOASĂ — vezi nota) | — | (poză) |
| `06-desert.mp4` | Deșert | 3840×2160 | 29.97 | 20.3s |

**De ce poză, nu video, la Arcul de Triumf**: căutat exhaustiv pe Pixabay,
Pexels, Mixkit, Coverr — niciun clip video liber-licențiat cu monumentul
specific. Videvo are unul, dar blochează accesul programatic (403). Doar
poza găsită, la 1280px — sub ținta de 4K, va fi vizibil mai slabă decât
celelalte 5 segmente după scalare. Teo a acceptat asta explicit.

**Sursele URL originale** (pentru re-descărcare dacă e nevoie, sau atribuire):
- Times Square: https://cdn.pixabay.com/video/2022/06/24/121994-724732238_large.mp4
- Tower Bridge: https://cdn.pixabay.com/video/2022/12/20/143615-784129606_large.mp4
- Shanghai: https://cdn.pixabay.com/video/2024/05/18/212404_large.mp4
- Shibuya: https://cdn.pixabay.com/video/2024/04/11/207611_large.mp4
- Arcul de Triumf (poză): https://cdn.pixabay.com/photo/2017/08/26/17/17/bucharest-2683691_1280.jpg
- Deșert: https://cdn.pixabay.com/video/2025/06/09/284566_large.mp4

---

## Bug-uri upstream descoperite azi (NU le mai investiga, sunt confirmate)

1. **`kino video-ai-upscale` complet stricat pe ffmpeg 9.0.** Folosește intern
   flagul `-vsync 0`, eliminat din ffmpeg (înlocuit cu `-fps_mode`). Eroare
   reprodusă manual: `Unrecognized option 'vsync'. Error splitting the
   argument list: Option not found`. Testat cu clipuri sintetice mici și
   medii, cu și fără alpha, cu model implicit și `--model realesrgan`
   explicit — eșuează identic de fiecare dată.
   **În plus**: chiar dacă ar merge, codul sursă
   (`kinocut/ai_engine/upscale.py`, funcția `_ai_upscale_opencv`) arată că
   NU folosește Real-ESRGAN, ci cade mereu pe FSRCNN (OpenCV DNN Super
   Resolution) — un model mult mai slab, indiferent de `--model` cerut.
   **Decizie**: renunțat la upscale AI. Doar scalare Lanczos în ffmpeg.

2. **`kino composite-layers` produce mereu H.264 la ieșire**, fără control
   de calitate (fără CRF, fără opțiune de codec), indiferent de extensia
   fișierului de output. Testat cu `.mov` — tot H.264 iese.
   **Decizie**: NU se folosește `composite-layers` pentru acest job. Se
   construiește compositing-ul direct în ffmpeg (vezi planul tehnic).

3. **(Cunoscut din sesiuni anterioare, relevant aici)**: `composite-layers`
   plafonează la 25fps intern dar etichetează cu fps-ul cerut. Irelevant
   pentru acest plan fiindcă nu mai folosim `composite-layers` deloc.

---

## PLANUL TEHNIC APROBAT — de executat exact așa

### Etapa 1 — Cutout persoană
```
kino hyperframes-remove-background in/punto-source.mp4 \
  -o work/punto-edit/01-cutout.mov \
  --model u2net_human_seg --quality best
```
Așteptat: ProRes 4444 cu alpha, 720×1280, 30fps, 6.433s.
Estimare: 1-2 minute (quality `best` mai lent decât `fast`, care era
~125ms/cadru pe teste anterioare).

### Etapa 2 — Pregătire 6 fundaluri (ÎN PARALEL, independente)

Segmentare exactă (6.433333 ÷ 6 = 1.072222s fiecare):

| # | Interval | Sursă | Fișier ieșire |
|---|---|---|---|
| 1 | 0.000000 – 1.072222 | `01-times-square.mp4` | `work/punto-edit/02-bg-01.mov` |
| 2 | 1.072222 – 2.144444 | `02-tower-bridge.mp4` | `work/punto-edit/02-bg-02.mov` |
| 3 | 2.144444 – 3.216667 | `03-shanghai-bund.mp4` | `work/punto-edit/02-bg-03.mov` |
| 4 | 3.216667 – 4.288889 | `04-shibuya.mp4` | `work/punto-edit/02-bg-04.mov` |
| 5 | 4.288889 – 5.361111 | `05-bucharest-arch.jpg` | `work/punto-edit/02-bg-05.mov` |
| 6 | 5.361111 – 6.433333 | `06-desert.mp4` | `work/punto-edit/02-bg-06.mov` |

Pentru fiecare sursă VIDEO: alege un punct de start în sursă (evită primele
1-2s, adesea fade-in/logo), taie exact `1.072222`s de acolo, scalează+
cadrează „cover" la 2160×3840 cu Lanczos, encodează ProRes 422 HQ la 30fps.

Filtru cover-fit (sursă landscape → canvas portret):
`scale=-2:3840:flags=lanczos,crop=2160:3840`
(scalează după înălțime la 3840, apoi decupează centrat la lățime 2160)

Times Square e deja 2160×3840 exact — doar trim, fără scale/crop.

Pentru poza Arcul de Triumf (1280×891, landscape): `-loop 1 -t 1.072222`
plus același filtru cover-fit. NOTĂ: scalare ~4.3× de la 891 la 3840 —
segmentul va fi vizibil moale, cum s-a discutat.

Comandă model (ajustează sursa/offset per fundal):
```
ffmpeg -y -ss <offset> -i in/backgrounds/NN-nume.mp4 -t 1.072222 \
  -vf "scale=-2:3840:flags=lanczos,crop=2160:3840,fps=30" \
  -c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le \
  work/punto-edit/02-bg-0N.mov
```

### Etapa 3a — Concatenare fundaluri (stream-copy, zero pierdere)
```
# creezi work/punto-edit/concat-list.txt cu cele 6 fisiere in ordine
ffmpeg -y -f concat -safe 0 -i work/punto-edit/concat-list.txt \
  -c copy work/punto-edit/03-background-track.mov
```
Verifică după: durata trebuie să fie 6.433333s ±0.05s.

### Etapa 3b — Compositing (subiect peste banda de fundal, O SINGURĂ trecere)
```
ffmpeg -y -i work/punto-edit/03-background-track.mov \
  -i work/punto-edit/01-cutout.mov \
  -filter_complex "[1:v]scale=2160:3840[subj];[0:v][subj]overlay=0:0:format=auto" \
  -c:v prores_ks -profile:v 3 -pix_fmt yuv422p10le \
  work/punto-edit/04-composed.mov
```
Scalare subiect: 720×1280 × 3 = 2160×3840 — potrivire matematică exactă,
fără crop necesar pe subiect.

**STOP AICI pentru verificare vizuală** (regula 7 din protocol). Extrage
câte un cadru din mijlocul fiecărui segment (la ~0.5s, ~1.6s, ~2.7s, ~3.75s,
~4.8s, ~5.9s), arată-le lui Teo, așteaptă confirmare explicită înainte de
Etapa 4.

### Etapa 4 — Interpolare 30→60fps + encodare finală (O SINGURĂ trecere,
### cea mai costisitoare, NU pornești fără aprobare pe cadrele de test)
```
ffmpeg -y -i work/punto-edit/04-composed.mov \
  -vf "minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:vsbmd=1:mb_size=8" \
  -an \
  -c:v libx264 -profile:v high -preset slow -crf 17 \
  -pix_fmt yuv420p -movflags +faststart \
  out/punto-final_2160x3840_60fps_h264-crf17.mp4
```
Alternativ H.265 10-bit dacă Teo preferă fișier mai mic (întreabă dacă nu
s-a decis explicit — NU s-a decis explicit, doar propus H.264 ca implicit).

Estimare: 3-8 minute, incertă (minterpolate pe 3840px lățime + preset slow
sunt ambele grele). Fără estimare mai precisă până nu rulează efectiv.

### Control de calitate obligatoriu după Etapa 4 (regula 6 din protocol)
- ffprobe pe ieșire: rezoluție 2160×3840, 60fps, H.264 High, yuv420p
- durată = 6.433333s ±0.1s (interpolarea nu trebuie să schimbe durata)
- FĂRĂ pistă audio (verifică explicit că nu există stream audio)
- extrage cadre la început/mijloc/sfârșit, verifică artefacte de
  interpolare (ghosting, warping) mai ales la cele 5 tranziții între
  segmente de fundal
- verifică cele 6 tranziții de fundal — pot avea 1 cadru interpolat ciudat
  la fiecare graniță (minterpolate poate face artefacte pe schimbare de
  scenă); e un risc cunoscut, nu o eroare de execuție dacă apare minor

---

## Nerezolvat / de întrebat dacă apare

- Codec final: H.264 propus ca implicit, NU confirmat explicit de Teo.
  Întreabă dacă vrea H.265 în schimb, înainte de Etapa 4.
- Offset-urile exacte de start în fiecare sursă video (unde anume tai cele
  1.072s) nu au fost alese încă — alege puncte fără fade-in/watermark
  vizibil, verifică vizual înainte de a le fixa în Etapa 2.

## Ce NU face acest plan (explicit, per regula 1 a protocolului)
- Nicio corecție de culoare, stabilizare, muzică, text, tranziții
  suplimentare — doar ce s-a cerut.
- Niciun fișier master separat.
- Nicio corectare a defectelor corporale.

---

## Progres execuție (bifat pe măsură ce rulează)

- [x] Etapa 1 — Cutout persoană (`work/punto-edit/01-cutout.mov`)
- [x] Etapa 2 — 6 fundaluri pregătite (offset-uri: TS 3.0s, Tower 5.0s, Shanghai 3.0s, Shibuya 4.0s, Arc still, Desert 4.0s) (`work/punto-edit/02-bg-0N.mov`)
- [x] Etapa 3a — Concatenare fundaluri (192 cadre / 6.4s) (`work/punto-edit/03-background-track.mov`)
- [x] Etapa 3b — Compositing (193 cadre / 6.433333s) (`work/punto-edit/04-composed.mov`)
- [ ] **STOP** — verificare vizuală 6 cadre, aprobare Teo  <-- AICI SUNTEM
- [ ] Etapa 4 — Interpolare 30→60fps + H.264 CRF 17 (`out/punto-final_2160x3840_60fps_h264-crf17.mp4`)
- [ ] QC final (ffprobe + verify-render)

### Note de execuție
- Se lucrează în `~/dev/media-lab` (proiectul media-lab existent). Intermediari în `work/punto-edit/`, livrare în `out/`.
- `ffmpeg`/`ffprobe`: binarele statice din `./bin/` (nu sunt pe PATH — se rulează cu `PATH="$PWD/bin:$PATH"`).
- `kino`: din `.venv` a proiectului.
