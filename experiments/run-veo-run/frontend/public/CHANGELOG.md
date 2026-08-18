# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Common Changelog](https://common-changelog.org/).

## 2026-08-18

### Added
- **Multi-Location Routing:** Support separate `GeminiClient` (global endpoint) and `VeoClient` (regional endpoint `us-central1`) to prevent location lookup errors across Vertex AI services (`run-veo-run-juq`).
- **Build Optimization:** Add `.gcloudignore` and `.dockerignore` to streamline Cloud Build uploads from ~55MB down to <1MB.

### Changed
- **Model Migration:** Migrate default Veo models from retired `veo-3.1-*-generate-preview` to active GA `veo-3.1-fast-generate-001` and `veo-3.1-generate-001`.
- **Configuration:** Add automatic string sanitization and trimming for environment variables.
- **Frontend Compatibility:** Update PostCSS configuration to `.cjs` for compatibility with modern Vite ESM loaders.

### Fixed
- **Model Aliasing:** Add server-side normalizer guardrail in `handlers/veo.go` to transparently route legacy `*-preview` requests to GA `*-001` endpoints.

## 2025-12-21
- Add --dev flag to build-run.sh (run-veo-run-v50)
- Fix Enhanced Prompt Dialog UX (run-veo-run-4tj)
- Show enhanced prompt dialog (run-veo-run-8oy)

## 2025-12-19
- Improve Gemini analysis prompt to include audio (run-veo-run-ley)

## 2025-12-15
- Enforce Video Upload Constraints (run-veo-run-32l)
- Research Veo Extension Limits (run-veo-run-dk1)
- Implement ReCAPTCHA Enterprise (run-veo-run-lx8.2)
- Support Video Upload (run-veo-run-i3a.4)
- Implement Memory Rate Limiting (run-veo-run-lx8.1)
- Implement Run, Veo, Run Prototype (run-veo-run-avr)
- Fix Gemini Content Role (run-veo-run-weg)
- Support Advanced Generation Modes (run-veo-run-i3a.3)
- Fix Model Selection for Ingredients (run-veo-run-t7b)
- Implement Ingredients Mode (run-veo-run-i3a.3.5)
- Implement Storyboard Mode (run-veo-run-i3a.3.4)
- Implement Image-to-Video Mode (run-veo-run-i3a.3.3)
- Create Frontend Upload Component (run-veo-run-i3a.3.2)
- Implement GCS Upload Endpoint (run-veo-run-i3a.3.1)
- Implement Info Dialog (run-veo-run-i3a.5)
- Implement Changelog Generation (run-veo-run-99c)
- Implement Infrastructure Scripts (run-veo-run-hcw)
- Fix GenAI Client Configuration (run-veo-run-zbv)
- Fix Signing Permissions for Service Account (run-veo-run-6jn)
- Support Separate Gemini Location (run-veo-run-coz)
- Implement Continuity Analysis Checkbox (run-veo-run-i3a.2)
- Implement Gemini Video Analysis Endpoint (run-veo-run-i3a.1)
- Plan Choose Your Own Adventure UI (run-veo-run-avr.1)
- Implement Settings UI (run-veo-run-zbv.1)
- Create App Favicon (run-veo-run-yyf.1)
- Plan Video Continuity Strategy (run-veo-run-bs1.1)
- Review and Enforce UI Styling (run-veo-run-6jn.1)
- Document Local Impersonation (run-veo-run-7u5)
- Fix Env Var Export (run-veo-run-bs1)
- Handle Signed URL Generation Errors (run-veo-run-6or)
- Scaffold Project Structure (run-veo-run-yyf)
- Implement Frontend Veo Integration (run-veo-run-ula)

