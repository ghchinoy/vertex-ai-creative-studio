# Illustrations — art-direction + real renders

This directory holds **Nano Banana art-direction** for the series' hero illustrations: the exact
generation prompt, intended placement, aspect ratio, anchor axis colour, and a theme-compliance
checklist for each image. All of it obeys `blog/graphic-theme.md` §4. As of 2026-09-07 the four
crawl-tier heroes also have their **real renders** here beside the art-direction.

## Status: all four crawl-tier heroes rendered ✅ (real, existence-verified — none faked)

The **real** images require the credentialed genmedia stack — the same one the series' own
Photoshoot/Director agents use:

- Vertex AI application-default credentials,
- the genmedia MCP suite **≥ v3.18.1** on `PATH` (`mcp-nanobanana-go`),
- a `GENMEDIA_BUCKET`.

This archivist container does **not** have that stack, so renders were produced on the credentialed
validator env via the authorized **EM render channel** (`vaics-adk-series-em`), existence-verified
there, then dropped beside each art-direction `.md` here. The archivist reviewed each PNG against its
theme-compliance checklist and accepted all four. Per the anti-fake rule (Simulation Trap), **no
placeholder/stub PNG was ever committed** — the `.png` files are the genuine renders.

## Inventory

| File | Post | Aspect | Anchor colour | Render |
|------|------|--------|---------------|--------|
| `00-overview-hero.md` | `00-overview.md` | 16:9 | balanced tri-colour | ✅ `00-overview-hero.png` (2752×1536) |
| `crawl-01-photoshoot-hero.md` | `crawl-01-photoshoot.md` | 16:9 | amber (Gemini-forward) | ✅ `crawl-01-photoshoot-hero.png` (2752×1536) |
| `crawl-02-director-hero.md` | `crawl-02-director.md` | 16:9 | teal (video) + gotcha-orange | ✅ `crawl-02-director-hero.png` (2752×1536) |
| `crawl-03-music-producer-hero.md` | `crawl-03-music-producer.md` | 16:9 | indigo structure + teal (three tools) | ✅ `crawl-03-music-producer-hero.png` (2752×1536) |
| `walk-01-scriptwriter-storyboarder-hero.md` | `walk-01-scriptwriter-storyboarder.md` | 16:9 | indigo/purple pipeline spine (state handoff) | ✅ `walk-01-scriptwriter-storyboarder-hero.png` (2752×1536) |

Per-image render evidence (existence-verification + sizes): `../../briefs/archivist-render-batch-1-evidence.md`.

## How these will be generated (recipe, for whoever runs the credentialed path)

Each art-direction file's **Prompt** block is written to be pasted straight into the Photoshoot
agent (or `nanobanana_image_generation` directly). Suggested call per image:

```
model: gemini-3.1-flash-image   # nanobanana default; leave unset to use it
aspect_ratio: 16:9
image_size: 2K
output_filename: <slug>-hero.png
output_directory: ./ (or gcs_bucket_uri = gs://<bucket>/adk-series-illustrations/)
```

Then **existence-verify** the bytes (this is the series' own discipline) and drop the real
`<slug>-hero.png` beside its `.md` here.
