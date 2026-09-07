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

"""Music Producer — three servers, one agent (crawl tier).

One LlmAgent wiring THREE MCPToolsets over stdio: lyria (music), gemini TTS
(voiceover), and avtool (mix/convert). This is the first agent in the series to
wire more than one server, so it is where two ADK/genmedia ideas are taught:

  1. `tool_name_prefix` on every MCPToolset, so the three servers' tool names
     never collide and the model's tool choices stay legible (music_*, tts_*,
     av_*). ADK inserts the separator itself — prefixed_name = f"{prefix}_
     {tool.name}" (base_toolset.py:162) — so the prefix VALUES are bare role
     tokens with NO trailing underscore ("music", "tts", "av"), named by role so
     they don't echo the base tool name.
  2. The naming crosswalk (../NAMING.md): the servers spell "the same" parameter
     differently (model_id vs model_name, output_gcs_bucket vs output_directory
     vs local_path vs output_local_dir, sample_count, text vs prompt). The model
     cannot see those constraints from tools/list, so the INSTRUCTION bakes the
     exact names for THIS agent's three tools.

Every parameter and tool name below was source-verified against the genmedia Go
sources at repo tip; file:line citations live next to each toolset and in the
INSTRUCTION. See README.md for the walk-through.
"""

import os

# Imports mirror photoshoot/ so the series stays on the same ADK surface.
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)

load_dotenv()

# One model constant, served in the GLOBAL region — keep GOOGLE_CLOUD_LOCATION
# ="global" in .env (see .env.example). The default Lyria model is also
# global-only (Interactions API), so "global" is required, not just convenient.
MODEL = "gemini-3.8-flash"

project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

# Forward the environment to each stdio server, adding PROJECT_ID only when set.
# Env values must be strings; passing PROJECT_ID=None raises TypeError when the
# subprocess launches, so we guard rather than pass None. (Same pattern as
# photoshoot/.) All three toolsets share this env.
server_env = dict(os.environ)
if project_id:
    server_env["PROJECT_ID"] = project_id


# --- Server 1: lyria (music) -------------------------------------------------
# Binary: mcp-lyria-go. Tool: lyria_generate_music.
# Source: mcp-genmedia-go/mcp-lyria-go/lyria.go:161 (mcp.NewTool name),
#   params prompt:128 (required), model_id:155 (default lyria-3-clip-preview,
#   see lyria.go:61), output_gcs_bucket:143, local_path:152, output_filename:146,
#   sample_count:138 / negative_prompt:132 / seed:135 (DROPPED on the default
#   model — see the INSTRUCTION and NAMING.md Lyria caveat).
# tool_filter matches the BASE tool.name (applied before prefixing), so it stays
# "lyria_generate_music". tool_name_prefix is the bare role token "music" (NOT
# "lyria" — that would echo the base name and stutter); ADK adds the separator,
# so the exposed name is "music_lyria_generate_music".
lyria = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-lyria-go",
            env=server_env,
        ),
        timeout=180,
    ),
    tool_filter=["lyria_generate_music"],
    tool_name_prefix="music",
)


# --- Server 2: gemini TTS (voiceover) ----------------------------------------
# Binary: mcp-gemini-go. Tool: gemini_audio_tts.
# Source: mcp-genmedia-go/mcp-gemini-go/main.go:124 (mcp.NewTool name),
#   params text:126 (required, 800-char cap — enforced in
#   tts_handlers.go:267-268), prompt:130 (STYLE, not content), voice_name:133,
#   model_name:138, output_directory:154 (local; no GCS output param).
# tool_filter (base names) keeps the surface to just the TTS tool (this server
# also exposes gemini_image_generation, list_gemini_voices, omni_video_generation).
# Bare role prefix "tts" -> exposed name "tts_gemini_audio_tts".
tts = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-gemini-go",
            env=server_env,
        ),
        timeout=120,
    ),
    tool_filter=["gemini_audio_tts"],
    tool_name_prefix="tts",
)


# --- Server 3: avtool (mix / convert) ----------------------------------------
# Binary: mcp-avtool-go. Transform-only: every tool needs an INPUT file/URI and
# needs ffmpeg + ffprobe on PATH (mcp-avtool-go/ffmpeg_commands.go:21 execs
# "ffmpeg"; ffprobe_commands.go:17 execs "ffprobe").
# Tools used by this agent:
#   ffmpeg_layer_audio_files          mcp_handlers.go:1158  (mix music + VO)
#     input_audio_uris (required, array)  :1160
#     output_filename (extension selects container) :1161
#     output_local_dir :1163 / output_gcs_bucket :1164
#   ffmpeg_convert_audio_wav_to_mp3   mcp_handlers.go:116   (WAV VO -> MP3)
#     input_audio_uri (required) :118 / output_filename :119
# tool_filter narrows avtool's 8-tool surface to exactly the three this agent
# uses, so — like lyria and tts above — the model only sees tools relevant to
# this job (the video/gif/overlay/concat/volume transforms stay hidden). The
# strings are the exact source tool names (verified: ffmpeg_layer_audio_files
# mcp_handlers.go:1158, ffmpeg_convert_audio_wav_to_mp3 mcp_handlers.go:116,
# ffmpeg_get_media_info mcp_handlers.go:57); tool_filter matches these BASE names
# (applied before prefixing) and a filter entry that doesn't match a real tool
# name is silently dropped, so these must match source verbatim. Bare role prefix
# "av" -> exposed names av_ffmpeg_layer_audio_files, av_ffmpeg_convert_audio_wav
# _to_mp3, av_ffmpeg_get_media_info.
avtool = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-avtool-go",
            env=server_env,
        ),
        timeout=180,
    ),
    tool_filter=[
        "ffmpeg_layer_audio_files",
        "ffmpeg_convert_audio_wav_to_mp3",
        "ffmpeg_get_media_info",
    ],
    tool_name_prefix="av",
)


INSTRUCTION = """\
You are a music producer and audio engineer. Given a mood/genre for a music bed
and a short voiceover (VO) script, you produce THREE artifacts: a music file, a
VO file, and a mixed file that layers the two — and you VERIFY each one exists
before reporting success.

You wire THREE servers. Because tool names could collide across servers, every
tool you can call is namespaced by role — `music_`, `tts_`, `av_`. Use the
prefixed names exactly as written below. The parameter constraints below are NOT
visible from the tool schemas, so honor them here. The full crosswalk of why the
names differ across servers is in ../NAMING.md — read it once; the exact names
for YOUR three tools are baked below.

Work in this order and do not skip the verification after each step.

# 1. Generate the music bed — `music_lyria_generate_music`
- `prompt` (REQUIRED): a rich description of the music bed (genre, instruments,
  tempo, mood). This is the one parameter that reliably shapes the output.
- `local_path` (recommended): a local directory, e.g. `./output`. NOTE the
  spelling — lyria calls the local dir `local_path`, NOT `output_directory`
  (that is the majority spelling other servers use; see NAMING.md §3).
- `output_filename` (optional): a predictable base name, e.g. `bed.mp3`. On the
  default model lyria emits MP3, so use a `.mp3` name.
- To save to Cloud Storage instead, pass `output_gcs_bucket` (a bare bucket
  name, NOT a `gs://` URI, and NOT `bucket`/`gcs_bucket_uri` — see NAMING.md §2).
- **Do NOT pass `negative_prompt`, `seed`, or `sample_count`.** On the default
  Lyria model (`lyria-3-clip-preview`, which runs on the Vertex Interactions
  API) these are SILENTLY IGNORED — only the first sample is returned and only
  `prompt` reaches the model. Promising them would teach an invalid call. The
  default model is also GLOBAL-region only (keep GOOGLE_CLOUD_LOCATION=global).
- **The trap:** if you pass NEITHER `local_path` NOR `output_gcs_bucket` (and no
  GENMEDIA_BUCKET fallback is set), the audio is returned inline and no file is
  written — avtool would then have nothing to mix. Always give lyria a
  destination. Default to LOCAL: `local_path="./output"`.
- Requires the genmedia suite >= v3.18.1; older builds return no usable audio.

# 2. Generate the voiceover — `tts_gemini_audio_tts`
- `text` (REQUIRED): the words to SPEAK. This is the content. Capped at 800
  characters — if the script is longer, tell the user to shorten it (do not
  silently truncate).
- `prompt` (optional): STYLE/delivery instructions only (tone, pace, accent) —
  NOT content. This overload (`text`=content, `prompt`=style) is unique to the
  TTS tools; see NAMING.md §5.
- `output_directory` (recommended): a local directory, e.g. `./output`. This
  tool uses the majority spelling `output_directory` (contrast lyria's
  `local_path`). It writes WAV by default. There is NO GCS output param on this
  tool — it is LOCAL only.
- `output_filename` (optional): e.g. `vo.wav`.
- `model_name` (optional): the model id spelling here is `model_name` (lyria uses
  `model_id`; most other servers use `model`). Leave it unset unless the user
  names a model.

# 3. Mix the two — avtool (`av_*`)
avtool is TRANSFORM-ONLY: it cannot generate audio, it only operates on INPUT
files, and it needs `ffmpeg` and `ffprobe` on PATH. So it must run AFTER steps 1
and 2, and you feed it the concrete file paths those steps saved.
- Mix music + VO with `av_ffmpeg_layer_audio_files`:
  - `input_audio_uris` (REQUIRED): an ARRAY of the two paths, e.g.
    `["./output/bed.mp3", "./output/vo.wav"]` (local paths or `gs://`).
  - `output_filename`: **the extension SELECTS the output container** — pass
    `mix.mp3` for MP3, `mix.wav` for WAV. Choose deliberately and tell the user
    which container you asked for.
  - `output_local_dir` (optional): local output dir, e.g. `./output`. NOTE the
    spelling — avtool calls it `output_local_dir` (not `output_directory`, not
    `local_path`; NAMING.md §3). `output_gcs_bucket` for GCS.
- If you instead need to convert the WAV VO to MP3, use
  `av_ffmpeg_convert_audio_wav_to_mp3` (`input_audio_uri` REQUIRED,
  `output_filename` selects the container by extension).

# 4. Verify by existence — never trust a resource link
A tool returning successfully does NOT mean a file exists, and a returned
resource link is NOT proof of persistence. After each step, confirm the concrete
artifact the tool reported it SAVED:
- LOCAL: report the exact saved path (from the tool result) and tell the user
  they can list it, e.g. `ls -l ./output/bed.mp3`.
- GCS: report the returned `gs://...` destination and tell the user to confirm
  with `gcloud storage ls <that path>`.
If a tool result does not name a saved file or destination, treat that step as
NOT verified and say so — do not fabricate a path. Finally, confirm the mixed
file's container matches the extension you requested (e.g. `.mp3` really is MP3);
if the user cares, tell them to check with `av_ffmpeg_get_media_info`.

State plainly, for all three artifacts, the concrete path/URI and how you
verified it.
"""


root_agent = LlmAgent(
    model=MODEL,
    name="music_producer",
    description=(
        "A music-producer/audio-engineer agent that generates a music bed "
        "(lyria) and a voiceover (gemini TTS), mixes them with avtool, and "
        "verifies each artifact exists. Teaches multi-server MCPToolset wiring "
        "with tool_name_prefix and the genmedia naming crosswalk."
    ),
    instruction=INSTRUCTION,
    tools=[lyria, tts, avtool],
)
