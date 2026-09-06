# ADK sample

This directory contains a Google Cloud Vertex AI Agent Development Kit (ADK) sample
agent that uses the MCP genmedia tools. It is a single `LlmAgent` that wires four
genmedia MCP servers and lets the model pick and sequence the tools it needs.

## Backend

This sample is pinned to the **Vertex AI / Google Cloud backend**. The dependency is
declared as `google-adk[gcp,mcp]` in `pyproject.toml`, which pulls in the Vertex/GCP
client stack. The sample is set up this way on purpose so it stays consistent with the
rest of the genmedia MCP servers, which all assume a Google Cloud configuration. The
Vertex backend is selected at runtime by setting `GOOGLE_GENAI_USE_VERTEXAI="True"`
(see [Setup](#setup) below); no other backend is configured.

## What this agent wires

The agent (`genmedia_agent/agent.py`) is one `LlmAgent` with four **stdio** MCP
toolsets — all invoked as binaries on your `PATH`, no separate server processes to
start:

| Toolset | Binary (`command`) | What it does |
|---|---|---|
| `nanobanana` | `mcp-nanobanana-go` | image generation (`nanobanana_image_generation`) |
| `chirp3` | `mcp-chirp3-go` | text-to-speech (Chirp 3) |
| `veo` | `mcp-veo-go` | text/image-to-video (Veo) |
| `avtool` | `mcp-avtool-go` | audio/video compositing (needs `ffmpeg`/`ffprobe`) |

## Prerequisites

1. **Install the MCP genmedia server suite (>= v3.18.1) on your `PATH`.** Use the
   suite's `install.sh` (from `experiments/mcp-genmedia/mcp-genmedia-go/`), which
   installs the Go binaries (`mcp-nanobanana-go`, `mcp-chirp3-go`, `mcp-veo-go`,
   `mcp-avtool-go`, ...) locally. Confirm they are on your path:

   ```bash
   which mcp-nanobanana-go mcp-chirp3-go mcp-veo-go mcp-avtool-go
   ```

2. **Install `ffmpeg` / `ffprobe`** (required by `avtool` for compositing):

   ```bash
   which ffmpeg ffprobe
   ```

3. **`uv`** for dependency management and running the ADK web UI.

## Setup

Add a `.env` file to the `genmedia_agent/` directory (see `genmedia_agent/.env.example`).
The agent model (`gemini-3.8-flash`) runs in the **`global`** region:

```bash
GOOGLE_CLOUD_PROJECT="your-project-id"
GOOGLE_CLOUD_LOCATION="global"
GOOGLE_GENAI_USE_VERTEXAI="True"
GENMEDIA_BUCKET="your-gcs-bucket-name"
```

`GENMEDIA_BUCKET` is the GCS bucket the media servers (veo, nanobanana) write their
output to. Veo always writes to GCS; nanobanana can write locally or to GCS. The media
servers take their own region/bucket configuration via environment, independent of the
agent's `global` model region.

## Run the ADK Developer UI

In this dir, start the `adk web` debug UX:

```bash
uv sync
source .venv/bin/activate
adk web
```

Then open the web UI and try a prompt such as *"Generate an image of a red bicycle
leaning against a blue wall."* — the agent will call `nanobanana_image_generation` and
report the output. Verify generated media by checking the output file / GCS destination
(do not rely on reading a returned resource link).

![adk web screenshot](./assets/adk-genmedia-mcp.png)
