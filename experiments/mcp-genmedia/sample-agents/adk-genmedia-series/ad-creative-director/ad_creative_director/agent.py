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
profiles.py) so a future audience is purely additive; THIS PR ships the `ad`
profile only, and `root_agent = build_root_agent(AD_PROFILE)` so `adk web` shows
the ad capstone by default.

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
for _sibling in ("photoshoot", "director-videographer", "music-producer"):
    _project_dir = _SERIES_ROOT / _sibling
    if not _project_dir.is_dir():
        raise RuntimeError(
            "ad-creative-director is the capstone: it COMPOSES the crawl "
            f"personas and needs the sibling example project '{_sibling}/' at "
            f"{_project_dir}, but that directory is missing. Check out the whole "
            "adk-genmedia-series/ (photoshoot/, director-videographer/, "
            "music-producer/ next to ad-creative-director/), not just this "
            "folder. See this project's README, section 'How it works'."
        )
    if str(_project_dir) not in sys.path:
        sys.path.insert(0, str(_project_dir))

from photoshoot.agent import root_agent as photoshoot_agent  # noqa: E402
from director_videographer.agent import root_agent as director_agent  # noqa: E402
from music_producer.agent import root_agent as music_producer_agent  # noqa: E402

# Wrap each persona as a callable tool. AgentTool(name=agent.name), so the tool
# names the LLM sees are "photoshoot", "director_videographer", "music_producer".
# These wrappers are stateless config, safe to share across the parallel shot
# slots (each call gets its own isolated Runner + session; see the header).
photoshoot_tool = AgentTool(agent=photoshoot_agent)
director_tool = AgentTool(agent=director_agent)
music_producer_tool = AgentTool(agent=music_producer_agent)


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


def _build_planner(profile: Profile) -> LlmAgent:
    return LlmAgent(
        model=MODEL,
        name="creative_director",
        description=(
            "Turns a brand brief + target duration into a schema-validated, "
            "duration-budgeted shot plan (AdPlan) in state['ad_plan']."
        ),
        instruction=PLANNER_BASE + profile.planner_persona,
        # output_schema makes the reply a schema-validated JSON plan; output_key
        # lands it in state['ad_plan'] for the downstream stages to read.
        output_schema=profile.plan_schema,
        output_key="ad_plan",
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


def _build_shot_stage(profile: Profile) -> ParallelAgent:
    # profile.shot_media == "clips" for the ad profile: still (photoshoot) then
    # clip (director) per slot. Kept on the Profile so a future stills-only
    # audience is a one-line change, not a graph rewrite.
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


def _build_audio_stage(profile: Profile) -> LlmAgent:
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
      output_path: local path to write the trimmed audio to (e.g.
        ./output/ad_mix_fit.m4a). The extension selects the container.

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


def _build_assembler(profile: Profile) -> LlmAgent:
    # profile.assembler_recipe == "video_ad_concat" for the ad profile.
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
    """Build the capstone SequentialAgent for the given profile.

    THIS PR ships the `ad` profile only. The factory seam keeps a future
    audience (e.g. an editorial storyboard profile) purely additive — no change
    to this graph shape, just a different Profile passed in.
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
