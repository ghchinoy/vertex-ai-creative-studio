# Developer's Guide

Welcome to the GenMedia Creative Studio application! This guide provides an overview of the application's architecture, key development patterns, and a step-by-step tutorial for contributing effectively.

## Application Architecture

This application is built using Python with the [Mesop](https://mesop-dev.github.io/mesop/) UI framework and a [FastAPI](https://fastapi.tiangolo.com/) backend. The project is structured to enforce a clear separation of concerns.

### Directory Structure

*   **`main.py`**: The main entry point. Initializes FastAPI, mounts Mesop, handles routing, and applies global middleware (Auth, CSP, Context).
*   **`app_factory.py`**: Contains the `on_load` handler which initializes global state (`AppState`) for every user session.
*   **`pages/`**: Top-level UI code for each distinct page (e.g., `/imagen`).
*   **`components/`**: Reusable UI elements (headers, dialogs, media library).
*   **`models/`**: Core business logic, including interactions with Vertex AI and other Google Cloud APIs.
*   **`state/`**: Global (`state.py`) and page-specific reactive state management.
*   **`config/`**: Configuration management, including model lists (`veo_models.py`), navigation, and prompt templates.
*   **`common/`**: Shared utilities for analytics, auth, metadata, and GCS storage.
*   **`experiments/`**: Incubator for new features. Features here are developed independently before being promoted to the core `pages/` and `models/`.

### Visual Workflow

The following sequence diagram shows the typical flow for a generative AI feature in this application.

![veo sequence diagram](https://github.com/user-attachments/assets/9df0cece-47b0-4c0f-848a-6d6dbf24465c)

1.  **UI (`pages/`)**: Captures user input.
2.  **Business Logic (`models/`)**: Calls Generative APIs.
3.  **Storage (`common/storage.py`)**: Persists media to GCS.
4.  **Metadata (`common/metadata.py`)**: Stores generation details in Firestore.
5.  **State (`state/`)**: Updates reactive state, triggering UI refresh.

---

## Core Development Patterns

### 1. Mesop UI and State Management

*   **Co-locating Page State**: State specific to a single page **must** be defined in the same file as the `@me.page` function to avoid `NameError` during hot-reloads.
*   **Global AppState**: Use `me.state(AppState)` for shared data like `user_email`, `session_id`, and `role`.
*   **Event Handlers**: Functions assigned to event handlers (e.g., `on_click`) must be generators that `yield` to trigger UI updates. Avoid wrapping generators in `lambda` functions as it breaks the update chain.

### 2. The Media Library Pattern (Generate -> Store -> Notify)

Every generative feature should follow this pattern to ensure it integrates with the shared Media Library:

1.  **Generate**: Call the model in `models/`.
2.  **Store**: Save the resulting bytes to GCS using `common.storage.store_to_gcs`.
3.  **Metadata**: Create a `MediaItem` dataclass and save it using `common.metadata.add_media_item_to_firestore`.
4.  **Notify**: Update the UI state and show a `snackbar` notification.

### 3. Secure Media Delivery (Media Proxy)

Never use raw GCS signed URLs for UI display. Instead, use the `create_display_url` utility from `common.utils`.
*   **How it works**: It converts `gs://bucket/path` to `/media/bucket/path`.
*   **Benefit**: The FastAPI backend proxies the content, enforcing IAP/Firebase authentication and providing better caching headers.

### 4. Dynamic Feature Management

Feature visibility is controlled via `config/navigation.json`.
*   **Feature Flags**: You can hide pages by adding `feature_flag` or `feature_flag_not` to the navigation item. These flags are checked against attributes in the `Default` config class (`config/default.py`).
*   **Model Lists**: Component dropdowns (like model selection) are often driven by config files like `config/imagen_models.py`. Update these files to add support for new model versions globally.

### 5. Analytics and Instrumentation

*   **Simple Clicks**: Use the `@track_click(element_id="...")` decorator.
*   **Complex Interactions**: Use `log_ui_click(element_id="...", extras={...})`.
*   **Model Performance**: Wrap API calls in the `track_model_call("model-name")` context manager.

---

## Contributing & Issue Tracking

This project uses **bd (beads)** for distributed issue tracking. To ensure a clean contribution workflow—especially when working on a fork—we use a dedicated **`beads-sync`** branch.

### 1. Forking and Setup

1.  **Fork the repository** on GitHub.
2.  **Initialize `bd`**:
    ```bash
    bd init --from-jsonl
    ```
    *Choose 'Y' to configure `.git/info/exclude`. This keeps `.beads/` files out of your code PRs.*

### 2. The `beads-sync` Workflow

Metadata updates are pushed to a dedicated sidecar branch named `beads-sync`.

*   **Standard Work**: Use `bd create`, `bd close`, etc.
*   **Synchronizing**: Run `bd sync` to persist your task state to your fork. 
*   **Session Completion**: Always run `bd sync` before finishing your work.

### 3. Using Coding Agents

For those using AI coding agents (like Gemini CLI), this repository includes a **`GEMINI.md`** file. This file contains project-specific instructions, quality gates, and architectural context optimized for agents. Ensuring your agent reads this file will help it adhere to the project's established conventions and contribution workflows.

---

## How to Add a New Page

### Step 1: Create the Page File
Create `pages/my_new_page.py` using the standard scaffold:

```python
import mesop as me
from components.page_scaffold import page_frame, page_scaffold
from components.header import header

@me.stateclass
class PageState:
    val: str = ""

@me.page(path="/my_page", title="My Page")
def page():
    with page_scaffold(page_name="my_page"):
        with page_frame():
            header("My Page", "rocket")
            me.text("Hello World")
```

### Step 2: Register & Navigate
1.  **Import in `main.py`**: `from pages import my_new_page`
2.  **Add to `config/navigation.json`**:
    ```json
    {
      "id": 100,
      "display": "My Page",
      "icon": "rocket",
      "route": "/my_page",
      "group": "workflows"
    }
    ```

### Step 3: Verify
Run quality gates on your new file:
```bash
uv run ruff format pages/my_new_page.py
uv run ruff check --fix pages/my_new_page.py
```