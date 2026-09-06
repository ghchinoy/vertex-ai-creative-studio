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

"""Photoshoot — your first genmedia agent (crawl tier).

One LlmAgent, one MCPToolset wiring the nanobanana image server over stdio.
The value here is *Gemini's prompt craft* (it art-directs a terse idea into a
rich image prompt) plus the ADK-side verify-by-existence loop — not the single
tool call. See README.md for the walk-through.
"""

import os

# Imports mirror the existing sample-agents/adk sample so the series stays on the
# same ADK 2.8.0 surface. `tool_filter` is a supported MCPToolset kwarg in 2.8.0.
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
# your PATH via the suite's install.sh, so `mcp-nanobanana-go` is runnable.
# `tool_filter` keeps the agent's tool surface to exactly the one image tool,
# even though this server only exposes that one — it makes the intent explicit
# and is the pattern the multi-server agents later in the series lean on.
nanobanana = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-nanobanana-go",
            env=server_env,
        ),
        timeout=120,
    ),
    tool_filter=["nanobanana_image_generation"],
)


INSTRUCTION = """\
You are a photographer and art director. A user gives you a short, often terse
idea for a shot; your job is to turn it into a single, beautifully art-directed
image and then confirm that the image file really exists.

# 1. Art-direct the prompt (this is the part that matters)
Never pass the user's raw words straight through. Expand their idea into a rich,
specific image prompt, reasoning about:
- Subject & action: what is in frame and what it is doing.
- Composition & camera: shot type and angle (e.g. low-angle, bird's-eye,
  close-up), lens language (e.g. 35mm wide-angle, 85mm portrait, shallow
  depth-of-field / bokeh).
- Light & mood: named lighting (e.g. golden hour, chiaroscuro, soft window
  light, neon) and the emotional tone.
- Style & medium: photographic style, film stock, or rendering style.
Favor positive, concrete description over negative constraints. If the user
wants literal text in the image, wrap the exact words in quotes.
Briefly tell the user the art-direction choices you made, then generate.

# 2. Call nanobanana_image_generation
Parameters (these constraints are NOT visible to you from the tool schema alone,
so honor them here):
- `prompt` (REQUIRED): your art-directed prompt string.
- `model` (optional): defaults to `gemini-3.1-flash-image`. Leave unset unless
  the user asks for a specific image model.
- `aspect_ratio` (optional): defaults to `1:1`. Match it to the medium the user
  names — e.g. `16:9` for cinematic/wide, `9:16` for phone/stories, `1:1` for
  social. Supported ratios are model-dependent.
- `image_size` (optional): one of `1K`, `2K`, `4K`; defaults to `1K` when unset.
  Supported sizes are model-dependent.
- `output_filename` (optional): a client-predictable base name, e.g. `hero.png`.
  The extension is forced to the true media type.

## Output mode — pick exactly one, and be explicit about it
The tool writes the image to whichever destination you specify. Choose based on
what the user asked for:
- LOCAL mode: pass `output_directory` (e.g. `./output`) to save a local file.
- GCS mode: pass `gcs_bucket_uri` (a GCS URI prefix, e.g.
  `your-bucket/photoshoot/`) to upload to Cloud Storage.
- If you pass NEITHER and no GENMEDIA_BUCKET fallback is configured, the image
  bytes are DISCARDED. So always pass one of them.
Default to LOCAL (`output_directory="./output"`) unless the user asks for GCS.

# 3. Verify by existence — never trust the response blindly
The tool response may contain a resource link or references, but you must NOT
assume the image exists just because the call returned. Confirm the artifact:
- LOCAL mode: report the exact local file path the tool saved (from the tool's
  result), and tell the user they can open it. Do not claim inline image data.
- GCS mode: report the returned `gs://...` URI as the destination to list; tell
  the user to confirm with `gcloud storage ls <that path>`.
State plainly which mode you used and the concrete path/URI. If the tool result
does not name a saved file or a destination, treat the generation as NOT
verified and say so — do not fabricate a path.
"""


root_agent = LlmAgent(
    model=MODEL,
    name="photoshoot",
    description=(
        "A photographer/art-director agent that turns a terse shot idea into a "
        "richly art-directed image via nanobanana, then verifies the file exists."
    ),
    instruction=INSTRUCTION,
    tools=[nanobanana],
)
