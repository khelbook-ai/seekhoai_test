---
name: demo-video-generation
description: >
  Produce a polished ~2–3 minute product demo / explainer video for SeekhAI (or any
  app) as a self-contained, auto-playing HTML "explainer video", then render it to a
  real .webm / .mp4 file with an optional background score. Use when someone asks for a
  product tour, launch video, feature walkthrough, or "a video of the app".
metadata:
  type: reference
---

# Demo video generation

How demo/explainer videos are made for this project. The deliverable is **two things**:
1. an **interactive HTML artifact** (published to claude.ai, plays in a browser with sound), and
2. a **rendered video file** (`.webm` → `.mp4`, optionally with a muxed background score).

The canonical implementation lives beside this file: **`seekhai-explainer.html`** (the video)
and **`record.mjs`** (the recorder). Read them before changing the approach.

---

## Why an HTML "explainer video" and not a screen recording

This environment usually has **no ffmpeg, no screen-capture pipeline, and an unstable local
stack**. A true narrated MP4 of the live app can't be produced here. So the video is a
**faithful recreation** of the real screens — built with the app's own styling and **real
course/product data pulled from the DB** — as an animated HTML page. Recreations are also
*cleaner* than live capture (no loading hiccups, exact timing). Then Playwright records it and
a downloaded static ffmpeg finishes the file.

Always confirm this trade-off with the user up front; some may want literal app footage (only
possible on their machine via OBS/Playwright + ffmpeg installed locally).

---

## Design system (grounded in the product)

- **Cinematic single-theme stage.** A fixed 16:9 dark-green "stage" (`--stage:#0d1411`) framed
  like a video, with **light app mockups** inside (`--paper:#fbfbfa`) so the screens look like
  the real product. Accent is the app's green (`--accent-deep:#2f5d50`; on-dark `#37b98a`).
- **Type.** App mockups use `system-ui` (matches the app). A **monospace "agent/terminal"
  motif** (`ui-monospace`) carries the build log, scene labels and code — it fits the subject.
- **Captions live in a top band** and **stream in like a typewriter**; the scene's content is
  **hidden until the caption finishes**, then fades in and animates. (Text first, then boxes.)
- **One scene per feature.** Each scene is a stylized real screen with a single motion moment
  (log streaming, ticks flipping, chips dragged into boxes, a code highlight sliding).
- **An animated mouse cursor** (`#cursor` + click ripple) drives every interaction so it reads
  as someone actually using the app.

---

## The scene engine (in `seekhai-explainer.html`)

Everything is one self-contained file (inline CSS + JS, no external assets — the artifact CSP
blocks them). Key pieces:

- `scenes[]` — ordered list of `{ label, eye, cap, html }`. `html` is a function returning the
  scene's markup; `cap` is the top-band caption; `eye` is the little mono eyebrow.
- `DUR[]` — per-scene seconds (index-aligned to `scenes`). Tune pacing here.
- `show(i)` — renders scene `i`, then `streamCaption(cap, …)`; **only after the caption finishes**
  does it add `.revealed` (fades the `.mock` in) and call `startAnims(i, div)`.
- `startAnims(i, div)` — dispatches per-scene animations (`runOrder`, `runLearn`, `runDrag`,
  `runWalk`, `runRouting`, `runSpark`, prompt typing, build-log streaming).
- Cursor helpers — `centerOf(el)` (coords relative to the stage), `moveCursor`, `clickRipple`.
- Audio — a soft Web-Audio pad + gentle bell arpeggio, started on the Play click.
- Controls — Play cover, mute (♪), restart (⟲), a bottom timeline.
- Honors `prefers-reduced-motion` (drops the motion/loops).

To **add a scene**: write a `xScene()` renderer, add an entry to `scenes[]`, a `DUR` value, and
(if it animates) a `runX(div)` called from `startAnims`.

---

## Rendering to a real file

1. **Record the artifact to `.webm`** (Playwright drives headless Chromium; no system ffmpeg
   needed — the browser screencasts it):
   ```bash
   cd video
   npm i playwright && npx playwright install chromium   # one-time
   node record.mjs                                        # → seekhai-tour.webm
   ```
   Keep `DURATION_MS` in `record.mjs` a few seconds longer than `sum(DUR)`.

2. **Convert to MP4** with a standalone ffmpeg (no Homebrew — download a static arm64 build):
   ```bash
   curl -fsSL -o /tmp/ffmpeg.zip https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip
   (cd /tmp && unzip -o ffmpeg.zip && chmod +x ffmpeg)
   /tmp/ffmpeg -y -i seekhai-tour.webm -c:v libx264 -pix_fmt yuv420p -crf 20 -movflags +faststart seekhai-tour.mp4
   ```

3. **Add a background score** (the recorder can't capture the artifact's Web-Audio, so
   regenerate a simple pad and mux it in):
   ```bash
   /tmp/ffmpeg -y -i seekhai-tour.mp4 -filter_complex \
     "sine=frequency=110[a];sine=frequency=164.81[b];sine=frequency=246.94[c];\
      [a][b][c]amix=inputs=3:duration=longest:normalize=0,volume=0.09,tremolo=f=0.1:d=0.4,\
      aecho=0.8:0.4:55|95:0.22|0.18,lowpass=f=1400,afade=t=in:st=0:d=4,afade=t=out:st=174:d=5[au]" \
     -map 0:v -map "[au]" -c:v copy -c:a aac -b:a 160k -shortest seekhai-tour-with-music.mp4
   ```

**Audio caveats:** the `.webm`/silent `.mp4` have no sound; the muxed pad is *a* simple score,
not the exact artifact arpeggio. For the *real* soundtrack, the user must screen-record the
artifact link with **OBS Studio** (captures system audio) on their own machine.

---

## Using real data

Pull the actual course from the DB so the video isn't generic. Example (multi-agent course):
```bash
docker compose exec -T backend python - <<'PY'
from app.db import fetchall
c=fetchall("SELECT id,title,raw_prompt FROM courses WHERE title ILIKE %s ORDER BY created_at DESC LIMIT 1", ("%Multi-Agent%",))
# then topics + calibrated_dl, subtopics, interaction-type counts, a real drag-drop payload…
PY
```
Use the real title, prompt, topics, difficulty levels, subtopic names, interaction mix, and a
real interaction (e.g. the drag-drop entities/boxes) so every scene shows genuine content.

---

## Publishing & versioning

- Publish with the **Artifact** tool using the **same file path** to keep one stable URL across
  revisions; load the `artifact-design` skill first.
- Commit `seekhai-explainer.html`, `record.mjs`, and the rendered `.mp4`/`.webm`. Gitignore
  `video/out/` and `video/node_modules/`.

---

## Lessons learned (bake these in — they came from real feedback)

- **Slow the streaming.** Caption typewriter ≈ 50 ms/char; field typing ≈ 10 chars/sec. Fast
  streaming reads as sloppy.
- **Content appears only after its caption finishes streaming.** Gate the `.mock` opacity.
- **Give each interaction enough time.** A scene that ends mid-animation (e.g. cutting off role
  cycling, or an ordering that only does one drag) looks broken. Multi-step interactions need
  ~18–25 s. Check `DUR[i]` ≥ (caption stream + reveal + full animation).
- **Show the mouse.** Hover + click ripple on every interactive scene.
- **Use the product's real, nicer screens** — the detailed curriculum, the full question rail
  with metrics on the right, the code walkthrough — not thin mockups.
- **Don't leak internals / IP.** Keep the build log generic ("searching the web", "writing
  questions", "verifying answers") — no model names, tool names, or vendor specifics.
- **Spell things out for viewers.** e.g. "Difficulty Level 1 to 3", not internal codes like
  "DL1/DL3". Every feature needs on-screen caption text or viewers won't know what they see.
- **Name things realistically.** Uploaded file = a real-looking course file
  (`STAN301 — …​.pdf`), not `deck.pdf`.
- **Put the most important capabilities early** (e.g. "you can also upload a PDF/slide deck"
  right after the prompt), and cut scenes that add no value (a bare sign-in page).
- **Don't over-repeat a persona name** in captions.
- **Landing text is the pitch** — one clear, slightly larger tagline
  ("A highly interactive, personalized, prompt-based educational course builder").
