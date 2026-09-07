# Art-direction — Scriptwriter / Storyboarder hero (walk tier)

- **Post:** `walk-01-scriptwriter-storyboarder.md`
- **Placement:** top hero, full-width.
- **Aspect ratio:** 16:9 · **image_size:** 2K · **output_filename:** `walk-01-scriptwriter-storyboarder-hero.png`
- **Anchor axis colour:** strong **indigo** structure (the new concept is ADK's `SequentialAgent` +
  `output_key` state passing — the pipeline handoff), with a distinct **purple** accent for the
  session-state handoff (the walk-tier signature), **teal** for the image tool, and an **amber**
  creative spark. This is the first "team of two," so the composition must read as *handoff*.
- **Status:** render pending — queued to the EM credentialed render channel (no stub committed).

## Prompt (paste into Photoshoot / `nanobanana_image_generation`)

> Flat editorial vector illustration, warm and tactile, light paper-grain texture, soft long shadows,
> on a warm off-white background. A left-to-right creative **handoff between two friendly flat-design
> personas**: on the left a **scriptwriter** at a desk finishing a **numbered shot list** (a sheet
> with a tidy 1–6 numbered list, an **amber** idea-spark above their head as the one-line brief
> becomes shots); in the centre the shot-list sheet slides along a clearly drawn **purple hand-off
> ribbon/track** (a labelled channel, evoking passing a note across a shared desk) to the right; on
> the right a **storyboard artist** who turns that list into a **six-panel storyboard** — a neat grid
> of small framed stills, each panel tied by a thin **indigo** connector line back to its matching
> numbered shot (a visible one-to-one shot→frame mapping), with a small **green check** on the
> finished storyboard (verified stills). A single **teal** camera/lens or image-tool glyph sits by the
> artist (the nanobanana still generator). The two personas and the purple ribbon form a clear
> indigo/purple **pipeline spine** across the frame. Modern developer-blog aesthetic, generous
> negative space, upper-left third clear for a title overlay. No text beyond faint indistinct list
> ruling and panel frames (no legible words), no logos, not photoreal, no UI screenshots.

## Theme-compliance checklist (`graphic-theme.md`)
- [ ] **Indigo/purple pipeline spine prominent** — reads as an ordered two-stage handoff (ADK
      `SequentialAgent`); **purple** hand-off ribbon = session-state `output_key` (walk-tier signature)
- [ ] Clear **1:1 mapping** — six numbered shots ↔ six storyboard panels (the post's proof-of-read)
- [ ] Amber *spark* present (Gemini turning the brief into shots) — Gemini axis
- [ ] One **teal** image-tool glyph (nanobanana) — MCP axis (kept single/secondary; MCP is Med here)
- [ ] Green check = verified storyboard stills (verify-by-existence, per shot)
- [ ] Two distinct persona roles (writer + storyboard artist) reading as a *team*, not one agent
- [ ] Flat editorial vector + paper grain; warm off-white ground
- [ ] Upper-left third clear; no legible baked text/logos/UI; not photoreal; 16:9

## Placement note
The most **narrative/left-to-right** hero in the series so far: it must visibly say "one collaborator
hands finished work to the next." The purple ribbon is doing the teaching — it is the picture of
`output_key="shot_list"` → `{shot_list}`. Keep the shot count at **six** so the 1:1 mapping matches
the agent's `K ≤ 6` bound and the validated six-still run.

## Persona-continuity note
Reuse the established flat-vector cast look (consistent with the Photoshoot photographer, Director,
and Music Producer heroes) so the writer + storyboard artist read as new members of the same studio.
The red-umbrella motif is optional here (could appear faintly inside one storyboard panel as a nod)
but not required — the lighthouse-keeper sample brief is the more natural subject for the panels if a
scene is shown.
