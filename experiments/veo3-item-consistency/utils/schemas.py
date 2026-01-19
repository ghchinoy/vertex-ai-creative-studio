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

from enum import Enum

from pydantic import BaseModel, Field


# --- Enumerations for Constrained Choices ---
class SexEnum(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    INDETERMINATE = "Indeterminate / Androgynous"


class AncestryEnum(str, Enum):
    WHITE_CAUCASIAN = "White / Caucasian"
    BLACK_AFRICAN_DESCENT = "Black / African Descent"
    HISPANIC_LATINO = "Hispanic / Latino/a"
    EAST_ASIAN = "East Asian"
    SOUTH_ASIAN = "South Asian"
    SOUTHEAST_ASIAN = "Southeast Asian"
    MIDDLE_EASTERN_NORTH_AFRICAN = "Middle Eastern / North African"
    INDIGENOUS_NATIVE_AMERICAN = "Indigenous / Native American"
    PACIFIC_ISLANDER = "Pacific Islander"
    MIXED_RACE_AMBIGUOUS = "Mixed Race / Ambiguous"


class FacialBuildEnum(str, Enum):
    SLENDER = "Slender / Bony"
    ATHLETIC = "Athletic / Toned"
    AVERAGE = "Average"
    HEAVY_SET = "Heavy-set / Fleshy"
    GAUNT = "Gaunt / Emaciated"


class FaceShapeEnum(str, Enum):
    OVAL = "Oval"
    ROUND = "Round"
    SQUARE = "Square"
    HEART = "Heart-shaped"
    DIAMOND = "Diamond-shaped"
    RECTANGULAR_LONG = "Rectangular / Long"
    TRIANGULAR = "Triangular"


class HairLengthEnum(str, Enum):
    BALD_SHAVED = "Bald / Shaved"
    BUZZ_CUT = "Buzz cut"
    SHORT = "Short (above ears)"
    EAR_LENGTH = "Ear-length"
    CHIN_LENGTH = "Chin-length"
    SHOULDER_LENGTH = "Shoulder-length"
    LONG = "Long (past shoulders)"


class HairTextureEnum(str, Enum):
    STRAIGHT = "Straight"
    WAVY = "Wavy"
    CURLY = "Curly"
    KINKY_COILY = "Kinky / Coily"


class HairlineEnum(str, Enum):
    STRAIGHT = "Straight"
    ROUNDED = "Rounded"
    WIDOWS_PEAK = "Widow's Peak"
    RECEDING = "Receding"
    UNEVEN = "Uneven"


class HairstyleEnum(str, Enum):
    """A detailed and comprehensive categorization of hairstyles across all genders."""

    # ============== Loose / Down Styles ==============
    # Describes hair that is worn down and not tied up.
    FREE_HAIR = "Free Hair"
    SIDE_PART = "Side Part"
    MIDDLE_PART = "Middle Part / Curtains"
    SLICKED_BACK = "Slicked Back"
    SHAG = "Shag / Heavily Layered"
    BANGS_FRINGE = "Bangs / Fringe"

    # ============== Short & Styled ==============
    # Distinct styles that are typically defined by a short-to-medium length cut.
    BOB = "Bob / Lob"
    PIXIE_CUT = "Pixie Cut"
    POMPADOUR = "Pompadour"
    QUIFF = "Quiff"
    SPIKY = "Spiky"
    COMB_OVER = "Comb Over"

    # ============== Tied / Updos ==============
    # Styles where hair is gathered and secured.
    PONYTAIL = "Ponytail"
    PIGTAILS = "Pigtails"
    BUN = "Bun / Top Knot"

    # ============== Braided / Platted / Twisted ==============
    # Styles created by weaving, plaiting, or twisting strands of hair.
    PLATTED_BRAIDED = "Platted / Braided"
    CORNROWS = "Cornrows"
    BOX_BRAIDS = "Box Braids"
    DREADLOCKS = "Dreadlocks / Locs"
    TWISTS = "Twists"
    FRENCH_DUTCH_BRAID = "French / Dutch Braid"

    # ============== Shaved / Cropped ==============
    # Very short styles, often created with clippers.
    BALD = "Bald / Clean Shaven"
    BUZZ_CUT = "Buzz Cut"
    FADE = "Fade / Taper"
    CREW_CUT = "Crew Cut"
    UNDERCUT = "Undercut"
    MOHAWK = "Mohawk / Faux Hawk"

    # ============== Textured / Unique Constructions ==============
    # Styles defined primarily by their unique texture or structure.
    AFRO = "Afro"
    MULLET = "Mullet"

    # ============== Other ==============
    OTHER = "Other"


class HairlineEnum(str, Enum):
    STRAIGHT = "Straight"
    ROUNDED = "Rounded"
    WIDOWS_PEAK = "Widow's Peak"
    RECEDING = "Receding"
    UNEVEN = "Uneven"


class EyeShapeEnum(str, Enum):
    ALMOND = "Almond"
    ROUND = "Round"
    DOWNTURNED = "Downturned"
    UPTURNED = "Upturned"
    HOODED = "Hooded"
    MONOLID = "Monolid"
    DEEP_SET = "Deep-set"


class EyebrowShapeEnum(str, Enum):
    STRAIGHT = "Straight"
    ARCHED = "Arched"
    CURVED = "Curved"
    ANGLED = "Angled"


class FacialHairTypeEnum(str, Enum):
    CLEAN_SHAVEN = "Clean-shaven"
    STUBBLE = "Stubble"
    MOUSTACHE = "Moustache"
    BEARD = "Beard"
    GOATEE = "Goatee"


# --- Nested Feature Models ---
class OverallImpression(BaseModel):
    perceived_sex: SexEnum
    perceived_age_description: str
    perceived_ancestry: AncestryEnum
    facial_build: FacialBuildEnum
    most_memorable_feature: str


class HeadAndFaceStructure(BaseModel):
    face_shape: FaceShapeEnum
    forehead_description: str
    cheekbones_description: str
    jawline_description: str
    chin_description: str


class HairFeatures(BaseModel):
    color: str
    length: HairLengthEnum
    texture: HairTextureEnum
    style: HairstyleEnum
    hairline: HairlineEnum
    density_and_condition: str


class EyeAndEyebrowFeatures(BaseModel):
    eyebrow_description: str
    eye_color: str
    eye_shape: EyeShapeEnum
    eye_details: str


class NoseFeatures(BaseModel):
    bridge_description: str
    tip_description: str
    nostril_description: str


class MouthAndLipFeatures(BaseModel):
    lip_fullness: str
    mouth_shape: str
    resting_expression: str
    teeth_description: str | None


class SkinFeatures(BaseModel):
    complexion_and_tone: str
    texture_and_condition: str
    distinguishing_marks: list[str]


class FacialHairFeatures(BaseModel):
    type: FacialHairTypeEnum
    style_and_condition: str
    color: str


class AccessoryFeatures(BaseModel):
    eyeglasses: str | None
    headwear: str | None
    piercings: list[str]


# --- The Master Schema ---
class FacialCompositeProfile(BaseModel):
    overall_impression: OverallImpression
    head_and_face_structure: HeadAndFaceStructure
    hair: HairFeatures
    eyes_and_eyebrows: EyeAndEyebrowFeatures
    nose: NoseFeatures
    mouth_and_lips: MouthAndLipFeatures
    skin: SkinFeatures
    facial_hair: FacialHairFeatures | None
    accessories: AccessoryFeatures | None


# --- Machine Profile Schema ---
class MachineProfile(BaseModel):
    """A detailed profile of a machine or robotic entity."""

    machine_type: str = Field(
        description="The type of machine, e.g., 'humanoid robot', 'industrial arm', 'cybernetic drone'.",
    )
    primary_materials: list[str] = Field(
        description="List of primary materials, e.g., ['brushed steel', 'carbon fiber', 'matte black polymer'].",
    )
    color_palette: list[str] = Field(description="The main colors of the machine.")
    form_factor: str = Field(
        description="Overall shape and build, e.g., 'bipedal and slender', 'bulky and utilitarian', 'aerodynamic'.",
    )
    key_features: list[str] = Field(
        description="Distinctive features, e.g., ['glowing mono-eye', 'exposed hydraulic pistons', 'multiple sensor arrays'].",
    )
    aesthetic: str = Field(
        description="The overall design style, e.g., 'cyberpunk', 'steampunk', 'minimalist', 'brutalist'.",
    )
    condition: str | None = Field(
        "pristine",
        description="The condition of the machine, e.g., 'pristine', 'weathered', 'battle-damaged'.",
    )


# --- Prompt Generation Schema ---
class GeneratedPrompts(BaseModel):
    prompt: str = Field(
        description="A single, comprehensive, photorealistic prompt describing the entire scene with the character and machine.",
    )
    negative_prompt: str = Field(
        default="blurry, cartoon, deformed, watermark, text, signature, low quality",
        description="A prompt describing unwanted elements to exclude from the generated image.",
    )


# --- Modified Top-Level Class ---
# This class now includes both the analysis profiles and the generated prompts.


class SceneAnalysis(BaseModel):
    """A comprehensive schema to hold both the structured analysis of a scene
    and the generated prompts for image generation.
    """

    character: FacialCompositeProfile | None = Field(
        None,
        description="Forensic profile of the human character in the image, if present.",
    )
    machine: MachineProfile | None = Field(
        None, description="Technical profile of the machine in the image, if present.",
    )


# Define a structured output for the model
class BestFrameSelection(BaseModel):
    best_frame_index: int = Field(
        description="The 0-based index of the best frame from the list.",
    )
    reasoning: str = Field(
        description="A brief explanation for why this frame was chosen.",
    )
