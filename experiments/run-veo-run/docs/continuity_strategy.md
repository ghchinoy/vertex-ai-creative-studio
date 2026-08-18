# Video Continuity Strategy

To ensure "Run, Veo, Run" generates coherent narratives, we must maintain visual and narrative context across extensions.

## The Problem
Veo 3.1 is an image/video-to-video model, but it relies heavily on the text prompt for guidance. If the prompt doesn't reiterate the style (e.g., "Cyberpunk, industrial techno"), the model might drift.

## The Solution: "Analyze & Augment" Loop

### 1. Analysis Step (Gemini)
After Veo generates a clip, we automatically trigger a Gemini 2.5 Multimodal analysis of that clip.

**Endpoint:** `/api/gemini/analyze-context`
**Input:** `videoUri` (GCS)
**Prompt:**
> "Analyze this video clip. Provide a concise, comma-separated list of the following elements to ensure visual continuity in a generative video model:
> 1. Visual Style (e.g., film grain, color palette)
> 2. Lighting (e.g., neon, harsh shadows)
> 3. Main Subject description (appearance, clothing)
> 4. Setting description"

**Output:** JSON `{ "context": "Cyberpunk style, neon blue lighting, female runner in red tank top, wet concrete street" }`

### 2. Augmentation Step (Frontend)
When the user wants to extend the video:
1.  **UI:** Show a "Context" chip or text field pre-filled with the Gemini analysis.
2.  **Action:** User types new action: "She jumps over a car."
3.  **Merge:** The app constructs the final prompt:
    > "She jumps over a car. [Cyberpunk style, neon blue lighting, female runner in red tank top, wet concrete street]"

### 3. Execution (Veo)
The `HandleExtendVideo` endpoint receives this augmented prompt and the previous video URI, ensuring Veo has both the pixel data and the semantic guardrails to maintain the vibe.
