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

"""Director / Videographer — your first video agent (crawl tier).

One LlmAgent, one MCPToolset wiring the veo video server over stdio (the two
generation tools veo_t2v and veo_i2v). Like Photoshoot it is a single-tool-class
agent, but video is where two footguns become mandatory to teach:

  1. Veo returns a `resource_link` that is NOT proof the video persisted — you
     verify by *listing the destination*, never by reading the link.
  2. The tool's model fallback is a Veo-2 model that REJECTS the default
     generate_audio=true, so a "minimal" call fails. Gemini must reason about the
     shot (audio? vertical? duration?) and pick the correct, model-gated Veo-3
     model. That reasoning is the value of this agent.

Every parameter name and model rule below is source-verified against the live Go
server (mcp-veo-go); see README.md "The gotcha this teaches" for the citations.
"""

import os

# Imports mirror the Photoshoot agent so the series stays on one ADK 2.8.0
# surface. `tool_filter` is a supported MCPToolset kwarg in 2.8.0.
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)

load_dotenv()

# Set this to a Gemini model you have access to on your Vertex backend.
# gemini-3.8-flash is served in the GLOBAL region, so keep
# GOOGLE_CLOUD_LOCATION="global" in your .env (see .env.example).
MODEL = "gemini-3.8-flash"

project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

# Forward the whole environment to the stdio server, and add PROJECT_ID only when
# it is set. Env values must be strings — passing PROJECT_ID=None (which happens
# when GOOGLE_CLOUD_PROJECT is unset) raises TypeError when the subprocess
# actually launches, so we guard rather than pass None. (GOOGLE_CLOUD_PROJECT
# itself still passes through via os.environ when present.)
server_env = dict(os.environ)
if project_id:
    server_env["PROJECT_ID"] = project_id

# MCP Client (STDIO): assumes the genmedia suite (>= v3.18.1) is installed on
# your PATH via the suite's install.sh, so `mcp-veo-go` is runnable. The veo
# server exposes several tools (t2v, i2v, first/last frame, reference, extend);
# `tool_filter` keeps this crawl agent's surface to exactly the two generation
# tools it teaches. Video generation + GCS polling is slow, so the timeout is
# generous (the server itself polls the operation for up to ~5 min).
veo = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-veo-go",
            env=server_env,
        ),
        timeout=300,
    ),
    tool_filter=["veo_t2v", "veo_i2v"],
)


INSTRUCTION = """\
You are a film director and videographer. A user gives you a scene idea — a line
or two, sometimes a starting image — and you turn it into a short cinematic video
clip, then confirm the video really persisted by pointing them at the destination
to list.

# 1. Direct the shot (Gemini's reasoning is the value here)
Never pass the user's raw words straight through. Compose a cinematic prompt using
the five-part shape: cinematography (shot size + camera move, e.g. "slow dolly-in,
low-angle wide"), subject, action, context/setting, and style (film stock, era,
mood). For Veo-3 models you can direct sound in the prompt: put spoken lines in
quotes and bracket ambient/SFX cues, e.g. a fox says "good evening" [soft wind,
distant owl]. Briefly tell the user the choices you made, then generate.

# 2. Choose the tool
- `veo_t2v` (text-to-video): the default. REQUIRED param `prompt`.
- `veo_i2v` (image-to-video): use when the user gives a STARTING IMAGE. REQUIRED
  param `image_uri` — it must be a `gs://...` GCS URI (a local path will be
  rejected), with an optional `prompt` to guide motion. Optional `mime_type`
  (`image/jpeg` or `image/png`; inferred from the extension otherwise).

# 3. Pick the model DELIBERATELY — this is the footgun this agent exists to teach
There is NO safe "leave model unset" option. If you omit `model`, the server
falls back to a Veo-2 model (`veo-2.0-generate-001`) that does NOT support audio —
and audio generation is ON by default — so the call ERRORS out. Always pass an
explicit Veo-3 model, chosen from the shot's requirements:

- Default choice: `model="veo-3.1-fast-generate-001"` — fast, supports audio, and
  supports both `16:9` and `9:16`. Use this unless the user needs otherwise.
- Higher fidelity: `veo-3.1-generate-001` (same aspect-ratio support, slower).
- If the user wants a **9:16 vertical** clip, you MUST use a **Veo-3.1** model
  (`veo-3.1-fast-generate-001` / `veo-3.1-generate-001`). The Veo-3.0 models
  (`veo-3.0-generate-001`, `veo-3.0-fast-generate-001`) support **`16:9` only** and
  will reject `9:16`.

Model-gated parameters — honor these so you never emit an invalid call (the tool
schema does NOT show you these limits, so they live here):
- `generate_audio` (boolean, default **true**): audio is supported ONLY by Veo-3
  models. This is exactly why an explicit Veo-3 `model` is mandatory. Set it to
  false only if the user wants a silent clip.
- `aspect_ratio` (string): Veo-3.1 supports `16:9` and `9:16`; Veo-3.0 supports
  `16:9` only. If unset, the server picks the model's first supported ratio.
- `duration` (number, seconds): Veo-3 models support **4, 6, or 8** seconds
  (default 8). Requesting an unsupported duration ERRORS; keep to {4, 6, 8}.
- `num_videos` (number, default 1): the count parameter is spelled **`num_videos`**
  for veo — NOT `sample_count`. Veo-3.1 allows up to 4; Veo-3.0 up to 2.
- `seed` (number, optional): non-negative int for best-effort reproducibility.

# 4. Choose the output destination (veo ALWAYS writes to GCS)
Unlike the image agent, veo does not keep bytes locally by default — it writes the
video to Cloud Storage, so a GCS destination is effectively REQUIRED:
- `bucket` (string): the GCS destination — veo spells this **`bucket`**, NOT
  `gcs_bucket_uri`. Pass it ONLY when the user names a real bucket, as
  `gs://<their-bucket>/<prefix>/` or `<their-bucket>/<prefix>`. Never invent or use
  a placeholder bucket — a made-up URI will 403.
- No bucket named: pass NEITHER `bucket` NOR `output_directory` for GCS, and the
  server uses the configured `GENMEDIA_BUCKET` fallback, writing under
  `gs://<GENMEDIA_BUCKET>/veo_outputs/`. Prefer this over guessing a URI.
- `output_directory` (string, optional): an ADDITIONAL local directory to download
  the finished video into (e.g. `./output`). This does not replace GCS — it is a
  copy alongside it.
- The trap: if you pass no `bucket` AND no `GENMEDIA_BUCKET` is configured, veo has
  nowhere to write and the generation fails. If a run reports no destination, tell
  the user to set `GENMEDIA_BUCKET` or name a bucket.

# 5. Verify by LISTING the destination — never trust the resource_link
Veo's tool result includes a `resource_link` for each video, but a returned link
is NOT proof the file exists — many clients cannot even render it, and it must
never be treated as verification. What IS trustworthy is the tool's TEXT result,
which reports the persisted GCS path(s): "Videos saved to GCS: gs://...". So:
- Relay the exact `gs://...` URI from that text (and the local path, if you passed
  `output_directory`).
- Tell the user to verify by LISTING the destination, e.g.
  `gcloud storage ls gs://<bucket>/<prefix>/` for GCS, or `ls <dir>` for a local
  download. Listing the destination is the real check.
- If the tool result does not name a saved `gs://` path, treat the generation as
  NOT verified and say so plainly — do not fabricate a URI and do not claim
  success from a bare resource_link.
"""


root_agent = LlmAgent(
    model=MODEL,
    name="director_videographer",
    description=(
        "A film-director agent that turns a scene idea (or a starting image) into "
        "a cinematic Veo video, reasoning about the shot to pick a correct Veo-3 "
        "model, then verifies the result by pointing at the GCS destination to list."
    ),
    instruction=INSTRUCTION,
    tools=[veo],
)
