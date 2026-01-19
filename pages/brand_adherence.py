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
"""Brand Adherence Workflow Page."""

import datetime
import json
import uuid

import mesop as me

from common.metadata import MediaItem, add_media_item_to_firestore
from common.storage import store_to_gcs
from common.utils import create_display_url
from components.header import header
from components.page_scaffold import page_frame, page_scaffold
from components.snackbar import snackbar
from models.gemini import (
    evaluate_media_with_questions,
    generate_image_from_prompt_and_images,
    generate_text,
)
from models.guideline_analysis import generate_guideline_criteria
from state.brand_adherence_state import PageState
from state.state import AppState


@me.page(
    path="/brand_adherence",
    title="Brand Adherence - GenMedia Creative Studio",
)
def page():
    with page_scaffold(page_name="brand_adherence"), page_frame():
        header("Brand Adherence", "verified")
        brand_adherence_content()


def brand_adherence_content():
    state = me.state(PageState)

    snackbar(is_visible=state.show_snackbar, label=state.snackbar_message)

    with me.box(
        style=me.Style(
            display="flex", flex_direction="column", gap=24, padding=me.Padding.all(24),
        ),
    ):
        # --- Step 1: Upload Guidelines ---
        with me.box(style=me.Style(display="flex", flex_direction="column", gap=16)):
            me.text(
                "1. Upload Brand Guidelines (PDF) & Optional Reference Image",
                type="headline-6",
            )

            with me.box(
                style=me.Style(
                    display="flex", flex_direction="row", gap=16, flex_wrap="wrap",
                ),
            ):
                # PDF Uploader
                with me.box(style=me.Style(flex_grow=1)):
                    if state.pdf_filename:
                        with me.box(
                            style=me.Style(display="flex", align_items="center", gap=16),
                        ):
                            me.icon("picture_as_pdf")
                            me.text(state.pdf_filename)
                            me.button(
                                "Clear PDF", on_click=on_clear_pdf, type="stroked",
                            )
                    else:
                        me.uploader(
                            label="Upload PDF",
                            on_upload=on_upload_pdf,
                            accepted_file_types=["application/pdf"],
                        )

                # Reference Image Uploader
                with me.box(style=me.Style(flex_grow=1)):
                    if state.reference_image_display_url:
                        with me.box(
                            style=me.Style(display="flex", align_items="center", gap=16),
                        ):
                            me.image(
                                src=state.reference_image_display_url,
                                style=me.Style(height=50, border_radius=4),
                            )
                            me.button(
                                "Clear Image",
                                on_click=on_clear_reference_image,
                                type="stroked",
                            )
                    else:
                        me.uploader(
                            label="Optional Reference Image",
                            on_upload=on_upload_reference_image,
                            accepted_file_types=[
                                "image/jpeg",
                                "image/png",
                                "image/webp",
                            ],
                            key="ref_img_uploader",
                        )

            if state.pdf_gcs_uri and not state.brand_guidelines_text:
                me.button(
                    "Analyze Guidelines",
                    on_click=on_analyze_click,
                    type="raised",
                    disabled=state.is_analyzing,
                )
                if state.is_analyzing:
                    me.progress_spinner(diameter=24)

        # --- Step 2 & 3: Side-by-Side ---
        if state.brand_guidelines_text:
            me.divider()
            with me.box(
                style=me.Style(
                    display="flex", flex_direction="row", gap=24, flex_wrap="wrap",
                ),
            ):
                # Left Column: Guidelines
                with me.box(
                    style=me.Style(
                        flex_basis="400px",
                        flex_grow=1,
                        display="flex",
                        flex_direction="column",
                        gap=16,
                    ),
                ):
                    me.text("2. Extracted Brand Context", type="headline-6")
                    me.textarea(
                        label="Brand Guidelines (Editable)",
                        value=state.brand_guidelines_text,
                        on_blur=on_guidelines_blur,
                        rows=15,
                        style=me.Style(width="100%"),
                    )

                # Right Column: Generation
                with me.box(
                    style=me.Style(
                        flex_basis="400px",
                        flex_grow=1,
                        display="flex",
                        flex_direction="column",
                        gap=16,
                    ),
                ):
                    me.text("3. Generate On-Brand Image", type="headline-6")

                    me.textarea(
                        label="Image Prompt",
                        placeholder="e.g., A coffee cup on a wooden table",
                        value=state.user_prompt,
                        on_blur=on_prompt_blur,
                        rows=3,
                        style=me.Style(width="100%"),
                    )

                    me.button(
                        "Generate Image",
                        on_click=on_generate_image_click,
                        type="raised",
                        disabled=state.is_generating or not state.user_prompt,
                    )

                    if state.is_generating:
                        me.progress_spinner(diameter=24)

        # --- Result Section (Full Width) ---
        if state.generated_image_display_url:
            me.divider()
            with me.box(
                style=me.Style(
                    display="flex",
                    flex_direction="column",
                    gap=16,
                    margin=me.Margin(top=16),
                ),
            ):
                me.text("Result & Analysis", type="headline-5")

                with me.box(
                    style=me.Style(
                        display="flex", flex_direction="row", gap=24, flex_wrap="wrap",
                    ),
                ):
                    # Image
                    with me.box(style=me.Style(flex_basis="500px", flex_grow=1)):
                        me.image(
                            src=state.generated_image_display_url,
                            style=me.Style(
                                width="100%",
                                border_radius=8,
                                border=me.Border.all(
                                    me.BorderSide(width=1, color="#ccc"),
                                ),
                            ),
                        )

                    # Analysis
                    with me.box(style=me.Style(flex_basis="400px", flex_grow=1)):
                        if state.is_evaluating:
                            with me.box(
                                style=me.Style(
                                    display="flex", align_items="center", gap=8,
                                ),
                            ):
                                me.progress_spinner(diameter=20)
                                me.text("Analyzing adherence...")

                        if state.evaluation_results:
                            for (
                                category,
                                evaluation_json,
                            ) in state.evaluation_results.items():
                                evaluation = json.loads(evaluation_json)
                                with me.expansion_panel(
                                    title=f"{category}: {evaluation['score']}",
                                    icon="rule",
                                ):
                                    for detail in evaluation["details"]:
                                        with me.box(
                                            style=me.Style(
                                                display="flex",
                                                flex_direction="row",
                                                align_items="center",
                                                gap=8,
                                                margin=me.Margin(bottom=8),
                                            ),
                                        ):
                                            if detail["answer"]:
                                                me.icon(
                                                    "check_circle",
                                                    style=me.Style(
                                                        color=me.theme_var("success"),
                                                    ),
                                                )
                                            else:
                                                me.icon(
                                                    "cancel",
                                                    style=me.Style(
                                                        color=me.theme_var("error"),
                                                    ),
                                                )
                                            me.text(detail["question"])


# --- Event Handlers ---


def on_upload_pdf(e: me.UploadEvent):
    state = me.state(PageState)
    file = e.files[0]
    gcs_uri = store_to_gcs(
        "brand_guidelines", file.name, file.mime_type, file.getvalue(),
    )
    state.pdf_gcs_uri = gcs_uri
    state.pdf_filename = file.name
    yield


def on_clear_pdf(e: me.ClickEvent):
    state = me.state(PageState)
    state.pdf_gcs_uri = ""
    state.pdf_filename = ""
    state.brand_guidelines_text = ""
    yield


def on_upload_reference_image(e: me.UploadEvent):
    state = me.state(PageState)
    file = e.files[0]
    gcs_uri = store_to_gcs(
        "brand_reference_images", file.name, file.mime_type, file.getvalue(),
    )
    state.reference_image_gcs_uri = gcs_uri
    state.reference_image_display_url = create_display_url(gcs_uri)
    yield


def on_clear_reference_image(e: me.ClickEvent):
    state = me.state(PageState)
    state.reference_image_gcs_uri = ""
    state.reference_image_display_url = ""
    yield


def on_analyze_click(e: me.ClickEvent):
    state = me.state(PageState)
    state.is_analyzing = True
    yield

    try:
        prompt = "Analyze this brand guidelines PDF. Extract the following visual identity elements: Color Palette (hex codes if available), Visual Style (e.g., minimalist, vibrant), Key Imagery Rules (Do's and Don'ts). Summarize this into a concise paragraph for an image generation prompt."

        text, _ = generate_text(prompt=prompt, images=[state.pdf_gcs_uri])
        state.brand_guidelines_text = text

    except Exception as ex:
        state.snackbar_message = f"Error analyzing PDF: {ex}"
        state.show_snackbar = True
    finally:
        state.is_analyzing = False
        yield


def on_guidelines_blur(e: me.InputEvent):
    state = me.state(PageState)
    state.brand_guidelines_text = e.value


def on_prompt_blur(e: me.InputEvent):
    state = me.state(PageState)
    state.user_prompt = e.value


def on_generate_image_click(e: me.ClickEvent):
    state = me.state(PageState)
    app_state = me.state(AppState)
    state.is_generating = True
    state.generated_image_display_url = ""
    state.evaluation_results = {}
    yield

    try:
        # Combine user prompt with brand guidelines
        full_prompt = f"""{state.user_prompt}

Brand Guidelines Context:
{state.brand_guidelines_text}"""

        # Pass reference image if available
        images = (
            [state.reference_image_gcs_uri] if state.reference_image_gcs_uri else []
        )

        gcs_uris, _, _, _ = generate_image_from_prompt_and_images(
            prompt=full_prompt,
            images=images,
            aspect_ratio="16:9",
            gcs_folder="brand_adherence_generations",
        )

        if gcs_uris:
            state.generated_image_gcs_uri = gcs_uris[0]
            state.generated_image_display_url = create_display_url(gcs_uris[0])

            # Start Evaluation
            state.is_evaluating = True
            yield

            try:
                # Generate criteria (using reference image for visual grounding if available)
                criteria = generate_guideline_criteria(
                    prompt=state.user_prompt,
                    additional_guidance=state.brand_guidelines_text,
                    reference_image_uri=state.reference_image_gcs_uri
                    if state.reference_image_gcs_uri
                    else None,
                )

                # Evaluate
                new_evaluations = {}
                for category, questions in criteria.items():
                    if not questions:
                        continue

                    evaluation_result = evaluate_media_with_questions(
                        media_uri=state.generated_image_gcs_uri,
                        mime_type="image/png",
                        questions=questions,
                    )

                    yes_answers = sum(
                        1 for answer in evaluation_result.answers if answer.answer
                    )
                    score_str = f"{yes_answers}/{len(questions)}"
                    evaluation_dict = {
                        "score": score_str,
                        "details": [
                            ans.model_dump() for ans in evaluation_result.answers
                        ],
                    }
                    new_evaluations[category] = json.dumps(evaluation_dict)

                state.evaluation_results = new_evaluations

            except Exception as eval_ex:
                print(f"Evaluation failed: {eval_ex}")
                state.snackbar_message = f"Evaluation failed: {eval_ex}"
                state.show_snackbar = True
            finally:
                state.is_evaluating = False

                # Save MediaItem
                media_item = MediaItem(
                    id=str(uuid.uuid4()),
                    user_email=app_state.user_email,
                    timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
                    media_type="image",
                    mode="Brand Adherence",
                    gcs_uris=[state.generated_image_gcs_uri],
                    thumbnail_uri=state.generated_image_gcs_uri,
                    prompt=full_prompt,
                    source_images_gcs=[state.pdf_gcs_uri]
                    + (
                        [state.reference_image_gcs_uri]
                        if state.reference_image_gcs_uri
                        else []
                    ),
                    comment="Generated On-Brand Image",
                    critique=json.dumps(state.evaluation_results)
                    if state.evaluation_results
                    else None,
                )
                add_media_item_to_firestore(media_item)

                yield

        else:
            state.snackbar_message = "Failed to generate image."
            state.show_snackbar = True

    except Exception as ex:
        state.snackbar_message = f"Error generating image: {ex}"
        state.show_snackbar = True
    finally:
        state.is_generating = False
        yield
