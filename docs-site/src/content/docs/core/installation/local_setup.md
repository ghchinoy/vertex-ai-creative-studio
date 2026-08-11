---
title: "Local Setup & Development"
---

## Setting up your development environment

### Python virtual environment

A python virtual environment, with required packages installed.

Using the [uv](https://github.com/astral-sh/uv) virtual environment and package manager:

```
# sync the requirements to a virtual environment
uv sync
```

If you've done this before, you can also use the command `uv sync --upgrade` to check for any package version upgrades.

### Application Environment variables

Use the included dotenv.template and create a `.env` file with your specific environment variables.

Only one environment variable is required:

- `PROJECT_ID` your Google Cloud Project ID, obtained via `gcloud config get project`

See the template dotenv.template file for the defaults and what environment variable options are available.

## GenMedia Creative Studio - Developing

### Running

Once you have your environment variables set, either on the command line or an in .env file:

```bash
uv run main.py
```

### Developing

Please see the [Developer's Guide](./developers_guide.md) for more information on how this application was built, including specific information about [Mesop](https://mesop-dev.github.io/mesop/) and the [scaffold for Studio style apps](https://github.com/ghchinoy/studio-scaffold).

When developing this app, since it's a FastAPI application that serves Mesop, please use the following

```bash
uv run main.py
```

Traditional Mesop hot reload capabilities (i.e. `mesop main.py`) are not fully available at this time.

### Smoke-testing your changes

Before merging any change that touches core-app runtime code (`pages/`, `models/`, `state/`, `config/`, `main.py`), run the boot smoke test:

```bash
./scripts/smoke_test.sh        # uv sync + boot + GET / -> /home (200) + GET /__login (200)
./scripts/smoke_test.sh -l     # also runs one live Vertex generateContent call (needs PROJECT_ID + ADC)
```

It is a fast, automated "does it still boot and serve?" check — not a replacement for the test suite, and not a deploy/IAP/Load Balancer validation. Running the app manually (above) remains the way to click around the UI yourself.