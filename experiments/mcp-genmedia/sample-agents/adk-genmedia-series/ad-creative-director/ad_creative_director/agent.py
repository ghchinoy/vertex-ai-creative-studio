# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Ad creative-director's assistant — the capstone (run tier).

A brand brief + a target duration (15s-2m) in; one assembled short video ad out.
This is the series' "real multi-agent app": a top-level `SequentialAgent` spine
wrapping a `ParallelAgent` per-shot fan-out, that REUSES the crawl personas you
already shipped (Photoshoot, Director, Music Producer) via `AgentTool` — it does
NOT re-author them.

    SequentialAgent(
        planner,                       # LlmAgent + output_schema=AdPlan -> state["ad_plan"]
        shot_stage = ParallelAgent(    # MAX_SHOTS fixed slots, run concurrently
            shot_1, shot_2, shot_3,    #   each: photoshoot still -> director clip (AgentTool)
        ),
        audio_stage,                   # LlmAgent -> music_producer persona (AgentTool): bed + VO
        assembler,                     # LlmAgent -> avtool: concat + mix + trim-to-video + combine, verify
    )

The engine is built behind `build_root_agent(profile=AD_PROFILE)` (see
profiles.py). It ships TWO profiles: the `ad` capstone (default, above) and the
editorial `storyboard` profile (stills-only, board-paced animatic + package/
manifest) reached through the headless `package` CLI (see package.py). Both use
the SAME graph shape; only the per-stage builders branch on the Profile.
`root_agent = build_root_agent(AD_PROFILE)` so `adk web` shows the ad capstone by
default, unchanged.

--------------------------------------------------------------------------------
ADK 2.8.0 constructs used here are source-verified against the installed 2.8.0
(== tag v2.8.0 of github.com/google/adk-python). file:line citations:

  * SequentialAgent  — agents/sequential_agent.py:83 (class); runs its
    sub_agents IN ORDER: `for i in range(start_index, len(self.sub_agents))`
    at :111, sharing one session (state passes via output_key). NOTE it is
    @deprecated in 2.8.0 (:79 "in favor of Workflow") but Workflow "cannot yet
    be used as an LlmAgent sub-agent", so it remains the correct construct and
    is what the merged walk-tier agent already ships.

  * ParallelAgent    — agents/parallel_agent.py:230 (class; @deprecated at :226,
    same caveat as above). Its sub_agents list is STATIC — `_run_async_impl`
    iterates `self.sub_agents` (:266); there is no runtime fan-out to a plan's
    shot count. Sub-agents run CONCURRENTLY via asyncio.TaskGroup
    (`_merge_agent_run` :82, :122) and SHARE session state: each branch ctx is a
    shallow `model_copy()` of the invocation context (:50 in
    `_create_branch_ctx_for_sub_agent` :44) that only changes `branch`, so the
    session (and its `state`) is the same object across branches. -> the fixed
    MAX_SHOTS design below, and each slot reading `shots[i]` if present.

  * AgentTool        — tools/agent_tool.py:109. Wraps an agent so another agent
    can call it as a tool. `run_async` builds its OWN Runner +
    InMemorySessionService (:264) and seeds the child session with a copy of the
    caller's state (:285), so calling the SAME wrapped persona object from
    several concurrent shot slots is isolated (no state clobber).

  * output_schema    — agents/llm_agent.py:404 (field), :415 (docstring). ADK
    validates the final reply against it (`validate_schema` at :1044) and writes
    the result to `state[output_key]` (:1045). For a Pydantic BaseModel the
    stored value is a dict (utils/_schema_utils.py:141-142). The planner has
    NO tools and NO sub_agents — it is a leaf — so the schema enforcement is
    unambiguous; it just emits a validated plan into state.

  * output_key       — agents/llm_agent.py:419 (field); write at :1045.

  * {ad_plan} templating — utils/instructions_utils.py:133 (`_replace_match`)
    reads `session.state["ad_plan"]` (:162) and substitutes `str(value)`; a
    plain (non-`?`) placeholder raises KeyError if absent (:174), which is what
    we want: the planner always runs first, so a missing plan is a real failure.

  * FunctionTool     — tools/function_tool.py:99 (class), :106 (__init__ takes a
    `func` and reads its docstring as the tool description). A bare callable in
    an LlmAgent's `tools` list is auto-wrapped in one: llm_agent.py:206-207
    (`if callable(tool_union): return [FunctionTool(func=tool_union)]`). The
    assembler uses this for its one local helper (see AUDIO/VIDEO DURATION below).

--------------------------------------------------------------------------------
AUDIO/VIDEO DURATION — why the assembler has a small local ffmpeg helper.
The final ad's audio must not run past the visuals. The reused Music Producer's
Lyria produces a FIXED-length (~30s) music bed — `lyria_generate_music` exposes
no duration/length parameter (mcp-lyria-go/lyria.go:128-161: only `prompt` +
model/output params). And avtool's mixing tools always mix with
`amix=...:duration=longest` and expose NO `-shortest`/`-t`/trim option
(mcp-avtool-go/mcp_handlers.go:485 in ffmpeg_combine_audio_and_video, :1310 in
ffmpeg_layer_audio_files), so a 30s bed over a 20s video yields a ~30s file with
a silent/last-frame tail. Modifying the shared avtool server is out of scope, so
the assembler fills that gap itself with `trim_audio_to_video_length` below (a
FunctionTool that shells the already-required ffmpeg/ffprobe — no new dependency)
and runs it on the mixed audio BEFORE the final combine, so the container tracks
the VIDEO length. This is the one spot the capstone drops below MCP, and it is a
deliberate, documented teaching point (README "How it works").
--------------------------------------------------------------------------------
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)

from .profiles import AD_PROFILE, Profile
from .schemas import MAX_SHOTS

load_dotenv()

# Set this to a Gemini model you have access to on your Vertex backend.
# gemini-3.8-flash is served in the GLOBAL region, so keep
# GOOGLE_CLOUD_LOCATION="global" in your .env (see .env.example). The default
# Lyria model reused via the Music Producer persona is also global-only.
MODEL = "gemini-3.8-flash"

project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

# Forward the whole environment to the stdio server, adding PROJECT_ID only when
# it is set. Env values must be strings — passing PROJECT_ID=None (which happens
# when GOOGLE_CLOUD_PROJECT is unset) raises TypeError when the subprocess
# launches, so we guard rather than pass None. Same guarded pattern as the crawl
# agents. (Only the assembler below wires its own MCPToolset directly; the shot
# and audio stages reuse the crawl personas, which each build their own
# server_env exactly like this.)
server_env = dict(os.environ)
if project_id:
    server_env["PROJECT_ID"] = project_id


# --- REUSE, not re-implement: import the merged crawl personas ---------------
# The capstone COMPOSES the crawl agents; it does not re-author them. Each crawl
# agent is its own self-contained uv project (a sibling directory), NOT a
# published library, and the merged sibling projects have no [build-system] in
# their pyproject.toml — so we cannot add them as uv path dependencies without
# modifying merged code we don't own. Instead we put each sibling PROJECT dir on
# sys.path (they all live under the shared series root) and import the persona's
# `root_agent`. Importing does NOT launch any MCP server — MCPToolset connects
# lazily on first tool use — so this is cheap and side-effect-free at import.
#
# CO-LOCATION DEPENDENCY (by design, documented in README): because this capstone
# composes its siblings, it REQUIRES the sibling example dirs to be present at
# their series paths. Paths are computed from __file__ (never cwd), the insert is
# idempotent, and a missing sibling fails LOUD with an actionable message — a
# reader who copied only this dir gets help, not an opaque ImportError.
_SERIES_ROOT = Path(__file__).resolve().parents[2]
# The `storyboard` profile (PR-6) reuses PR-4's scriptwriter-storyboarder too, so
# it is a required sibling of the engine alongside the three the ad profile uses.
for _sibling in (
    "photoshoot",
    "director-videographer",
    "music-producer",
    "scriptwriter-storyboarder",
):
    _project_dir = _SERIES_ROOT / _sibling
    if not _project_dir.is_dir():
        raise RuntimeError(
            "ad-creative-director is the profile-driven engine: it COMPOSES the "
            f"crawl/walk personas and needs the sibling example project "
            f"'{_sibling}/' at {_project_dir}, but that directory is missing. "
            "Check out the whole adk-genmedia-series/ (photoshoot/, "
            "director-videographer/, music-producer/, scriptwriter-storyboarder/ "
            "next to ad-creative-director/), not just this folder. See this "
            "project's README, section 'How it works'."
        )
    if str(_project_dir) not in sys.path:
        sys.path.insert(0, str(_project_dir))

from photoshoot.agent import root_agent as photoshoot_agent  # noqa: E402
from director_videographer.agent import root_agent as director_agent  # noqa: E402
from music_producer.agent import root_agent as music_producer_agent  # noqa: E402
# REUSE PR-4's beat AUTHOR (the scriptwriter LEAF — text only, output_key=
# "shot_list"), NOT the storyboarder image half: in the storyboard profile the
# stills come from the shot stage reusing Photoshoot (addendum §4.4). Importing
# scriptwriter_storyboarder.agent constructs its SequentialAgent, which sets
# `scriptwriter.parent_agent` — that is fine: we reuse `scriptwriter` via
# AgentTool, and AgentTool runs it in its OWN Runner and never adds it to a
# sub_agents list, so there is no "already has a parent agent" conflict
# (base_agent.py:704-712 only fires when an agent is added as a sub_agent).
from scriptwriter_storyboarder.agent import scriptwriter  # noqa: E402

# Wrap each persona as a callable tool. AgentTool(name=agent.name), so the tool
# names the LLM sees are "photoshoot", "director_videographer", "music_producer",
# "scriptwriter". These wrappers are stateless config, safe to share across the
# parallel shot slots (each call gets its own isolated Runner + session; see the
# header).
photoshoot_tool = AgentTool(agent=photoshoot_agent)
director_tool = AgentTool(agent=director_agent)
music_producer_tool = AgentTool(agent=music_producer_agent)
scriptwriter_tool = AgentTool(agent=scriptwriter)


# ============================================================================
# Stage 1 — the planner (LlmAgent + output_schema, NO tools, NO sub_agents)
# ============================================================================
# The construct-level half of the planner instruction. The tone/audience half is
# the profile's `planner_persona`, appended below — that is the only per-profile
# difference in the planner. Note there are NO `{...}` templates here: the
# planner is the FIRST stage and reads the user's brief directly.
PLANNER_BASE = f"""\
You are the creative director for a short video ad. Turn the user's brand brief
and target duration into a duration-budgeted shot plan. You emit a STRUCTURED
plan only — you do not call any tools; later stages generate the media from your
plan.

# The duration budget (respect it precisely)
- The finished ad must be between 15 and 120 seconds (15s-2m).
- You have AT MOST {MAX_SHOTS} hero shots. This is a hard cap: the shot stage has
  exactly {MAX_SHOTS} parallel slots, so a {MAX_SHOTS + 1}th shot would be
  silently dropped. Use fewer shots for a short bumper; never exceed {MAX_SHOTS}.
- Each shot becomes a Veo-3 clip, and Veo-3 supports clip durations of ONLY
  4, 6, or 8 seconds. So every shot's `duration_seconds` MUST be 4, 6, or 8.
- Allocate the per-shot durations so their SUM is as close as possible to the
  requested target, up to the hero-footage ceiling of {MAX_SHOTS} x 8 =
  {MAX_SHOTS * 8}s. If the user asks for longer than {MAX_SHOTS * 8}s, plan to
  the {MAX_SHOTS * 8}s ceiling and tell the user this reference capstone caps
  hero footage at {MAX_SHOTS} shots — do NOT invent extra shots to pad the time.

# What each shot needs
For every shot provide: `look` (still art-direction — subject, composition,
lens, light, mood), `motion` (camera/subject motion for the clip), `vo_line`
(one spoken line), and `duration_seconds` (4, 6, or 8). Keep the combined
voiceover concise: all `vo_line`s together should be well under ~800 characters
(the TTS cap the audio stage honors). Also give the ad a `brand`,
`total_duration_seconds`, and a `music_mood` for the score.

Return ONLY the plan as JSON matching the required schema — no preamble.
"""


# The storyboard planner's construct-level base. Unlike the ad planner it (a)
# has a TOOL — it REUSES PR-4's scriptwriter to author the editorial beats rather
# than re-authoring beat planning from scratch — and (b) has NO duration budget
# (board-paced, addendum §6). `output_schema` (StoryboardPlan) and `tools` are
# used TOGETHER: ADK exposes the tool during the thought loop and enforces the
# schema only on the final reply (llm_agent.py:404-418, docstring verbatim: "The
# ADK supports using output_schema and tools together. It works by exposing tools
# during the thought loop and enforcing structure only on the final output.").
# There are NO `{...}` templates here: the planner is the FIRST stage and reads
# the user's brief directly.
STORYBOARD_PLANNER_BASE = f"""\
You are the planner for an editorial storyboard. Turn the user's brief into a
board-paced storyboard plan of AT MOST {MAX_SHOTS} panels. There is NO ad
duration budget — the story sets the pace, not a clock.

# Author the beats by REUSING the scriptwriter (do not invent them cold)
First call the `scriptwriter` tool with the user's brief to get a numbered shot
list of editorial beats (it returns plain text: Scene / Action / Look per shot).
Use that as the backbone of your plan — it is the series' walk-tier beat author,
and reusing it keeps this profile consistent with what the series already taught.
You MAY tighten or trim it to at most {MAX_SHOTS} panels, but do not discard it
and re-author from scratch.

# Structure the result into the required plan
Turn the scriptwriter's beats into the plan: a `subject` (what the storyboard is
about), a `music_mood` for the bed, and a `shots` list (1..{MAX_SHOTS} panels).
For EACH panel provide: `beat` (the editorial moment), `prompt` (art-direction
for the still — subject, composition, lens, light, mood; this drives the
nanobanana still, there is no motion/clip), and `narration_line` (one neutral,
explanatory voiceover line). Keep the combined narration concise: all
`narration_line`s together should be well under ~800 characters (the TTS cap the
audio stage honors).

Return ONLY the plan as JSON matching the required schema — no preamble.
"""


def _build_planner(profile: Profile) -> LlmAgent:
    # The storyboard profile reuses PR-4's scriptwriter to author beats and emits
    # a StoryboardPlan; the ad profile plans clips with no tools (unchanged).
    if profile.shot_media == "stills":
        return LlmAgent(
            model=MODEL,
            name="storyboard_planner",
            description=(
                "Reuses PR-4's scriptwriter to author editorial beats, then "
                "emits a schema-validated StoryboardPlan into "
                f"state['{profile.plan_state_key}']."
            ),
            instruction=STORYBOARD_PLANNER_BASE + profile.planner_persona,
            tools=[scriptwriter_tool],
            output_schema=profile.plan_schema,
            output_key=profile.plan_state_key,
        )
    return LlmAgent(
        model=MODEL,
        name="creative_director",
        description=(
            "Turns a brand brief + target duration into a schema-validated, "
            f"duration-budgeted shot plan (AdPlan) in state['{profile.plan_state_key}']."
        ),
        instruction=PLANNER_BASE + profile.planner_persona,
        # output_schema makes the reply a schema-validated JSON plan; output_key
        # lands it in state[plan_state_key] for the downstream stages to read.
        output_schema=profile.plan_schema,
        output_key=profile.plan_state_key,
    )


# ============================================================================
# Stage 2 — the shot stage (ParallelAgent with MAX_SHOTS fixed slots)
# ============================================================================
# ADK's ParallelAgent has a STATIC sub_agents list (see header), so we build
# exactly MAX_SHOTS shot slots up front. Each slot reads its own shot index from
# the shared plan and no-ops if the plan has fewer shots. All slots run
# concurrently and share session state.
def _shot_slot_instruction(index: int) -> str:
    # human-friendly 1-based number for prose, 0-based index for array access
    human = index + 1
    return f"""\
You are the unit that produces HERO SHOT {human} of a short video ad. The
creative director's plan is injected below from session state:

<ad_plan>
{{ad_plan}}
</ad_plan>

# 1. Find YOUR shot
Read the plan's `shots` list (0-indexed) and take element [{index}] — that is
YOUR shot ({human}). If the list has fewer than {human} shots, then this slot
has no work: say "shot {human}: no shot in plan" and STOP without calling any
tool. Do NOT borrow another slot's shot and do NOT invent one.

# 2. Generate the still, then the clip (reuse the crawl personas as tools)
You do not generate media yourself — you delegate to two persona tools, in order:

a) `photoshoot` tool — hand it YOUR shot's `look` as a shot description and ask
   it to produce ONE still and save it LOCALLY under ./output with a predictable
   name like `shot-{human:02d}.png` (pass output_directory="./output"). The
   photoshoot persona art-directs, calls nanobanana, and verifies the file by
   existence. Capture the exact local path it reports.

b) `director_videographer` tool — hand it YOUR shot's `motion` plus the still
   from step (a) and ask for an image-to-video (i2v) clip of exactly YOUR shot's
   `duration_seconds` seconds. IMPORTANT constraints to pass through so the clip
   actually renders (the director persona enforces them, but state them):
     - veo_i2v needs the starting image as a gs:// URI, so if your still is
       local, ask the director to use it as the visual reference / first frame;
       if only text motion is available, veo_t2v is acceptable.
     - An explicit Veo-3 model is REQUIRED (the default falls back to a Veo-2
       model that rejects audio and errors). The director defaults to
       veo-3.1-fast-generate-001; keep that unless the plan implies 9:16 (still
       a Veo-3.1 model).
     - duration must be YOUR shot's `duration_seconds` (one of 4/6/8).
   Veo writes to GCS; capture the exact gs:// URI the director verified by
   LISTING the destination (never a bare resource_link).

# 3. Report
End with two labelled lines for shot {human}:
  shot {human} still -> <local path> (verified)
  shot {human} clip  -> <gs:// URI> (verified)
If either step could not be verified, say so plainly for shot {human} — do not
fabricate a path or URI.
"""


# ---------------------------------------------------------------------------
# Stills-only shot slot (storyboard profile). NO director, NO Veo anywhere —
# addendum §6: the storyboard is a stills board (cheaper/faster/deterministic
# docs tool). Each slot reuses ONLY the Photoshoot persona and saves its still
# into the package's shots/ dir with an index-derived name the deterministic
# packager can predict (shot-0N.png). Reads its panel from state[<plan key>]
# and the destination dir from state['shots_dir'] (both seeded by the package
# CLI; see package.py).
def _stills_slot_instruction(index: int, plan_key: str) -> str:
    human = index + 1
    return f"""\
You are the unit that produces STORYBOARD PANEL {human}. The planner's storyboard
plan is injected below from session state, and the destination directory for the
stills is also injected:

<plan>
{{{plan_key}}}
</plan>

Save stills into this directory (an absolute path):
<shots_dir>{{shots_dir}}</shots_dir>

# 1. Find YOUR panel
Read the plan's `shots` list (0-indexed) and take element [{index}] — that is
YOUR panel ({human}). If the list has fewer than {human} shots, then this slot
has no work: say "panel {human}: no shot in plan" and STOP without calling any
tool. Do NOT borrow another slot's panel and do NOT invent one.

# 2. Generate ONE still (reuse the Photoshoot persona as a tool)
Call the `photoshoot` tool with YOUR panel's `prompt` as the shot description.
Tell it to save LOCALLY by passing output_directory="{{shots_dir}}" and
output_filename="shot-{human:02d}.png" so the file lands at
{{shots_dir}}/shot-{human:02d}.png with a predictable name. There is NO clip and
NO video for this profile — do NOT call any director or Veo tool; a still is the
whole job. The Photoshoot persona art-directs, calls nanobanana, and verifies the
file by existence. Capture the exact local path it reports.

# 3. Report
End with one labelled line for panel {human}:
  panel {human} still -> <local path> (verified)
If the still could not be verified, say so plainly for panel {human} — do not
fabricate a path.
"""


def _build_shot_stage(profile: Profile) -> ParallelAgent:
    # profile.shot_media selects what each of the MAX_SHOTS fixed slots produces:
    #   "clips"  -> still (photoshoot) then clip (director): the ad path.
    #   "stills" -> still ONLY (photoshoot), no director/Veo: the storyboard path.
    if profile.shot_media == "stills":
        shot_slots = [
            LlmAgent(
                model=MODEL,
                name=f"panel_{i + 1}",
                description=(
                    f"Produces storyboard panel {i + 1}: a still (photoshoot) "
                    f"only, reading shots[{i}] from the plan; no-ops if absent."
                ),
                instruction=_stills_slot_instruction(i, profile.plan_state_key),
                tools=[photoshoot_tool],
            )
            for i in range(MAX_SHOTS)
        ]
        return ParallelAgent(
            name="panels",
            description=(
                f"Runs {MAX_SHOTS} per-panel slots concurrently; each turns its "
                "plan panel into a verified nanobanana still (no clip/Veo)."
            ),
            sub_agents=shot_slots,
        )

    # profile.shot_media == "clips" — the ad path (unchanged from PR-5).
    shot_slots = [
        LlmAgent(
            model=MODEL,
            name=f"shot_{i + 1}",
            description=(
                f"Produces hero shot {i + 1}: a still (photoshoot) then a clip "
                f"(director), reading shots[{i}] from the plan; no-ops if absent."
            ),
            instruction=_shot_slot_instruction(i),
            tools=[photoshoot_tool, director_tool],
        )
        for i in range(MAX_SHOTS)
    ]
    # KNOWN QUIRK (benign, no fix needed): running several shot slots
    # concurrently, each calling AgentTool-wrapped personas that hold stdio
    # MCPToolsets, can emit teardown noise in the logs as the parallel branches
    # finish — e.g. "ConnectionError: MCP session connection lost" /
    # "BrokenResourceError" as the per-call stdio subprocesses close. It is
    # harmless: it is retried and blocks no artifact. AgentTool already closes
    # its child runner and MCP sessions correctly (tools/agent_tool.py:340,
    # "Clean up runner resources (especially MCP sessions)"), so this is NOT a
    # leak in our wiring — it is a concurrency/teardown artifact of the
    # AgentTool-over-stdio-MCP reuse pattern. Because AgentTool always builds its
    # own child runner regardless of the outer runner, it is not specific to the
    # headless InMemoryRunner. Documented in the README so learners aren't alarmed.
    return ParallelAgent(
        name="shots",
        description=(
            f"Runs {MAX_SHOTS} per-shot slots concurrently; each turns its plan "
            "shot into a verified still + clip by reusing the crawl personas."
        ),
        sub_agents=shot_slots,
    )


# ============================================================================
# Stage 3 — the audio stage (LlmAgent reusing the Music Producer persona)
# ============================================================================
AUDIO_INSTRUCTION = """\
You are the audio department for a short video ad. The creative director's plan
is injected below:

<ad_plan>
{ad_plan}
</ad_plan>

Produce TWO audio artifacts for the ad by delegating to the `music_producer`
persona tool (it wires lyria for music and gemini TTS for voice, and verifies
each file by existence):

# 1. The music bed
Ask `music_producer` to generate a music bed matching the plan's `music_mood`,
saved LOCALLY under ./output (e.g. bed.mp3). Reuse the persona as-is — it knows
the lyria quirks (global-only default model; negative_prompt/seed/sample_count
are silently ignored; give it a local destination so a file is actually written).

# 2. The voiceover (VO)
Concatenate the plan's per-shot `vo_line`s, in shot order, into ONE continuous
narration script and ask `music_producer` to generate the VO from it, saved
LOCALLY under ./output (e.g. vo.wav). The gemini TTS tool caps `text` at 800
characters — if the combined narration exceeds that, tell the user to shorten
the VO lines rather than truncating silently. You want the VO as its OWN file;
you do NOT need the persona's mixed output here (the assembler mixes music and
VO against the video in the next stage).

# 3. Report
End with two labelled lines, each with the concrete verified local path:
  music bed -> <local path> (verified)
  voiceover -> <local path> (verified)
If either could not be verified, say so plainly — do not fabricate a path.
"""


# The storyboard audio stage: same reuse of the Music Producer persona, but it
# reads a StoryboardPlan (narration_line per panel, not vo_line) and writes the
# two files into the package's audio/ dir with predictable names the packager can
# find (music.mp3, narration.wav).
STORYBOARD_AUDIO_INSTRUCTION = """\
You are the audio department for an editorial storyboard animatic. The planner's
storyboard plan is injected below, and the destination directory for the audio:

<plan>
{plan}
</plan>

Save audio into this directory (an absolute path):
<audio_dir>{audio_dir}</audio_dir>

Produce TWO audio artifacts by delegating to the `music_producer` persona tool
(it wires lyria for music and gemini TTS for voice, and verifies each file by
existence):

# 1. The music bed
Ask `music_producer` to generate a music bed matching the plan's `music_mood`,
saved LOCALLY into {audio_dir} with the name `music.mp3` (lyria writes MP3 on the
default model; give it a local destination so a file is actually written).

# 2. The narration
Concatenate the plan's per-panel `narration_line`s, in panel order, into ONE
continuous explainer narration script and ask `music_producer` to generate it as
speech, saved LOCALLY into {audio_dir} with the name `narration.wav`. The gemini
TTS tool caps `text` at 800 characters — if the combined narration exceeds that,
tell the user to shorten the narration lines rather than truncating silently. You
want the narration as its OWN file; you do NOT need the persona's mixed output
(the assembler mixes music and narration against the animatic in the next stage).

# 3. Report
End with two labelled lines, each with the concrete verified local path:
  music bed -> {audio_dir}/music.mp3 (verified)
  narration -> {audio_dir}/narration.wav (verified)
If either could not be verified, say so plainly — do not fabricate a path.
"""


def _build_audio_stage(profile: Profile) -> LlmAgent:
    if profile.shot_media == "stills":
        return LlmAgent(
            model=MODEL,
            name="audio",
            description=(
                "Reuses the Music Producer persona to produce a music bed (from "
                "music_mood) and an explainer narration (from the panels' "
                "narration_lines) as files in the package's audio/ dir."
            ),
            instruction=STORYBOARD_AUDIO_INSTRUCTION,
            tools=[music_producer_tool],
        )
    return LlmAgent(
        model=MODEL,
        name="audio",
        description=(
            "Reuses the Music Producer persona to produce a music bed (from the "
            "plan's music_mood) and a VO (from the plan's vo_lines) as files."
        ),
        instruction=AUDIO_INSTRUCTION,
        tools=[music_producer_tool],
    )


# ============================================================================
# Stage 4 — the assembler (LlmAgent wiring avtool + one local ffmpeg helper)
# ============================================================================
def _ffprobe_duration_seconds(media_path: str) -> float:
    """Return a media file's duration in seconds via ffprobe (float)."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            media_path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def trim_audio_to_video_length(
    audio_path: str, video_path: str, output_path: str
) -> str:
    """Trim an audio file so it is no longer than a video, writing a new audio file.

    Use this on the MIXED music+VO track BEFORE combining it with the video, so
    the finished ad's audio does not run past the visuals. It is needed because
    the reused Lyria music bed is a fixed ~30s clip (no duration parameter) and
    avtool mixes with `amix=duration=longest` and offers no `-shortest`/trim, so
    without this step a 20s ad becomes a ~30s file with a silent/last-frame tail.

    The video is never modified. If the audio is already shorter than the video,
    it is left as-is (nothing to trim).

    Args:
      audio_path: local path to the mixed audio (music bed + VO) to trim.
      video_path: local path to the concatenated video whose duration is the target.
      output_path: local path to write the trimmed AAC audio to — use an
        .m4a/.mp4 container (the audio is re-encoded with -c:a aac); e.g.
        ./output/ad_mix_fit.m4a.

    Returns:
      A human-readable status string with the video duration, the original and
      the resulting audio durations, and the output path (verify by existence).
    """
    for tool in ("ffprobe", "ffmpeg"):
        if shutil.which(tool) is None:
            return (
                f"ERROR: '{tool}' is not on PATH. ffmpeg and ffprobe are required "
                "for assembly (see the project prerequisites)."
            )
    for label, p in (("audio", audio_path), ("video", video_path)):
        if not os.path.isfile(p):
            return f"ERROR: {label} file not found at '{p}'. Pass the verified path from the earlier step."

    try:
        video_dur = _ffprobe_duration_seconds(video_path)
        audio_dur = _ffprobe_duration_seconds(audio_path)
    except (subprocess.CalledProcessError, ValueError) as exc:
        return f"ERROR: could not read media duration with ffprobe: {exc}"

    if audio_dur <= video_dur + 0.05:
        return (
            f"No trim needed: audio {audio_dur:.2f}s <= video {video_dur:.2f}s. "
            f"Use '{audio_path}' as the audio input to the final combine."
        )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    # -t caps the OUTPUT to the video duration: the video is untouched and the
    # audio is cut at video length, so the combined container tracks the video.
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-t", f"{video_dur:.3f}",
             "-c:a", "aac", output_path],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as exc:
        return f"ERROR: ffmpeg trim failed: {exc.stderr or exc}"

    if not os.path.isfile(output_path):
        return f"ERROR: expected trimmed audio at '{output_path}' but it was not written."
    try:
        new_dur = _ffprobe_duration_seconds(output_path)
    except (subprocess.CalledProcessError, ValueError):
        new_dur = video_dur
    return (
        f"Trimmed audio to the video length. video={video_dur:.2f}s, "
        f"audio was {audio_dur:.2f}s, now {new_dur:.2f}s. "
        f"Use '{output_path}' as the audio input to the final combine (verified: file exists)."
    )


def build_stills_animatic_slideshow(
    image_paths: list[str],
    output_path: str,
    narration_audio_path: str = "",
    seconds_per_image: float = 3.0,
) -> str:
    """Build a silent slideshow video (.mp4) from an ordered list of still images.

    This is the storyboard profile's SECOND "one spot below MCP" (the ad profile
    has one: `trim_audio_to_video_length`). It exists because avtool genuinely has
    NO stills->video tool: its surface is ffmpeg_get_media_info,
    ffmpeg_convert_audio_wav_to_mp3, ffmpeg_video_to_gif,
    ffmpeg_combine_audio_and_video, ffmpeg_overlay_image_on_video,
    ffmpeg_adjust_volume, ffmpeg_layer_audio_files, and
    ffmpeg_concatenate_media_files (mcp-avtool-go/mcp_handlers.go:57, 116, 218,
    367, 532, 1035, 1158, 652) — every one needs existing media as input; none
    turns a set of PNGs into a timed video. Modifying the shared avtool server is
    out of scope, so this helper fills the gap by shelling the already-required
    ffmpeg (no new dependency), and the avtool server still does the audio mix +
    combine (the established reuse). Documented in the README "one spot below MCP".

    The slideshow is BOARD-PACED: if `narration_audio_path` is given and exists,
    each image is shown for narration_duration / len(images) seconds so the video
    length matches the narration (the storyboard has no ad duration budget — the
    narration sets the pace, addendum §6). Otherwise each image is shown for
    `seconds_per_image` seconds.

    Args:
      image_paths: ordered local paths to the still images (shots/shot-01.png …).
      output_path: local path to write the slideshow .mp4 to, e.g.
        <package>/slideshow.mp4.
      narration_audio_path: optional local path to the narration audio; when
        present its measured duration drives the per-image time (board-pacing).
      seconds_per_image: fallback per-image duration when no narration is given.

    Returns:
      A human-readable status string with the resulting video path and duration
      (verify by existence), or an "ERROR: …" string on any failure (fail-loud;
      the caller must NOT claim success on an ERROR return).
    """
    for tool in ("ffprobe", "ffmpeg"):
        if shutil.which(tool) is None:
            return (
                f"ERROR: '{tool}' is not on PATH. ffmpeg and ffprobe are required "
                "for the storyboard animatic (see the project prerequisites)."
            )
    if not image_paths:
        return "ERROR: no image paths were given; cannot build a slideshow."
    for p in image_paths:
        if not os.path.isfile(p):
            return f"ERROR: still not found at '{p}'. Pass the verified paths from the panel stage."

    per_image = seconds_per_image
    if narration_audio_path:
        if not os.path.isfile(narration_audio_path):
            return f"ERROR: narration audio not found at '{narration_audio_path}'."
        try:
            narration_dur = _ffprobe_duration_seconds(narration_audio_path)
            if narration_dur > 0:
                per_image = max(0.5, narration_dur / len(image_paths))
        except (subprocess.CalledProcessError, ValueError) as exc:
            return f"ERROR: could not read narration duration with ffprobe: {exc}"

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    # Use the ffmpeg concat demuxer: a temp list naming each image with a
    # `duration`. The concat demuxer needs the LAST image repeated with no
    # trailing duration so the final panel is held for its full time. Scale to
    # even dimensions and force yuv420p so the .mp4 is broadly playable.
    import tempfile

    list_lines = []
    for p in image_paths:
        abs_p = os.path.abspath(p)
        list_lines.append(f"file '{abs_p}'")
        list_lines.append(f"duration {per_image:.3f}")
    # Repeat the last file (concat demuxer quirk) so its duration is honored.
    list_lines.append(f"file '{os.path.abspath(image_paths[-1])}'")
    list_text = "\n".join(list_lines) + "\n"

    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False
    ) as list_file:
        list_file.write(list_text)
        list_path = list_file.name

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
                "-r", "25", "-pix_fmt", "yuv420p", output_path,
            ],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as exc:
        return f"ERROR: ffmpeg slideshow build failed: {exc.stderr or exc}"
    finally:
        try:
            os.unlink(list_path)
        except OSError:
            pass

    if not os.path.isfile(output_path):
        return f"ERROR: expected slideshow at '{output_path}' but it was not written."
    try:
        dur = _ffprobe_duration_seconds(output_path)
    except (subprocess.CalledProcessError, ValueError):
        dur = per_image * len(image_paths)
    return (
        f"Built the silent slideshow at '{output_path}': {len(image_paths)} "
        f"panels x {per_image:.2f}s = {dur:.2f}s (verified: file exists). Use it "
        "as the video input to the audio mix + combine steps."
    )


# ---------------------------------------------------------------------------
# The assembler wires the avtool server (LlmAgent tool orchestration) plus the
# one local helper above.
# ---------------------------------------------------------------------------
# The assembler is the capstone's OWN new role (no crawl persona covers final
# video assembly), so it wires the avtool server directly with the video tools
# the Music Producer's audio-only avtool filter deliberately hides. avtool is
# TRANSFORM-ONLY: every tool needs input files and needs ffmpeg + ffprobe on
# PATH. tool_filter matches BASE tool names, verified verbatim against the Go
# source (mcp-genmedia-go/mcp-avtool-go/mcp_handlers.go):
#   ffmpeg_concatenate_media_files  :652  (concat the per-shot clips)
#   ffmpeg_layer_audio_files        :1158 (mix music bed + VO)
#   ffmpeg_combine_audio_and_video  :367  (lay the mixed audio over the video)
#   ffmpeg_get_media_info           :57   (verify the final container/duration)
assembler_avtool = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-avtool-go",
            env=server_env,
        ),
        timeout=300,
    ),
    tool_filter=[
        "ffmpeg_concatenate_media_files",
        "ffmpeg_layer_audio_files",
        "ffmpeg_combine_audio_and_video",
        "ffmpeg_get_media_info",
    ],
)


ASSEMBLER_INSTRUCTION = """\
You are the video editor who assembles the final ad. The creative director's
plan is injected below for reference (shot order, total duration):

<ad_plan>
{ad_plan}
</ad_plan>

The shot stage produced one verified clip per shot (in GCS) and the audio stage
produced a verified music bed and a verified VO (local). The exact paths/URIs
are in the conversation above — read them from there; do NOT guess names.

avtool is TRANSFORM-ONLY (it needs real input files and ffmpeg/ffprobe on PATH),
so feed it the concrete paths the earlier stages reported. The output filename
EXTENSION selects the container, so use .mp4 for the video and .m4a/.mp3 for
audio. Assemble in this order:

# 1. Concatenate the clips -> one video
Call `ffmpeg_concatenate_media_files` with `input_media_uris` = the per-shot clip
URIs IN SHOT ORDER, `output_filename="ad_video.mp4"`, and
`output_local_dir="./output"` (or `output_gcs_bucket` if the user wants GCS).

# 2. Mix the music bed + VO -> one audio track
Call `ffmpeg_layer_audio_files` with `input_audio_uris` = [music bed, VO],
`output_filename="ad_mix.m4a"`, `output_local_dir="./output"`. If the VO should
sit above the bed, you may lower the bed with a volume step, but a straight mix
is fine for the reference.

# 3. Trim the mixed audio to the VIDEO length (so the audio doesn't run long)
The Lyria music bed is a fixed ~30s clip and avtool mixes with
`amix=duration=longest`, so the mixed audio from step 2 is usually LONGER than
the video from step 1 — combining them directly would leave the ad's audio
playing over a frozen/black tail. Before combining, call the
`trim_audio_to_video_length` tool with `audio_path` = the mixed audio (step 2),
`video_path` = the concatenated video (step 1), and
`output_path="./output/ad_mix_fit.m4a"`. Use its returned audio path as the
audio input to the next step (it tells you whether it trimmed or no trim was
needed). This keeps BOTH streams and never modifies the video.

# 4. Lay the (fitted) audio over the video -> the final ad
Call `ffmpeg_combine_audio_and_video` with `input_video_uri` = the concatenated
video from step 1, `input_audio_uri` = the fitted audio from step 3,
`output_filename="final_ad.mp4"`, `output_local_dir="./output"`.

# 5. VERIFY the final ad by existence — never a resource_link
Confirm final_ad.mp4 really exists and is within the duration budget: call
`ffmpeg_get_media_info` on it and report its duration, and tell the user to list
the destination (e.g. `ls -l ./output/final_ad.mp4`, or
`gcloud storage ls <gs URI>` for GCS). A tool returning successfully or a bare
resource_link is NOT proof — the destination listing / media info IS. If the
final file cannot be verified, say so plainly; do not claim success.

End with the concrete verified path/URI of the final ad and its measured
duration, and confirm it fits the 15s-2m budget.
"""


# The storyboard assembler wires avtool for the audio mix + combine + info, and
# has TWO local ffmpeg helpers: build_stills_animatic_slideshow (stills->silent
# video — avtool has no such tool) and the SAME trim_audio_to_video_length the ad
# assembler uses (do NOT write a second trimmer). The Lyria bed is a fixed ~30s
# clip and avtool mixes with amix=duration=longest with no -shortest, so the mixed
# music+narration must be trimmed to the slideshow length before combining, or the
# animatic gets a tail over a frozen last panel — the exact trap the ad path hit.
storyboard_assembler_avtool = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-avtool-go",
            env=server_env,
        ),
        timeout=300,
    ),
    tool_filter=[
        "ffmpeg_layer_audio_files",
        "ffmpeg_combine_audio_and_video",
        "ffmpeg_get_media_info",
    ],
)


STILLS_ANIMATIC_INSTRUCTION = """\
You are the editor who assembles the final editorial ANIMATIC (a stills board set
to narration + music). The planner's storyboard plan is injected for reference,
and the package directory where the final file must land:

<plan>
{plan}
</plan>

Write the final animatic into this directory (an absolute path):
<package_dir>{package_dir}</package_dir>

The panel stage produced one verified still per panel (local, named
shot-01.png, shot-02.png, … under {package_dir}/shots) and the audio stage
produced a verified music bed ({package_dir}/audio/music.mp3) and a verified
narration ({package_dir}/audio/narration.wav). The exact paths are in the
conversation above — read them from there; do NOT guess names.

There is NO Veo clip in this profile — you build the video FROM the stills. Work
in this order and verify by existence at the end:

# 1. Build the silent slideshow FROM the stills
Call the `build_stills_animatic_slideshow` tool with `image_paths` = the verified
still paths IN PANEL ORDER, `output_path="{package_dir}/slideshow.mp4"`, and
`narration_audio_path="{package_dir}/audio/narration.wav"` (so the slideshow is
board-paced to the narration length). Use the video path it reports. If it
returns an ERROR, stop and report it — do not continue.

# 2. Mix the music bed + narration -> one audio track
Call `ffmpeg_layer_audio_files` with `input_audio_uris` =
["{package_dir}/audio/music.mp3", "{package_dir}/audio/narration.wav"],
`output_filename="animatic_mix.m4a"`, `output_local_dir="{package_dir}"`.

# 3. Trim the mixed audio to the SLIDESHOW length
The Lyria bed is a fixed ~30s clip and avtool mixes with amix=duration=longest,
so the mixed audio is usually LONGER than the slideshow — combining directly
leaves audio over a frozen last panel. Call `trim_audio_to_video_length` with
`audio_path` = the mixed audio (step 2), `video_path` = the slideshow (step 1),
and `output_path="{package_dir}/animatic_mix_fit.m4a"`. Use its returned audio
path as the audio input to the next step.

# 4. Lay the (fitted) audio over the slideshow -> the animatic
Call `ffmpeg_combine_audio_and_video` with `input_video_uri` = the slideshow from
step 1, `input_audio_uri` = the fitted audio from step 3,
`output_filename="animatic.mp4"`, `output_local_dir="{package_dir}"`. The final
file MUST be exactly {package_dir}/animatic.mp4 so the packager can find it.

# 5. VERIFY the animatic by existence — never a resource_link
Call `ffmpeg_get_media_info` on {package_dir}/animatic.mp4 and report its
duration, and tell the user to list the destination (e.g.
`ls -l {package_dir}/animatic.mp4`). A tool returning successfully or a bare
resource_link is NOT proof — the destination listing / media info IS. If the file
cannot be verified, say so plainly; do not claim success.

End with the concrete verified path of {package_dir}/animatic.mp4 and its
measured duration.
"""


def _build_assembler(profile: Profile) -> LlmAgent:
    if profile.assembler_recipe == "stills_animatic":
        return LlmAgent(
            model=MODEL,
            name="assembler",
            description=(
                "Builds a silent slideshow from the panels' stills, mixes music "
                "+ narration, trims the audio to the slideshow length, lays it "
                "over the slideshow via avtool, and verifies animatic.mp4 by "
                "existence."
            ),
            instruction=STILLS_ANIMATIC_INSTRUCTION,
            # avtool for mix/combine/info, plus TWO local ffmpeg helpers: the new
            # stills->video slideshow builder and the SAME trim helper the ad
            # assembler uses (bare callables ADK auto-wraps in FunctionTools:
            # llm_agent.py:206-207).
            tools=[
                storyboard_assembler_avtool,
                build_stills_animatic_slideshow,
                trim_audio_to_video_length,
            ],
        )

    # profile.assembler_recipe == "video_ad_concat" — the ad path (unchanged).
    return LlmAgent(
        model=MODEL,
        name="assembler",
        description=(
            "Concatenates the per-shot clips, mixes music + VO, trims the audio "
            "to the video length, lays it over the video via avtool, and verifies "
            "the final ad by existence."
        ),
        instruction=ASSEMBLER_INSTRUCTION,
        # avtool MCPToolset for the transform steps, plus one local ffmpeg helper
        # (a bare callable ADK auto-wraps in a FunctionTool: llm_agent.py:206-207)
        # that fills avtool's missing audio-trim; see the AUDIO/VIDEO DURATION note
        # in the module docstring.
        tools=[assembler_avtool, trim_audio_to_video_length],
    )


# ============================================================================
# The engine — one factory, the ad profile as default
# ============================================================================
def build_root_agent(profile: Profile = AD_PROFILE) -> SequentialAgent:
    """Build the engine's SequentialAgent for the given profile.

    The same graph shape serves both audiences — only the per-stage builders
    branch on the Profile's fields (shot_media, assembler_recipe, plan_schema,
    plan_state_key). `AD_PROFILE` (default) is the ad capstone; `STORYBOARD_PROFILE`
    is the editorial storyboard/dogfood profile reached via the `package` CLI.
    `root_agent` below is built with AD_PROFILE, so `adk web` loads the ad
    capstone unchanged.
    """
    return SequentialAgent(
        name=f"ad_creative_director_{profile.name}",
        description=(
            "The capstone: a brand brief + target duration -> one assembled "
            "short video ad, composing the crawl personas via AgentTool."
        ),
        sub_agents=[
            _build_planner(profile),
            _build_shot_stage(profile),
            _build_audio_stage(profile),
            _build_assembler(profile),
        ],
    )


# `adk web` discovers this module-level `root_agent`. Building with AD_PROFILE
# means the ad capstone is what loads by default.
root_agent = build_root_agent(AD_PROFILE)
