# Agent Guidelines for Vertex AI GenMedia Creative Studio

This document provides guidelines for AI agents working on the GenMedia Creative Studio codebase.

## Styling

- Prefer using shared styles from `components/styles.py` for common UI elements and layout structures.
- Page-specific or component-specific styles that are not reusable can be defined locally within those files.

## Google Cloud Storage (GCS)

- All interactions with GCS for storing media or other assets should use the `store_to_gcs` utility function located in `common/storage.py`.
- This function is configurable via `config/default.py` for bucket names.

## Configuration

- Application-level configuration values, such as model IDs, API keys (though avoid hardcoding keys directly), GCS bucket names, and feature flags, should be defined in `config/default.py`.
- Access these configurations by importing `cfg = Default()` from `config.default`.

## State Management

- Global application state (e.g., theme, user information) is managed in `state/state.py`.
- Page-specific UI state should be defined in corresponding files within the `state/` directory (e.g., `state/imagen_state.py`, `state/veo_state.py`).

## Error Handling

- For errors that occur during media generation processes and need to be communicated to the user, use the `GenerationError` custom exception defined in `common/error_handling.py`.
- Display these errors to the user via dialogs or appropriate UI elements.
- Log detailed errors to the console/server logs for debugging.

## Adding New Generative Models

- When adding a new generative model capability (e.g., a new type of image model, a different video model):
  - Add model interaction logic (API calls, request/response handling) to a new file in the `models/` directory (e.g., `models/new_model_name.py`).
  - Create UI components for controlling the new model in a subdirectory under `components/` (e.g., `components/new_model_name/generation_controls.py`).
  - Create a new page for the model in `pages/` (e.g., `pages/new_model_name.py`), utilizing the page scaffold and new components.
  - Define any page-specific state in `state/new_model_name_state.py`.
  - Add relevant configurations to `config/default.py`.
  - Update navigation in `config/navigation.json`.

## Metadata

- When storing metadata for generated media, use the `MediaItem` dataclass from `common/metadata.py` and the `add_media_item_to_firestore` function.
- Ensure all relevant fields in `MediaItem` are populated.

## Testing

- Write unit tests for utility functions and model interaction logic.
- Aim to mock external API calls during unit testing.
- Use `pytest` as the testing framework.

## Code Quality

- Use `ruff` for code formatting and linting.
- **Mandatory verification:** After any tool call that modifies Python code (`replace`, `write_file`), you MUST run `uv run ruff format <file_path>` and `uv run ruff check --fix <file_path>` immediately on the affected file. This prevents syntax and indentation errors from persisting or cascading.
- Ensure the project-wide lint pass (`ruff check .`) passes without new regressions before finalizing a task.


## 🤖 GitHub Automation Agents

This repository uses **Google's Gemini CLI** to automate software engineering tasks. Our AI agents assist with code reviews, issue triage, and general maintenance to keep the project moving efficiently.

## Automatic Behaviors

These agents run automatically based on events in the repository.

### 🔎 Code Reviewer

- **Trigger:** When a **Pull Request** is opened.

- **Action:** The agent reviews the code changes (diff), looking for bugs, security issues, and style improvements.
- **Output:** It posts review comments directly on the PR.
- **Note:** The agent focuses on the *diff* only and provides constructive feedback. It does not replace human review.

### 📋 Issue Triage

- **Trigger:** When a new **Issue** is opened.

- **Action:** The agent analyzes the title and body of the issue.
- **Output:** It automatically applies relevant **Labels** (e.g., `bug`, `enhancement`, `question`) to help organize the backlog.

---

## Maintainer Commands

Project maintainers (Owners, Members, Collaborators) can manually invoke the agents using comment commands.

| Command | Description |
| :--- | :--- |
| `@gemini-cli /review` | Manually triggers a full code review on the current Pull Request. |
| `@gemini-cli /triage` | Manually triggers label analysis on the current Issue or PR. |
| `@gemini-cli [question]` | Ask the agent a question about the codebase or request a specific task.  

*Example:* `@gemini-cli Explain how the authentication flow works.` |

> **Note:** These commands are restricted to project maintainers to prevent abuse and manage costs.

---

## Workflow Architecture

The automation is built on GitHub Actions using a "Router-Worker" pattern:

1. **Dispatch Router (`gemini-dispatch.yml`):** The entry point. It listens for events, validates permissions, and routes the request to the correct worker.
2. **Worker Workflows:**
    - `gemini-review.yml`: Handles code analysis.
    - `gemini-triage.yml`: Handles labeling.
    - `gemini-invoke.yml`: Handles general Q&A.

This system is powered by the [Gemini CLI](https://github.com/google-github-actions/run-gemini-cli) action.
---

## 7. Documentation Workflows

### Updating Documentation for New Features/Experiments

When new code, features, or experiments are added, it's crucial to update the relevant documentation to ensure discoverability and maintainability.

1.  **Identify Relevant Docs:** Determine which documentation files need updating (e.g., main `README.md`, `experiments/README.md`, `developers_guide.md`).
2.  **Analyze Existing Conventions:** Read the target documentation to understand its structure, tone, and formatting conventions for similar items.
3.  **Synthesize New Content:** Extract key information from the new feature's source code or its own README to create a concise and accurate description.
4.  **Propose Changes:** Present the proposed documentation changes to the user for review and approval before applying them. Use markdown blocks to clearly show the additions or modifications.
5.  **Apply Changes:** Use the `replace` or `write_file` tool to apply the approved changes.

---

## Issue Tracking

This project uses **bd (beads)** for issue tracking.
A dedicated **`beads-sync`** branch is used to persist issue metadata independently from the source code. This is particularly useful for forks where direct write access to the upstream `main` branch is not available.

### Sync Workflow

When you run `bd sync`, the following happens:
1. Your current work is stashed.
2. `bd` switches to the `beads-sync` branch.
3. It pulls/rebases changes from `origin/beads-sync`.
4. It commits your latest issue updates (`.beads/*.jsonl`).
5. It pushes back to `origin/beads-sync`.
6. It switches you back to your working branch and restores your stash.

Run `bd prime` for full workflow context.

**Quick reference:**
- `bd ready` - Find unblocked work
- `bd create "Title" --type task --priority 2` - Create issue
- `bd close <id>` - Complete work
- `bd sync` - Sync issues to the `beads-sync` branch

For full workflow details: `bd prime`

---

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds