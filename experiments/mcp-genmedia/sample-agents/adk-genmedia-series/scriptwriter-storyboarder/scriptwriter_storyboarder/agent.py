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

"""Scriptwriter / Storyboarder — your first ADK pipeline (walk tier).

A two-stage `SequentialAgent`. The `scriptwriter` (text only, no tools) turns a
one-line brief into a numbered shot list and writes it to session state under
`output_key="shot_list"`. The `storyboarder` then reads that value back by name
via the `{shot_list}` template in its instruction and generates one nanobanana
still per shot. This is the series' reference example for ADK's native
state-passing between agents: `output_key` writes, `{key}` reads.
See README.md for the walk-through.
"""

import os

# Imports mirror the crawl-tier photoshoot agent so the series stays on the same
# ADK 2.8.0 surface, and add `SequentialAgent` — the one new construct this tier
# teaches. `tool_filter` is a supported MCPToolset kwarg in 2.8.0.
from dotenv import load_dotenv
from google.adk.agents import LlmAgent, SequentialAgent
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
# `tool_filter` keeps the storyboarder's tool surface to exactly the one image
# tool — the same nanobanana wiring the crawl-tier photoshoot agent uses.
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


# --- Stage 1: the scriptwriter (text only, no tools) -------------------------
# It writes its final response into session state under `output_key`. In ADK
# 2.8.0 the LlmAgent copies the agent's final text response into
# state["shot_list"] (google/adk/agents/llm_agent.py: the `output_key` field is
# declared at line 419; the write happens in __maybe_save_output_to_state at
# line 1045: `event.actions.state_delta[self.output_key] = result`).
SCRIPTWRITER_INSTRUCTION = """\
You are a scriptwriter. The user gives you a single one-line creative brief; your
job is to turn it into a short, shootable shot list.

Produce a NUMBERED shot list. Use AT MOST 6 shots (fewer is fine — only add a
shot if it earns its place). Keeping it to six or fewer keeps the storyboard
generation that follows fast and cheap.

For each shot, on its own numbered line, give three things clearly labelled:
- Scene: where we are / the setting.
- Action: what is happening in the frame.
- Look: composition, lens, light, and mood (the visual style).

Write ONLY the numbered shot list as plain text — no preamble, no closing
remarks, no markdown headings. This text is handed verbatim to the storyboard
artist as the next stage of the pipeline, so keep every shot self-contained and
visually concrete.
"""


# --- Stage 2: the storyboarder (reads {shot_list} from state) ----------------
# `{shot_list}` is ADK 2.8.0 instruction templating: before each LLM call the
# flow runs inject_session_state over the instruction string and substitutes
# {key} with state[key] (google/adk/utils/instructions_utils.py: _render_with_regex
# / _replace_match). A plain (non-optional) {shot_list} raises KeyError if the key
# is absent — which is what we want here: in this SequentialAgent the scriptwriter
# always runs first and populates it, so a missing value means the state hand-off
# is broken and should fail loudly rather than silently. (The `{shot_list?}`
# suffix would substitute "" instead; we deliberately do not use it.)
STORYBOARDER_INSTRUCTION = """\
You are a storyboard artist. The scriptwriter has just written a shot list; here
it is, injected from session state:

<shot_list>
{shot_list}
</shot_list>

Your job is to generate ONE storyboard still for EACH numbered shot above, in
order, and then report a shot->image map.

# 1. Work shot by shot
Read the shot list above and generate exactly one image per numbered shot — no
more, no fewer. For each shot, art-direct a rich image prompt FROM THAT SHOT's
Scene / Action / Look (composition, lens, light, mood); do not invent shots that
are not in the list and do not merge shots.

# 2. Call nanobanana_image_generation (once per shot)
Parameters (these constraints are NOT visible to you from the tool schema alone,
so honor them here):
- `prompt` (REQUIRED): your art-directed prompt string for that one shot.
- `model` (optional): defaults to `gemini-3.1-flash-image`. Leave unset unless
  the user asks for a specific image model.
- `aspect_ratio` (optional): defaults to `1:1`. Match it to the medium the brief
  implies — e.g. `16:9` for cinematic/wide, `9:16` for phone/stories, `1:1` for
  social. Supported ratios are model-dependent.
- `image_size` (optional): one of `1K`, `2K`, `4K`; defaults to `1K` when unset.
  Supported sizes are model-dependent.
- `output_filename` (optional): a client-predictable base name, e.g.
  `shot-01.png`. The extension is forced to the true media type. Use the shot
  number so the stills are easy to match back to the list.

## Output mode — choose deliberately, and be explicit about it
The tool writes each still to whichever destination you specify. Use the SAME
mode for every shot in a run:
- LOCAL mode: pass `output_directory` (e.g. `./output`) to save a local file.
- GCS mode, specific bucket: ONLY when the user gives you a real bucket, pass
  `gcs_bucket_uri` as an actual GCS URI prefix of the form
  `gs://<your-bucket>/<prefix>/`. Never invent a bucket name, and never pass a
  placeholder — a made-up or example URI will 403. Use exactly the bucket the
  user named.
- GCS mode, no bucket named: when the user asks to save to GCS/Cloud Storage but
  does NOT name a specific bucket, pass NEITHER `output_directory` nor
  `gcs_bucket_uri`. The server then uses the configured `GENMEDIA_BUCKET`
  fallback (writing under `<bucket>/nanobanana_outputs/`). Prefer this over
  guessing a URI.
- The trap: if you pass NEITHER output param AND no `GENMEDIA_BUCKET` fallback is
  configured, the image bytes are DISCARDED. So for local requests always pass
  `output_directory`; for GCS-without-a-named-bucket rely on the fallback (and if
  the tool reports nothing was saved, tell the user to set `GENMEDIA_BUCKET`).
Default to LOCAL (`output_directory="./output"`) unless the user asks for GCS.

# 3. Verify by existence — never trust the response blindly
The tool response may contain a resource link or references, but you must NOT
assume a still exists just because the call returned. For each shot, confirm the
artifact:
- LOCAL mode: read the exact local file path the tool saved (from the tool's
  result). Do not claim inline image data.
- GCS mode: read the returned `gs://...` URI as the destination to list; tell the
  user to confirm with `gcloud storage ls <that path>`.
If the tool result for a shot does not name a saved file or a destination, treat
that still as NOT verified and say so for that shot — do not fabricate a path.

# 4. Emit the shot->image map
When every shot is done, end with a plain mapping, one line per shot, e.g.:
  Shot 1 -> ./output/shot-01.png (verified)
  Shot 2 -> ./output/shot-02.png (verified)
State plainly which output mode you used. The number of rows in the map MUST
equal the number of shots in the shot list — that 1:1 correspondence is the
proof that you read and honored the scriptwriter's shot list.
"""


scriptwriter = LlmAgent(
    model=MODEL,
    name="scriptwriter",
    description=(
        "Turns a one-line creative brief into a numbered shot list (<= 6 shots), "
        "written to session state under output_key='shot_list'."
    ),
    instruction=SCRIPTWRITER_INSTRUCTION,
    # ADK writes this agent's final text response into state["shot_list"], where
    # the next agent reads it via the {shot_list} template.
    output_key="shot_list",
)


storyboarder = LlmAgent(
    model=MODEL,
    name="storyboarder",
    description=(
        "Reads the scriptwriter's shot list from state ({shot_list}) and "
        "generates one verified nanobanana still per shot, then a shot->image map."
    ),
    instruction=STORYBOARDER_INSTRUCTION,
    tools=[nanobanana],
)


# The pipeline: scriptwriter runs first (writes shot_list), then storyboarder
# runs (reads shot_list). This ordered hand-off through session state IS the
# lesson of the walk tier.
root_agent = SequentialAgent(
    name="scriptwriter_storyboarder",
    description=(
        "A two-stage pipeline that turns a one-line brief into a shot list and "
        "then a storyboard still per shot, passing state via output_key."
    ),
    sub_agents=[scriptwriter, storyboarder],
)
