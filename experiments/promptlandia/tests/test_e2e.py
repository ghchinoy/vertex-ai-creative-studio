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

from playwright.sync_api import Page, expect


def test_checklist_page(page: Page):
    page.goto("http://localhost:32123/checklist")

    # Find the input field and type a prompt
    prompt_input = page.get_by_placeholder("Enter prompt to evaluate...")
    prompt_input.fill("This is a test prompt.")

    # Click the "Evaluate" button
    evaluate_button = page.get_by_role("button", name="send")
    evaluate_button.click()

    # Check that the results are displayed
    expect(page.locator("text=Checklist found")).to_be_visible()
