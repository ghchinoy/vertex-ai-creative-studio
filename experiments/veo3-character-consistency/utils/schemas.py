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
    style: str
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


# --- Prompt Generation Schema ---
class GeneratedPrompts(BaseModel):
    prompt: str = Field(
        description="A detailed, photorealistic prompt for an image generation model.",
    )
    negative_prompt: str = Field(
        description="A prompt describing unwanted elements to exclude from the generated image.",
    )
