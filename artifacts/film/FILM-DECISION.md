# FILM DECISION — Option 1 executed

**Decision taken 2026-09-30 by the film reconciler. No approval pending; this is a record, not a request.**

## What I did

**Option 1 — a 90-second re-cut of the existing rendered film, with the four false claims corrected in place.**

Nothing was re-rendered from the HyperFrames compositions. The source film and the whole `rytm-miasta/` project were treated as read-only; the cut is an ffmpeg `select` + `drawbox`/`drawtext` pass over the existing `final/rytm-miasta-1080p.mp4`, encoded once.

- Film: `artifacts/film/sopocka-strona-biznesu-90s.mp4` — 90.000 s, 1920×1080, 30 fps, H.264 High, 0 audio streams, 36 221 114 B, SHA-256 `1b183949…23ce9`
- Poster: `artifacts/film/POSTER.jpg` — frame 86.0 s, the b09 end card
- Evidence: `artifacts/film/frames/C1_t30.0.png`, `C4_t52.0.png`, `C7_t69.0.png`
- Full record: `artifacts/film/RECONCILIATION.md`

## Why option 1 and not 2 or 3

**Not option 3 (drop the film).** Dropping it would have thrown away a genuinely finished, well-crafted 300-second artefact and left the submission with nothing moving. The four false claims are all repairable without a re-render, and a re-render was never needed: every offending string lives in a **fixed-position overlay** whose pixel geometry I measured directly out of the mp4, not out of the HTML.

**Not option 2 (keep 300 s + head card).** Option 2 leaves ~4.5 minutes of uncorrected footage behind a five-second warning, and it keeps claims 1–4 physically on screen where a juror will meet them one at a time and forget the card. The 90-second cut is also worth more to the actual deliverable: the deck is the scored artefact and the pitch is live, so a 90-second film that can be played whole inside a presentation slot beats a five-minute film nobody has time to screen.

**Option 1 was chosen with one deliberate trade.** The audit's §2.4 cut list assumed three of the six b04 category chips would survive. I checked `b04.html`'s timeline: the chips enter at block-local 17.5 s, so a 12-second b04 segment ending at master 97.0 shows **none** of them. I took that. Five of the six chips are unsupportable (the dataset has one MCC), and covering five chips with five legible plates over a moving dolly would have been exactly the illegible-overlay outcome the brief warns against. Ending at 97.0 removes claim 2 by construction and the plate states the constraint instead. The cost is real and it is recorded in `RECONCILIATION.md` §6.10: the film no longer shows any category movement at all.

Two further deviations from the proposed cut list were forced by the film's own timing and are documented in §2 of the reconciliation: **b08 had to move to 245–251** (its privacy labels do not exist before master 245.5 — the proposed 237–243 would have kept none of the block's point), and **b09 had to become its last 13 seconds** (the end card only enters at master 290.05; a head-cut would have dropped the product name and tagline).

## What is still not true, and is still on screen

The film is **reconciled, not clean**. Eight items remain, listed in full in `RECONCILIATION.md` §6. The three a juror is most likely to catch:

1. **„+38 %"** — a self-declared placeholder with no model behind it. There is no evidenced replacement, so it stands; it is now labelled *wartość ilustracyjna* on screen.
2. **The whole calendar grid is one day ahead of the real 2026 week.** I corrected the four 9-July statements; the surrounding grid still shows 18 June 2026 as a Friday when it is a Thursday. Static overlays cannot fix a scrolling calendar.
3. **Photo rights are unconfirmed** and seven photographers are credited by name on the end card. This is the submission's highest legal risk and I cannot resolve it from here.

And one thing I could not do at all: **I have no image input.** No frame of this film has been looked at by me. Every cut point was screened numerically (luminance mean and standard deviation at each in/out) and every correction was verified by differencing the covered rectangle against the original, but **a human must watch the delivered 90 seconds once, end to end, before it is played to a jury.** That is the one open action this decision leaves behind.
