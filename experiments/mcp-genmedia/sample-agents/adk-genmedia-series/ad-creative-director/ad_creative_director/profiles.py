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

"""The profile seam — a plain-Python dataclass + factory input.

The capstone is built behind `build_root_agent(profile)` (see agent.py) so the
same engine can later grow a second audience (e.g. an editorial `storyboard`
profile) without reworking the graph. THIS PR ships the `ad` profile ONLY; the
README presents "the ad creative-director's assistant" and the seam stays a thin
internal one-liner, not reader-facing overhead.

DESIGN CONSTRAINT (deliberate): profiles are a **frozen dataclass + factory**,
using only stable ADK constructor APIs. We do NOT use ADK's `from_config` /
`AgentConfig` YAML loader: in ADK 2.8.0 `agents/config_agent_utils.py:from_config`
is decorated BOTH `@deprecated` AND `@experimental(FeatureName.AGENT_CONFIG)`, so
building the engine on it would schedule a removal into the series.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from .schemas import AdPlan


@dataclass(frozen=True)
class Profile:
    """Selects what the one engine produces for a given audience.

    Attributes:
      name: short profile id, used in the root agent's name ("ad").
      planner_persona: tone/audience prose appended to the shared planner
        instruction (PLANNER_BASE in agent.py).
      plan_schema: the planner's `output_schema` (AdPlan for the ad profile).
      shot_media: what each per-shot slot produces ("clips": still -> Veo clip).
      assembler_recipe: which avtool assembly the assembler runs
        ("video_ad_concat": concat clips + mix music/VO + combine).
    """

    name: str
    planner_persona: str
    plan_schema: type[BaseModel]
    shot_media: str
    assembler_recipe: str


# The tone/audience half of the planner instruction for the ad profile. The
# construct-level half (schema fields, duration budget, shot cap) lives in
# PLANNER_BASE in agent.py so it is shared across any future profile.
_AD_PLANNER_PERSONA = """\

# Your brief and voice (ad creative director)
You are an ad creative director. The user gives you a brand brief and a target
duration; you turn it into a tight, persuasive short video ad. Think like an
advertiser: a clear through-line, a hero product/benefit, an emotional beat, and
a crisp call-to-action in the final shot's voiceover. Keep the brand voice
consistent across shots and make every second earn its place.
"""


AD_PROFILE = Profile(
    name="ad",
    planner_persona=_AD_PLANNER_PERSONA,
    plan_schema=AdPlan,
    shot_media="clips",
    assembler_recipe="video_ad_concat",
)
