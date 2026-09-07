# Ad creative-director's assistant — a real multi-agent app (+ Creative Studio)

> **The capstone — and a small engine.** This is the last and largest agent in
> the series. It reuses the same eight-section template as the rest (**What
> you'll build · What you'll learn · Prerequisites · Run it · How it works · The
> gotcha this teaches · See also · Next in the series**), but where the earlier
> agents each wired one or a few tools, this one **composes the agents you
> already built**.
>
> It is also **one engine that serves two audiences through a plain-Python
> profile factory** — `build_root_agent(profile)`:
> - the **`ad`** profile (the capstone below): a brand brief → one assembled
>   short video ad. It is the **default** (`root_agent = build_root_agent(AD_PROFILE)`),
>   so `adk web` loads it unchanged. Read this first — it teaches the graph.
> - the **`storyboard`** profile ("**Creative Studio**"): an editorial, stills-only
>   animatic + a machine-readable **package + `manifest.json`**, run through a
>   **headless CLI**. It is the series' *dogfood* tool ("we built this to write
>   about itself"). See **[Creative Studio — the storyboard profile](#creative-studio--the-storyboard-profile-dogfood)**.

## What you'll build

An ad creative-director's assistant. You give it a **brand brief** and a
**target duration** (anywhere from 15 seconds to 2 minutes) — *"a 20-second ad
for Aurora, a cold-brew coffee brand; bright, optimistic, ends on the can"* — and
it produces **one assembled short video ad**: a duration-budgeted shot plan, a
still and a motion clip for each hero shot, a music bed, a voiceover, and a final
`.mp4` that concatenates the clips with the audio mixed over them — every
intermediate artifact verified to exist.

It does this by **orchestrating the crawl-tier personas you already shipped** —
[Photoshoot](../photoshoot/) (stills), [Director /
Videographer](../director-videographer/) (clips), and [Music
Producer](../music-producer/) (music + voice) — as callable tools. It composes
them; it does not re-implement them.

## What you'll learn

**The new ADK concepts: a `SequentialAgent` spine that contains a `ParallelAgent`
fan-out, agents reused as tools via `AgentTool`, and a planner whose reply is a
schema-validated JSON plan via `output_schema`.** Concretely:

- **`SequentialAgent` ⊃ `ParallelAgent`.** The top-level pipeline runs its four
  stages in order; stage two is itself a parallel agent that generates several
  shots at once, sharing session state.
- **`AgentTool` — reuse, don't re-author.** Each crawl persona is wrapped with
  `AgentTool` and handed to the stage that needs it. The photoshoot/director/
  music-producer *instructions and tool wiring live in their own projects*; this
  capstone imports their `root_agent` objects and calls them.
- **`output_schema` — a plan that is data, not prose.** The planner emits an
  `AdPlan` (a Pydantic model), so the downstream stages read a guaranteed shape
  from `state["ad_plan"]` instead of parsing free text.
- **The static-fan-out constraint.** `ParallelAgent`'s sub-agent list is fixed at
  build time — you'll see how to reconcile that with a runtime-variable shot
  count.

## Prerequisites

- **Python ≥ 3.13** and [`uv`](https://docs.astral.sh/uv/).
- **The genmedia MCP suite ≥ v3.18.1, installed on your `PATH`.** This is the one
  agent that exercises **every** server: it calls (directly or through the reused
  personas) `mcp-nanobanana-go`, `mcp-veo-go`, `mcp-lyria-go`, `mcp-gemini-go`,
  and `mcp-avtool-go`. Install them from the suite's
  [`install.sh`](../../../mcp-genmedia-go/install.sh); confirm they're reachable:
  ```bash
  for b in mcp-nanobanana-go mcp-veo-go mcp-lyria-go mcp-gemini-go mcp-avtool-go; do which $b; done
  ```
  The suite **must be ≥ v3.18.1** — older builds don't return usable Lyria audio
  and don't give avtool a muxable container.
- **`ffmpeg` and `ffprobe` on your `PATH`** — avtool is transform-only and shells
  out to them for the final assembly.
- **A Google Cloud project with Vertex AI enabled**, and application-default
  credentials (`gcloud auth application-default login`).
- **The sibling example dirs must be present.** This capstone composes them, so
  [`photoshoot/`](../photoshoot/), [`director-videographer/`](../director-videographer/),
  and [`music-producer/`](../music-producer/) must sit next to this project in the
  `adk-genmedia-series/` tree (they do in a normal checkout). See **How it works**
  for why. If one is missing, the agent fails at import with an actionable message.
- **Environment variables** — copy `.env.example` to `.env` and fill in:
  - `GOOGLE_CLOUD_PROJECT` — your project id.
  - `GOOGLE_CLOUD_LOCATION="global"` — `gemini-3.8-flash` and the default Lyria
    model are served globally.
  - `GOOGLE_GENAI_USE_VERTEXAI="True"` — use the Vertex backend.
  - `GENMEDIA_BUCKET` — a **real** bucket name (no `gs://`). Veo (the clips)
    always writes to GCS, so this fallback matters here. A placeholder URI 403s.

## Run it

```bash
cp .env.example .env      # then edit .env with your values
uv sync                   # create the venv and install google-adk[gcp,mcp]
source .venv/bin/activate
adk web                   # open the printed URL, pick "ad_creative_director_ad"
```

Try this sample brief (name your duration explicitly):

> Make a 20-second ad for **Aurora**, a canned cold-brew coffee. Bright and
> optimistic, morning-city energy, and end on a clean shot of the can with the
> tagline "Mornings, brightened." Save artifacts locally.

The assistant will: plan a duration-budgeted 3-shot spine, generate a still then
a clip for each shot (in parallel), generate a music bed and a voiceover, and
assemble the final `./output/final_ad.mp4` — reporting the verified path and the
measured duration.

## How it works

The whole engine is `ad_creative_director/agent.py`, built behind a one-line
factory in `ad_creative_director/profiles.py`. The graph:

```python
SequentialAgent(name="ad_creative_director_ad", sub_agents=[
    planner,                       # LlmAgent(output_schema=AdPlan, output_key="ad_plan")
    ParallelAgent(name="shots", sub_agents=[shot_1, shot_2, shot_3]),
    audio,                         # LlmAgent(tools=[music_producer_tool])
    assembler,                     # LlmAgent(tools=[avtool, trim_audio_to_video_length])
])
root_agent = build_root_agent(AD_PROFILE)   # adk web loads the ad capstone
```

**Stage 1 — the planner** is an `LlmAgent` with an `output_schema` (`AdPlan`) and
`output_key="ad_plan"`, and **no tools and no sub-agents**. From the brief +
duration it emits a schema-validated JSON plan — per-shot `look` / `motion` /
`vo_line` / `duration_seconds`, plus `music_mood` — that ADK writes into
`state["ad_plan"]`. Keeping the planner tool-free keeps the schema enforcement
unambiguous: its only job is to produce the plan.

**Stage 2 — the shot stage** is a `ParallelAgent` of three shot slots that run
concurrently and share session state. Each slot reads *its* shot from the plan
(`shots[i]`), then delegates: it calls the **`photoshoot`** tool for the still,
then the **`director_videographer`** tool for the clip. `ParallelAgent`'s
sub-agent list is **static** (fixed at build time), so we build a fixed number of
slots and each slot no-ops if the plan has fewer shots — see *The gotcha this
teaches*.

**Stage 3 — the audio stage** is an `LlmAgent` that reuses the **`music_producer`**
persona (one `AgentTool`) to generate a music bed from the plan's `music_mood`
and a voiceover from the plan's `vo_line`s.

**Stage 4 — the assembler** is an `LlmAgent` that wires the **avtool** server
directly (final video assembly is a new role no crawl persona covers). It
concatenates the clips, mixes the music bed with the VO, **trims that audio to
the video's length**, lays it over the video, and **verifies the final file by
existence** (media-info + destination listing), never by a returned resource
link. That trim step is the one place this capstone drops below MCP — see
*Keeping the audio in sync* below for why.

### Keeping below MCP honest (the two local helpers)

There are exactly **two** spots in this engine where an assembler does *not* call
an MCP tool. Both are the same honest move — a small, well-labelled local
`ffmpeg`/`ffprobe` step where avtool doesn't expose the one flag you need — and
both live in `agent.py`, documented at their definitions, right below the avtool
wiring:

**1. `trim_audio_to_video_length` (the `ad` profile).** The reused Music
Producer's Lyria bed is a **fixed ~30-second clip** — `lyria_generate_music` has
no duration parameter — and avtool always mixes with `amix=duration=longest` and
exposes no `-shortest`/trim option
([`mcp_handlers.go:485`](../../../mcp-genmedia-go/mcp-avtool-go/mcp_handlers.go)
in combine, `:1310` in layer). So mixing a 30s bed onto a 20s video and combining
directly yields a **~30s file** whose last ~10s is audio over a frozen/black
tail. Since modifying the shared avtool server is out of scope, the assembler
fills the gap with a tiny local helper — a plain Python function ADK auto-wraps
as a `FunctionTool` — that shells the already-required `ffprobe`/`ffmpeg` to cut
the mixed audio to the concatenated-video duration (`-t`) before the final
combine. It keeps both streams and never touches the video.

**2. `build_stills_animatic_slideshow` (the `storyboard` profile).** The
storyboard profile has no Veo clips — it turns the still panels into a slideshow
video. avtool's tool surface transforms and combines *existing* media
(`ffmpeg_combine_audio_and_video`, `ffmpeg_layer_audio_files`,
`ffmpeg_get_media_info`) but has **no "images → timed slideshow" tool**
([`mcp-avtool-go/mcp_handlers.go`](../../../mcp-genmedia-go/mcp-avtool-go/mcp_handlers.go)
registers no such handler). So the assembler builds the slideshow with a second
local helper — same shape as the trim helper — that shells `ffmpeg`'s concat
demuxer over the panel stills, pacing each panel so the slideshow length matches
the narration audio, then hands the result back to avtool to mix and combine. And
because the narration length and the slideshow length still won't match exactly,
the storyboard assembler **reuses the very same `trim_audio_to_video_length`** to
trim before the final combine — one trimmer, two profiles.

Real pipelines are full of these seams where a managed tool doesn't expose the one
flag (or the one operation) you need; the honest move is a small, well-labelled
local step, not pretending the gap isn't there.

### Reuse, not re-implement (and the co-location dependency)

The heart of the capstone is that it **composes the personas you already
taught**. Each crawl persona is its own self-contained `uv` project, so it is
reused like this (`agent.py`, abridged):

```python
# each sibling PROJECT dir is put on sys.path (computed from __file__, not cwd,
# idempotent, and it fails LOUD if a sibling dir is missing)
_SERIES_ROOT = Path(__file__).resolve().parents[2]
for _sibling in ("photoshoot", "director-videographer", "music-producer"):
    ...  # sys.path.insert(0, series_root / sibling)

from photoshoot.agent import root_agent as photoshoot_agent
from director_videographer.agent import root_agent as director_agent
from music_producer.agent import root_agent as music_producer_agent

photoshoot_tool = AgentTool(agent=photoshoot_agent)          # tools/agent_tool.py:109
director_tool   = AgentTool(agent=director_agent)
music_producer_tool = AgentTool(agent=music_producer_agent)
```

`AgentTool` ([`tools/agent_tool.py:109`](https://github.com/google/adk-python/blob/v2.8.0/src/google/adk/tools/agent_tool.py#L109)
@ v2.8.0) wraps an agent so another agent can call it as a tool. When a slot
calls one, `AgentTool` runs the wrapped persona in its **own** runner and session
(seeded with a copy of the caller's state), so the three shot slots can call the
*same* photoshoot/director objects concurrently without stepping on each other.

Because the imports are `photoshoot`, `director_videographer`, `music_producer`,
**this capstone requires those sibling example directories to be present at their
series paths.** That co-location dependency is inherent to a capstone that
composes its siblings — it is not a published library depending on packages, it
is one example directory reusing the example directories next to it. Why `sys.path`
rather than declaring them as dependencies? Each sibling is a runnable example
project, not a buildable/publishable library, so wiring them as package
dependencies would mean restructuring the merged siblings; putting their project
dirs on `sys.path` reuses them verbatim and keeps every example copy-pasteable.
Their only runtime needs — `google-adk` and `python-dotenv` — are already in this
project's own dependencies, so a single `uv sync` here runs the whole thing.

### The profile seam (one internal line)

The engine is built by `build_root_agent(profile=AD_PROFILE)`. A `Profile` (a
frozen dataclass in `profiles.py`) selects the planner's persona, the plan schema,
what each shot slot produces, the assembler recipe, and whether the run emits a
package. **This project ships two profiles** through that one seam — `AD_PROFILE`
(the capstone above) and `STORYBOARD_PROFILE` (**[Creative
Studio](#creative-studio--the-storyboard-profile-dogfood)**, below) — so the same
graph serves two audiences without being reshaped. It is deliberately a
plain-Python dataclass + factory, **not** ADK's `from_config` / `AgentConfig`
YAML, which is `@deprecated` *and* `@experimental` in ADK 2.8.0.

The seam is small on purpose. `AD_PROFILE` keeps the existing behavior exactly —
`shot_media="clips"` (still → Veo clip per shot), `assembler_recipe="video_ad_concat"`,
`plan_schema=AdPlan`, `plan_state_key="ad_plan"`, `emit_package=False` — so
`root_agent = build_root_agent(AD_PROFILE)` and `adk web` are unchanged.
`STORYBOARD_PROFILE` flips exactly the fields it must: `plan_schema=StoryboardPlan`,
`shot_media="stills"` (photoshoot only, **no Veo**), `assembler_recipe="stills_animatic"`,
`plan_state_key="plan"`, `emit_package=True`.

## The gotcha this teaches

**`ParallelAgent` fans out to a *fixed* list of sub-agents, not to a
runtime-determined count — so budget the shots and reconcile the two.**

`ParallelAgent._run_async_impl` iterates `self.sub_agents`
([`agents/parallel_agent.py:266`](https://github.com/google/adk-python/blob/v2.8.0/src/google/adk/agents/parallel_agent.py#L266)
@ v2.8.0); there is no mechanism to spawn one branch per plan shot at runtime.
The plan, however, has a variable number of shots. We reconcile them with a
**fixed shot cap, `MAX_SHOTS = 3`**:

- We build exactly 3 shot slots. Each reads `shots[i]` from the plan if present
  and **no-ops** if the plan has fewer shots. `AdPlan.shots` is bounded to
  `max_length=3`, and the planner instruction states the cap, so the plan never
  asks for a fourth shot that would be silently dropped.
- **Why 3?** Each shot becomes a Veo-3 clip, and Veo-3 supports clip durations of
  **only 4, 6, or 8 seconds**. So 3 shots × {4,6,8}s = **12–24 seconds** of
  distinct hero footage — squarely a short-form / bumper ad, and comfortably
  inside the 15s–2m budget ceiling. The planner allocates the per-shot durations
  to sum near the requested target, up to the 3×8 = 24s hero-footage ceiling; if
  you ask for longer, it plans to the ceiling and tells you rather than inventing
  filler shots. Keeping N small also keeps a demo run fast and cheap (three
  parallel Veo generations is already the heavy part).

This is the honest shape of a static-graph framework meeting a dynamic plan: pick
a cap you can justify against the real constraints (here, the Veo clip-length
grid and the duration budget), enforce it in the schema *and* the instruction,
and make the extra slots degrade gracefully.

> **A benign log quirk you may see.** When the shot slots run in parallel, each
> calls `AgentTool`-wrapped personas that hold stdio `MCPToolset`s, and as those
> concurrent branches finish you may see teardown noise in the logs —
> `ConnectionError: MCP session connection lost` or `BrokenResourceError` — as
> the per-call stdio subprocesses close. It is **harmless**: it is retried and
> blocks no artifact. `AgentTool` already closes its child runner and MCP
> sessions correctly ([`tools/agent_tool.py:340`](https://github.com/google/adk-python/blob/v2.8.0/src/google/adk/tools/agent_tool.py#L340)),
> so this is not a leak in the wiring — it's a concurrency/teardown artifact of
> reusing stdio-MCP agents as tools under a `ParallelAgent`. Nothing to fix.

**And, as everywhere in this series: verify by existence.** The assembler confirms
the final `.mp4` with `ffmpeg_get_media_info` and a destination listing — never a
returned `resource_link`. This matters most here because Veo returns exactly such
a link that is *not* proof of persistence.

Every server this agent touches carries its own quirks — the explicit Veo-3 model
(the default falls back to a Veo-2 model that rejects audio), Lyria's dropped
params and global-only default, avtool needing real inputs + ffmpeg with the
output extension selecting the container, and the gemini TTS 800-char cap. Those
quirks live *inside the reused personas' instructions* (that's the point of
reuse), and the naming crosswalk that spans all of them is
[`../NAMING.md`](../NAMING.md) — this is the agent that exercises the whole
crosswalk.

## Creative Studio — the storyboard profile (dogfood)

The **storyboard** profile turns the same engine into a **Creative Studio**: from
a subject brief it plans a short **editorial storyboard**, generates a **still
panel** per beat (photoshoot only — **no Veo**), lays a music bed and a narration
track, assembles a **stills animatic** (`animatic.mp4`), and — the point of this
profile — emits a **machine-readable package**: a directory of the real media plus
a versioned `manifest.json` that a downstream tool can consume without ever
touching the agent's Python.

This is the series' **dogfood** surface — *"we built the studio to write about
itself."* It runs through a **headless CLI** (no `adk web`), so it is scriptable
and its output is a stable data contract, not a chat transcript.

### Run it (headless)

```bash
uv run python -m ad_creative_director.package \
    --profile storyboard \
    --brief "A quiet three-panel storyboard for a lighthouse keeper at dawn; \
hopeful, cinematic, ends on the lit lamp." \
    --out packages/lighthouse/
```

- `--brief` takes literal text **or** `@path/to/brief.txt`.
- `--out` is optional; it defaults to `packages/<slug>-<UTC-timestamp>/`.
- **Exit code is the contract**: `0` only when **every** expected artifact is
  verified to exist; **non-zero** if any is missing (and the manifest records
  `artifacts_verified: false`). **No stubs, ever** — a missing file is a hard
  failure, not a placeholder. `packages/` is git-ignored.

Prerequisites are the same as the capstone **minus Veo** (the storyboard profile
never calls `mcp-veo-go`) **plus** the deterministic suite-version pin: set
`GENMEDIA_SUITE_VERSION` in `.env` to the suite version you installed (single
source of truth: `mcp-genmedia-go/VERSION`). If unset, the packager falls back to
the series-pinned floor (`3.18.1`). This value is recorded in the manifest
**deterministically — never authored by the LLM.**

**One extra sibling.** The storyboard profile reuses PR-4's beat author, so — on
top of the three siblings the ad capstone needs
([`photoshoot/`](../photoshoot/), [`director-videographer/`](../director-videographer/),
[`music-producer/`](../music-producer/)) — it **also** requires
[`scriptwriter-storyboarder/`](../scriptwriter-storyboarder/) next to this project
(**four** siblings in total). That import is **lazy**: it happens only when the
storyboard planner is built, so the ad capstone / `adk web` never needs this
fourth sibling and its import surface is unchanged. If you run the storyboard CLI
without `scriptwriter-storyboarder/` present, the planner build **fails loud** with
a `RuntimeError` naming the missing sibling.

### Package layout

```
packages/lighthouse/
├── manifest.json        # the versioned contract (read this downstream)
├── plan.json            # the schema-validated planner output (provenance)
├── shots/
│   ├── shot-01.png      # one still panel per storyboard beat
│   ├── shot-02.png
│   └── shot-03.png
├── audio/
│   ├── narration.wav
│   └── music.mp3
└── animatic.mp4         # the assembled stills animatic
```

### The manifest contract (`manifest_version: "1"`)

The manifest is written by a **thin, deterministic, non-LLM packaging function**
(`build_manifest` in `package.py`) that reads the schema-validated plan from
session state, derives each expected artifact path from the shot indices and the
fixed audio/animatic names, and records `verified: <bool>` for each from a real
`os.path.exists` check against the package dir — **never** from a returned
`resource_link`. `artifacts_verified` is `true` **only if every listed path
exists** (an empty plan never verifies). Both `manifest.json` and `plan.json` are
written even on failure, so a bad run leaves an inspectable record of *which*
files were missing.

```jsonc
{
  "manifest_version": "1",      // bump only on a breaking schema change
  "profile": "storyboard",
  "brief": "A quiet three-panel storyboard …",
  "created": "2026-09-07T12:00:00Z",   // UTC, seconds precision, Z-suffixed
  "model": "gemini-3.8-flash",         // engine MODEL, for provenance
  "suite_version": "3.18.1",           // deterministic (GENMEDIA_SUITE_VERSION)
  "subject": "a lighthouse keeper at dawn",
  "music_mood": "hopeful, cinematic",
  "shots": [
    { "index": 1, "beat": "…", "prompt": "…", "image": "shots/shot-01.png", "verified": true }
  ],
  "audio": { "narration": "audio/narration.wav", "music": "audio/music.mp3" },
  "assembled": "animatic.mp4",
  "artifacts_verified": true    // AND of every verified flag above
}
```

A consumer (see the archivist in **See also**) reads **only** `manifest.json` —
a stable, versioned data contract — never the agent's internals. `manifest_version`
is bumped only on a breaking change to this shape.

### How the storyboard profile differs from the capstone

It is the *same graph*; only the profile fields change (see **The profile seam**
above). Concretely: the planner emits a `StoryboardPlan` (no per-shot duration
budget — an editorial board, not a duration-budgeted ad) into `state["plan"]`;
each shot slot produces a **still only** (the photoshoot tool, no director/Veo);
the assembler runs the `stills_animatic` recipe — it builds the slideshow with the
local `build_stills_animatic_slideshow` helper, mixes the audio, **reuses
`trim_audio_to_video_length`** to match the tracks, and combines to `animatic.mp4`
(see **Keeping below MCP honest** above for both local helpers). And
`emit_package=True` is what tells the CLI to run the deterministic packager.

The `ad` capstone is untouched by any of this: `root_agent =
build_root_agent(AD_PROFILE)`, so `adk web` still loads the ad pipeline exactly as
before.

## See also

- **[`countdown-workflow`](../../../../countdown-workflow/)** — a Python pipeline
  that does the same end-to-end job on another surface: script → Nano Banana
  first-frames → continuous Veo clips → validate/select → compose with music
  (with Pydantic-validated data structures). This capstone re-expresses that
  *shape* in ADK primitives (`SequentialAgent` ⊃ `ParallelAgent`, `AgentTool`,
  `output_schema`); read the workflow for the deeper composition craft. Cited,
  not forked.
- **The `story-generator` skill** —
  [`experiments/mcp-genmedia/skills/story-generator/SKILL.md`](../../../skills/story-generator/SKILL.md).
  Its "writers room → per-scene generation" shape — and its "Editor's QC Room"
  self-critique loop — is the storytelling craft behind the planner and the
  (future, optional) QC stage. Read it for the technique; this agent is an
  ADK-runnable surface of the same idea. Cited, not forked.
- **Downstream: the archivist (manifest consumer).** The Creative Studio profile
  exists to be *consumed*, not just watched. A downstream tool — the series'
  archivist, which assembles blog/marketing posts — reads **only** the
  [`manifest.json` contract](#the-manifest-contract-manifest_version-1): it runs
  the CLI (or is handed a finished package dir), then reads the versioned manifest
  for verified artifact paths and provenance (`profile`, `model`, `suite_version`,
  `created`). It never imports this agent's Python and never re-implements the
  pipeline — the dependency is the **stable, versioned data contract over the
  headless entrypoint**, nothing more. That separation is the whole point of the
  deterministic packager: the studio can change internally as long as
  `manifest_version` holds.

## Next in the series

You've reached the capstone — head back to the [series overview](../README.md)
to see the whole arc, from a nine-line single-tool agent to this multi-agent ad
pipeline. This example already grows a **second** audience on the profile seam —
the [Creative Studio storyboard profile](#creative-studio--the-storyboard-profile-dogfood)
and its headless package/manifest dogfood tool. From here, the natural next
extension (an optional `LoopAgent` QC stage) builds directly on the same profile
seam and reuse pattern you just saw.
