# Ad creative-director's assistant — a real multi-agent app

> **The capstone.** This is the last and largest agent in the series. It reuses
> the same eight-section template as the rest (**What you'll build · What you'll
> learn · Prerequisites · Run it · How it works · The gotcha this teaches · See
> also · Next in the series**), but where the earlier agents each wired one or a
> few tools, this one **composes the agents you already built**.

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

### Keeping the audio in sync (the one local helper)

There is exactly one spot where the assembler does *not* call an MCP tool. The
reused Music Producer's Lyria bed is a **fixed ~30-second clip** —
`lyria_generate_music` has no duration parameter — and avtool always mixes with
`amix=duration=longest` and exposes no `-shortest`/trim option
([`mcp_handlers.go:485`](../../../mcp-genmedia-go/mcp-avtool-go/mcp_handlers.go)
in combine, `:1310` in layer). So mixing a 30s bed onto a 20s video and combining
directly yields a **~30s file** whose last ~10s is audio over a frozen/black
tail. Since modifying the shared avtool server is out of scope for this example,
the assembler fills the gap with a tiny local helper,
`trim_audio_to_video_length` — a plain Python function ADK auto-wraps as a
`FunctionTool` — that shells the already-required `ffprobe`/`ffmpeg` to cut the
mixed audio to the concatenated-video duration (`-t`) before the final combine.
It keeps both streams and never touches the video. Real pipelines are full of
these seams where a managed tool doesn't expose the one flag you need; the honest
move is a small, well-labelled local step, not pretending the gap isn't there.

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
frozen dataclass in `profiles.py`) selects the planner's persona, the plan schema
(`AdPlan`), what each shot slot produces, and the assembler recipe. **This project
ships the `ad` profile only** — the seam is a thin internal factory so the same
engine can grow a second audience later without reshaping the graph. It is
deliberately a plain-Python dataclass + factory, **not** ADK's `from_config` /
`AgentConfig` YAML, which is `@deprecated` *and* `@experimental` in ADK 2.8.0.

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

## Next in the series

You've reached the capstone — head back to the [series overview](../README.md)
to see the whole arc, from a nine-line single-tool agent to this multi-agent ad
pipeline. From here, the natural extensions (an optional `LoopAgent` QC stage, or
a second planner profile) build directly on the profile seam and the reuse
pattern you just saw.
