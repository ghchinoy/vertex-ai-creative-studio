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

from dataclasses import field

import mesop as me


@me.stateclass
class PageState:
    """Brand Adherence Page State"""

    # Input
    pdf_gcs_uri: str = ""
    pdf_filename: str = ""
    user_prompt: str = ""
    reference_image_gcs_uri: str = ""
    reference_image_display_url: str = ""

    # Analysis
    is_analyzing: bool = False
    brand_guidelines_text: str = ""

    # Image Generation
    is_generating: bool = False
    generated_image_gcs_uri: str = ""
    generated_image_display_url: str = ""

    # Evaluation
    is_evaluating: bool = False
    evaluation_results: dict[str, str] = field(default_factory=dict)  # JSON strings

    # UI
    show_snackbar: bool = False
    snackbar_message: str = ""
    info_dialog_open: bool = False
