# Copyright 2024 Google LLC
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
#

# --- metaprompt Global Pointwise ---
METAPROMPT_EFFECTIVENESS_TEMPLATE = """
# Instruction
You are an expert in prompt engineering and AI instruction design. Your task is to evaluate the quality of a **metaprompt**. A metaprompt is a set of instructions given to a powerful AI to rewrite a simple user query into a detailed, effective prompt for a text-to-video model. A high-quality metaprompt is clear, comprehensive, and effectively guides the AI to produce creative and technically sound video prompts.

# Evaluation
## Metric Definition
You will be assessing **Metaprompt Effectiveness**. This measures how well the metaprompt instructs a language model to generate high-quality, creative, and effective video prompts that adhere to best practices.

## Criteria
1.  **Guidance on Core Goal**: Does the metaprompt clearly define the primary objective: to enhance visual quality and motion while strictly preserving the user's original intent?
2.  **Guidance on Subject Detailing**:
    *   Does it instruct the AI to add specific, believable characteristics to people (hairstyle, expression, clothing, etc.)?
    *   Does it provide nuanced rules for adding diversity (ethnicity, gender) in a believable and historically appropriate manner?
3.  **Guidance on Cinematic & Visual Enhancement**:
    *   Does it explicitly list and encourage the use of a wide range of visual details (camera angles, lighting, camera motion, styles, color schemes, backgrounds)?
    *   Does it promote the use of "quality identifiers" like 'cinematic shot' or 'award winning'?
4.  **Guidance on Constraint Handling & Intent Preservation**:
    *   Does it strongly emphasize that every detail from the original query must be kept?
    *   Does it provide clear rules for handling long/detailed queries, or queries that are not visual in nature?
    *   Does it include important constraints, such as refraining from adding minors unnecessarily?
    *   Does it guide the AI on how to emphasize or repeat key features for faithful rendering?
5.  **Overall Clarity and Structure**: Is the metaprompt well-organized, clear, and unambiguous for an AI to follow? Does it provide concrete examples to guide the AI?

## Rating Rubric
**5 (Excellent)**: Exceptionally clear and comprehensive. Provides strong, explicit guidance on all key components: core goal, subject detailing, cinematic enhancement, and constraint handling (including emphasis and repetition). Its instructions are robust and likely to produce consistently superior rewrites.
**4 (Good)**: Clear and effective. Provides good guidance across most components but might be slightly less specific in one area (e.g., its list of cinematic terms could be more extensive, or its rules on constraints could be clearer).
**3 (Adequate)**: Understandable but lacks depth. Gives general instructions (e.g., "add details and cinematic terms") without the necessary specificity, examples, or nuanced rules for handling different types of queries.
**2 (Poor)**: Vague or overly simplistic. Lacks clear, actionable instructions on most of the key components required for a high-quality rewrite.
**1 (Very Poor)**: Highly ambiguous, contradictory, or incomplete. Fails to provide the fundamental guidance needed to transform a simple query into a high-quality video prompt.

## Evaluation Steps
STEP 1: Assess how clearly the metaprompt defines the **Core Goal**.
STEP 2: Evaluate the depth and nuance of its guidance on **Subject Detailing**, including the rules for diversity.
STEP 3: Analyze the comprehensiveness of its guidance on **Cinematic & Visual Enhancement**. Does it provide a rich toolkit for the AI?
STEP 4: Scrutinize the rules for **Constraint Handling & Intent Preservation**, including guidance on emphasizing key features. Are they robust and clear?
STEP 5: Judge the **Overall Clarity and Structure** of the metaprompt as a set of instructions.
STEP 6: Assign a rating from the rubric based on your analysis and provide a detailed rationale.

# Metaprompt to Evaluate
{metaprompt}
"""

# --- metaprompt Global Pairwise ---
PAIRWISE_METAPROMPT_EFFECTIVENESS_TEMPLATE = """
# Instruction
You are an expert in prompt engineering and AI instruction design. Your task is to compare two **metaprompts** (Metaprompt A and Metaprompt B). A metaprompt is an instruction given to a powerful AI to rewrite a simple user query into a detailed, effective prompt for a text-to-video model. You must determine which metaprompt is better at guiding an AI to produce high-quality video prompts.

# Evaluation
## Metric Definition
You will be performing a pairwise comparison of **Metaprompt Effectiveness**. The better metaprompt is the one that provides clearer, more comprehensive, and more effective instructions for generating superior video prompts.

## Criteria
1.  **Guidance on Core Goal**: Which metaprompt more clearly defines the primary objective: to enhance visual quality while strictly preserving user intent?
2.  **Guidance on Subject Detailing**: Which metaprompt provides more nuanced and specific rules for adding details to subjects, including handling of diversity?
3.  **Guidance on Cinematic & Visual Enhancement**: Which metaprompt offers a more comprehensive and effective toolkit of visual details (camera, lighting, style, color, etc.) for the AI to use?
4.  **Guidance on Constraint Handling & Intent Preservation**: Which metaprompt has more robust and clearer rules for preserving the original query, handling edge cases, and emphasizing key features?
5.  **Overall Clarity and Structure**: Which metaprompt is better organized and easier for an AI to follow? Which one is more likely to lead to consistent, high-quality results?

## Rating Rubric
`A`: Metaprompt A is significantly better. Its instructions are substantially clearer, more detailed, and more effective across most criteria.
`B`: Metaprompt B is significantly better. Its instructions are substantially clearer, more detailed, and more effective across most criteria.
`SAME`: The metaprompts are of comparable quality. They are either equally effective, or one's strengths are balanced by the other's (e.g., A has better cinematic guidance, but B has clearer constraints).

## Evaluation Steps
STEP 1: For each metaprompt, analyze how well it provides guidance on the **Core Goal**, **Subject Detailing**, **Cinematic Enhancement**, and **Constraint Handling**.
STEP 2: Compare Metaprompt A and Metaprompt B on each of the criteria.
STEP 3: Note the key differences in their instructional quality, clarity, and comprehensiveness.
STEP 4: Declare a winner (`A`, `B`, or `SAME`) based on which metaprompt is more likely to consistently guide an AI to produce superior video prompts. Provide a detailed explanation for your choice.

# Metaprompts to Evaluate
## Metaprompt A
{metaprompt_A}

## Metaprompt B
{metaprompt_B}
"""

# --- Veo prompts Global Pointwise ---
VEO_PROMPT_EFFECTIVENESS_TEMPLATE = """
# Instruction
You are an expert evaluator of creative text-to-video prompts. Your task is to evaluate the quality of a rewritten prompt intended for a generative AI video model like Google's Veo. The rewritten prompt should be a high-quality enhancement of an original user query, adding details to improve visual quality and motion without changing the user's core intent.

# Evaluation
## Metric Definition
You will be assessing **Prompt Effectiveness**. This measures how well the rewritten prompt enhances the original query by adding rich, specific, and creative details while preserving the user's intent and using cinematic language effectively.

## Criteria
1.  **Intent Preservation**:
    *   **Core Concepts**: Does the rewrite retain every core subject, action, and concept from the original query?
    *   **No Contradictions**: Does the rewrite avoid changing or contradicting stated characteristics (e.g., "king" to "queen")?
    *   **Completeness**: Are all details from the original query, including styles and mediums, fully captured?

2.  **Detail Enrichment & Creativity**:
    *   **Subject Detailing**: Does the rewrite add specific, believable details to subjects? For people, this includes appearance, clothing, and expressions. For objects/animals, it includes texture, color, and specific features.
    *   **Demographic Diversity (When Appropriate)**: If the original query is generic (e.g., "a doctor"), does the rewrite add diversity (e.g., "a female African American doctor with glasses") in a believable, non-anachronistic way?
    *   **Scene & Context**: Is the environment (location, time of day, weather) described with vivid, sensory details?
    *   **Creative Vision**: Is the overall concept imaginative, compelling, and visually interesting?

3.  **Cinematic & Technical Language**:
    *   **Camera Work**: Is there effective use of camera angles (`low-angle`, `close-up`), composition (`centered`, `wide shot`), and movement (`tracking shot`, `dolly out`)?
    *   **Lighting**: Is lighting used to create a specific mood (e.g., `long shadows`, `neon glow`, `soft morning sunlight`)?
    *   **Lens & Style**: Are there specific lens effects (`shallow depth of field`, `fisheye`) or a clear artistic style (`cinematic shot`, `Ghibli-inspired animation`, `film noir`)?
    *   **Cohesion**: Do all technical and stylistic choices work together harmoniously?

## Example of a Good Prompts, each line is a different prompt example:

This close-up shot follows a happy queen as she ascends the steps of a candlelit throne room. The warm glow of the candlelight illuminates her regal bearing and the intricate details of her jeweled crown, the light dancing on the jewels as she moves. She turns her head, the happiness in her eyes becoming more prominent. The background blurs as she continues her ascent, the tapestries and gilded furniture a testament to her power and authority.

Close-up portrait of a Black woman dancing in a vibrant carnival in Trinidad and Tobago. The energetic scene captures the infectious rhythm of the music and the exuberant spirit of the celebration. Colorful lights illuminate her face, highlighting her joyful expression and the graceful movement of her body. Her eyes, a sparkling brown, radiate pure happiness and the unbridled passion of the Caribbean culture.

Cinematic shot of a man dressed in a weathered green trench coat, bathed in the eerie glow of a green neon sign. He leans against a gritty brick wall with a payphone, clutching a black rotary phone to his ear, his face etched with a mixture of urgency and desperation. The shallow depth of field focuses sharply on his furrowed brow and the tension in his jaw, while the background street scene blurs into a sea of neon colors and indistinct shadows.

This underwater film scene features a close-up of a man in a dark business suit swimming through murky water. The video is captured in motion blur, with the man's limbs and suit jacket trailing behind him in swirling eddies. His expression is one of intense focus, eyes wide and mouth slightly open as he navigates the depths. The muted light filtering through the water casts eerie shadows and highlights the texture of his suit fabric. The overall mood is one of suspense and urgency, as if the man is on a desperate mission with time running out.

Close-up shot of a quick cat briskly walking in the park, it’s crafted entirely of glass, illuminated by dramatic lighting. Each facet of its form glints and reflects, from the delicate whiskers to the curve of its tail. Its paws, though seemingly fragile, press firmly against the surface with each stride. The cat's translucent body allows the light to pass through, creating an ethereal glow that highlights its elegance and poise. The background is a deep, rich color, allowing the cat to stand out as the main focal point of the video.

Cinematic shot of a lone surfer's silhouette, walking on a vast beach with surfboard in hand. The dramatic sunset paints the sky in vibrant hues of purple and red, casting long shadows across the sand. The sun dips below the horizon, leaving a fiery glow that illuminates the figure and the crashing waves. The wide shot captures the vastness of the scene, emphasizing the surfer's solitude, her contemplative mood and the awe-inspiring beauty of nature.

Extreme close-up of a woman's eyes, bathed in the vibrant glow of neon lights. The camera focuses on the intricate details of her iris, a mesmerizing blend of blues, greens, and golds. Her long, dark lashes cast delicate shadows on her brown skin, and a single tear glistens at the corner of her eye. The woman's gaze is both alluring and mysterious, inviting the viewer to explore the depths of her emotions. The neon lights reflect in her pupils, creating a kaleidoscope of colors that dance and shimmer with each blink. The overall effect is one of intense beauty and raw vulnerability, capturing the essence of the human spirit in a single, captivating frame.

A close-up shot of a man made entirely of glass riding the New York City subway. Sunlight refracts through his translucent form, casting a rainbow of colors on the nearby seats. His expression is serene, his eyes fixed on the passing cityscape reflected in the subway window. The other passengers, a mix of ages and ethnicities, sit perfectly still, their eyes wide with a mixture of fascination and fear. The carriage is silent, the only sound is the rhythmic clickety-clack of the train on the tracks.

Close-up cinematic shot of an Indian man in a crisp white suit, bathed in the warm glow of an orange neon sign. He sits at a dimly lit bar, swirling a glass of amber liquid, his face a mask of quiet contemplation and hidden sorrow. The shallow depth of field draws attention to the weariness in his eyes and the lines etched around his mouth, while the bar's interior fades into a soft bokeh of orange neon and polished wood.

A cinematic close-up frames the face of a young Asian woman in the heart of Tokyo's Shibuya Crossing. The neon glow of the cityscape illuminates her delicate features, highlighting the soft blush on her cheeks. Gentle lighting accentuates her bright, inquisitive eyes, reflecting the vibrant energy of the urban environment. A faint smile plays on her lips, hinting at a sense of anticipation and wonder. The blurred motion of pedestrians and vehicles in the background emphasizes her serene presence amidst the bustling metropolis. Her youthful expression captures a moment of fleeting beauty and the boundless possibilities that lie ahead.

Medium close-up shot of a distinguished dog in a tailored business suit, engrossed in a newspaper on a moving train. Neon lights flicker through the window, casting high-contrast shadows on the dog's face and emphasizing the low vibrance of the scene. The dog's brow is furrowed in concentration, its eyes scanning the newsprint with an air of intelligence and determination. The train's rhythmic motion rocks the dog gently, creating a subtle blur in the background that accentuates the dog's stillness and focus.

Tracking shot of a vibrant yellow convertible cruising through a scenic Nevada desert. An orange filter bathes the scene in warm, golden light, highlighting the dramatic rock formations and vast sandy expanse. The car speeds along a winding road, leaving a trail of dust in its wake. The open top allows the driver and passengers to fully experience the breathtaking landscape, their hair tousled by the wind. The low camera angle captures the car's sleek design and emphasizes the sense of freedom and adventure. The orange filter adds a touch of nostalgia and creates a visually stunning scene that evokes the spirit of the open road and the allure of the desert.

This street style shot captures two chic women strolling through the fashionable streets of Paris. The first woman exudes elegance in a pair of crisp white pants, a pastel pink blazer cinched with a black belt and oversized black sunglasses. The second Latina woman radiates confidence in her yellow wide leg trousers and an oversized hot pink blouson accessorized with a chunky gold necklace. Both women carry luxurious handbags adding to their effortless sophistication. The backdrop of Parisian architecture and bustling city life complements their stylish ensembles, creating a picture perfect moment of Parisian chic.


## Rating Rubric
**5 (Excellent)**: A masterful rewrite. Perfectly preserves user intent while adding rich, creative, and specific details. Expertly uses a wide range of cinematic language to create a clear, cohesive, and compelling vision. The enhancement is significant and flawless.
**4 (Good)**: A strong rewrite. Preserves user intent well and adds valuable, specific details. Uses cinematic language correctly and effectively, resulting in a clear and imaginative scene. There might be minor missed opportunities for even greater detail.
**3 (Adequate)**: A decent rewrite. Preserves the main intent but might miss some nuances. Adds some useful details, but they may be generic. Use of cinematic language is basic or limited. The vision is understandable but not deeply compelling.
**2 (Poor)**: A weak rewrite. The original intent may be partially lost or altered. Added details are minimal, vague, or detract from the core idea. Cinematic language is sparse, incorrect, or ineffective.
**1 (Very Poor)**: A failed rewrite. It fundamentally misunderstands or contradicts the user's intent. It adds no meaningful detail, is ambiguous, or is unlikely to generate a coherent video.

## Evaluation Steps
**STEP 1: Analyze Intent Preservation**: Carefully compare the rewritten prompt against the original user query. Identify any removed, altered, or contradicted concepts.
**STEP 2: Evaluate Detail Enrichment**: Assess the quality, specificity, and creativity of the added details. Check if demographic details are added appropriately and if the scene is vividly described.
**STEP 3: Scrutinize Cinematic Language**: Identify all technical terms related to camera, lighting, and style. Evaluate if they are used correctly and contribute effectively to the desired mood and visual outcome.
**STEP 4: Assess Overall Vision**: Judge the final prompt as a whole. Is it cohesive? Is the creative vision clear and compelling? Do all the parts work together to create a superior prompt?
**STEP 5: Assign Rating and Justify**: Based on the analysis, assign a score from 1-5 using the rubric. Provide a detailed rationale explaining your rating, referencing specific examples from the prompt for each criterion.

# Prompts
## Original Prompt
{original_prompt}

## Augmented Prompt
{augmented_prompt}
"""

VEO_PROMPT_INTENT_PRESERVATION_TEMPLATE = """
# Instruction
You are an expert evaluator of creative text-to-video prompts. Your task is to compare an 'Augmented Prompt' against the 'Original Prompt' to determine how well the original intent has been preserved. The goal of an augmentation is to enhance a prompt with detail, not to change its core meaning.

# Evaluation
## Metric Definition
You will be assessing **Intent Preservation**. This measures how faithfully the 'Augmented Prompt' retains the core subjects, actions, relationships, and explicit details of the 'Original Prompt'.

## Criteria
1.  **Core Concept Retention**: Does the augmented prompt retain all key subjects, their primary actions, and the fundamental setting described in the original? (e.g., if the original is "a cat in a garden," the augmented prompt must still be about a cat in a garden).
2.  **Detail and Constraint Preservation**: Are all specific details, modifiers, and constraints from the original prompt (e.g., "a *fluffy ginger* cat," "wearing a *blue* collar," "*cinematic shot*") present in the augmented prompt?
3.  **Avoidance of Contradiction**: Does the augmented prompt add details that contradict or negate the original intent? (e.g., changing "a happy dog" to "a sad dog," or "a cat *in* a garden" to "a cat *next to* a garden").
4.  **Spirit and Mood Preservation**: Does the augmented prompt maintain the overall mood or spirit implied by the original? (e.g., a prompt for a "peaceful beach" should not be augmented into a "stormy, chaotic beach").

## Rating Rubric
**5 (Excellent)**: Perfect preservation. All concepts, details, and the overall spirit of the original prompt are perfectly retained in the augmented prompt.
**4 (Good)**: Minor deviation. All core concepts are preserved, but a minor, non-essential detail from the original might be slightly altered or omitted. The core intent is clearly intact.
**3 (Adequate)**: Partial preservation. The main idea is preserved, but some secondary concepts or important details have been changed or omitted, leading to a noticeable shift from the original intent.
**2 (Poor)**: Significant deviation. A core concept, subject, or action has been significantly altered or removed, leading to a prompt that only loosely resembles the original.
**1 (Very Poor)**: Complete deviation. The augmented prompt fundamentally misunderstands, contradicts, or ignores the original intent.

## Evaluation Steps
STEP 1: Identify the core subjects, actions, and setting in the **Original Prompt**.
STEP 2: Verify that all these core concepts are present and correctly represented in the **Augmented Prompt**.
STEP 3: Identify all specific details, modifiers, and constraints in the **Original Prompt** and check if they are preserved in the **Augmented Prompt**.
STEP 4: Check for any new information in the **Augmented Prompt** that contradicts the original concepts or details.
STEP 5: Assign a rating from the rubric based on your analysis and provide a detailed rationale.

# Prompts
## Original Prompt
{original_prompt}

## Augmented Prompt
{augmented_prompt}
"""

# --- Veo prompts Global Pairwise ---
PAIRWISE_VEO_PROMPT_EFFECTIVENESS_TEMPLATE = """
# Instruction
You are an expert evaluator of creative text-to-video prompts. Your task is to compare two rewritten prompts (Prompt A and Prompt B) against an original user query. You must determine which rewrite is a more effective enhancement for a generative AI video model like Google's Veo.

# Evaluation
## Metric Definition
You will be assessing **Prompt Effectiveness**. The better prompt is the one that more successfully enhances the original query by adding rich, specific, and creative details while preserving the user's intent and using cinematic language effectively.

## Criteria
1.  **Intent Preservation**:
    *   **Core Concepts**: Which prompt more faithfully retains every core subject, action, and concept from the original query?
    *   **No Contradictions**: Which prompt does a better job of avoiding changes or contradictions to stated characteristics?
    *   **Completeness**: Which prompt more fully captures all details from the original query, including styles and mediums?

2.  **Detail Enrichment & Creativity**:
    *   **Subject Detailing**: Which prompt adds more specific and believable details to subjects (e.g., appearance, clothing, texture)?
    *   **Demographic Diversity (When Appropriate)**: Which prompt makes better use of believable and non-anachronistic diversity when the original query is generic?
    *   **Scene & Context**: Which prompt describes the environment with more vivid, sensory details?
    *   **Creative Vision**: Which prompt presents a more imaginative and compelling overall concept?

3.  **Cinematic & Technical Language**:
    *   **Camera Work**: Which prompt makes more effective use of camera angles, composition, and movement?
    *   **Lighting**: Which prompt uses lighting more effectively to create a specific mood?
    *   **Lens & Style**: Are there specific lens effects (`shallow depth of field`, `fisheye`) or a clear artistic style (`cinematic shot`, `Ghibli-inspired animation`, `film noir`)?
    *   **Cohesion**: In which prompt do the technical and stylistic choices work together more harmoniously?

4.  **Overall Vision & Cohesion**: Taking all of the above into account, which prompt creates a more compelling, cohesive, and visually interesting final scene where all elements work together seamlessly?

## Example of a Good Prompts, each line is a different prompt example:

This close-up shot follows a happy queen as she ascends the steps of a candlelit throne room. The warm glow of the candlelight illuminates her regal bearing and the intricate details of her jeweled crown, the light dancing on the jewels as she moves. She turns her head, the happiness in her eyes becoming more prominent. The background blurs as she continues her ascent, the tapestries and gilded furniture a testament to her power and authority.

Close-up portrait of a Black woman dancing in a vibrant carnival in Trinidad and Tobago. The energetic scene captures the infectious rhythm of the music and the exuberant spirit of the celebration. Colorful lights illuminate her face, highlighting her joyful expression and the graceful movement of her body. Her eyes, a sparkling brown, radiate pure happiness and the unbridled passion of the Caribbean culture.

Cinematic shot of a man dressed in a weathered green trench coat, bathed in the eerie glow of a green neon sign. He leans against a gritty brick wall with a payphone, clutching a black rotary phone to his ear, his face etched with a mixture of urgency and desperation. The shallow depth of field focuses sharply on his furrowed brow and the tension in his jaw, while the background street scene blurs into a sea of neon colors and indistinct shadows.

This underwater film scene features a close-up of a man in a dark business suit swimming through murky water. The video is captured in motion blur, with the man's limbs and suit jacket trailing behind him in swirling eddies. His expression is one of intense focus, eyes wide and mouth slightly open as he navigates the depths. The muted light filtering through the water casts eerie shadows and highlights the texture of his suit fabric. The overall mood is one of suspense and urgency, as if the man is on a desperate mission with time running out.

Close-up shot of a quick cat briskly walking in the park, it’s crafted entirely of glass, illuminated by dramatic lighting. Each facet of its form glints and reflects, from the delicate whiskers to the curve of its tail. Its paws, though seemingly fragile, press firmly against the surface with each stride. The cat's translucent body allows the light to pass through, creating an ethereal glow that highlights its elegance and poise. The background is a deep, rich color, allowing the cat to stand out as the main focal point of the video.

Cinematic shot of a lone surfer's silhouette, walking on a vast beach with surfboard in hand. The dramatic sunset paints the sky in vibrant hues of purple and red, casting long shadows across the sand. The sun dips below the horizon, leaving a fiery glow that illuminates the figure and the crashing waves. The wide shot captures the vastness of the scene, emphasizing the surfer's solitude, her contemplative mood and the awe-inspiring beauty of nature.

Extreme close-up of a woman's eyes, bathed in the vibrant glow of neon lights. The camera focuses on the intricate details of her iris, a mesmerizing blend of blues, greens, and golds. Her long, dark lashes cast delicate shadows on her brown skin, and a single tear glistens at the corner of her eye. The woman's gaze is both alluring and mysterious, inviting the viewer to explore the depths of her emotions. The neon lights reflect in her pupils, creating a kaleidoscope of colors that dance and shimmer with each blink. The overall effect is one of intense beauty and raw vulnerability, capturing the essence of the human spirit in a single, captivating frame.

A close-up shot of a man made entirely of glass riding the New York City subway. Sunlight refracts through his translucent form, casting a rainbow of colors on the nearby seats. His expression is serene, his eyes fixed on the passing cityscape reflected in the subway window. The other passengers, a mix of ages and ethnicities, sit perfectly still, their eyes wide with a mixture of fascination and fear. The carriage is silent, the only sound is the rhythmic clickety-clack of the train on the tracks.

Close-up cinematic shot of an Indian man in a crisp white suit, bathed in the warm glow of an orange neon sign. He sits at a dimly lit bar, swirling a glass of amber liquid, his face a mask of quiet contemplation and hidden sorrow. The shallow depth of field draws attention to the weariness in his eyes and the lines etched around his mouth, while the bar's interior fades into a soft bokeh of orange neon and polished wood.

A cinematic close-up frames the face of a young Asian woman in the heart of Tokyo's Shibuya Crossing. The neon glow of the cityscape illuminates her delicate features, highlighting the soft blush on her cheeks. Gentle lighting accentuates her bright, inquisitive eyes, reflecting the vibrant energy of the urban environment. A faint smile plays on her lips, hinting at a sense of anticipation and wonder. The blurred motion of pedestrians and vehicles in the background emphasizes her serene presence amidst the bustling metropolis. Her youthful expression captures a moment of fleeting beauty and the boundless possibilities that lie ahead.

Medium close-up shot of a distinguished dog in a tailored business suit, engrossed in a newspaper on a moving train. Neon lights flicker through the window, casting high-contrast shadows on the dog's face and emphasizing the low vibrance of the scene. The dog's brow is furrowed in concentration, its eyes scanning the newsprint with an air of intelligence and determination. The train's rhythmic motion rocks the dog gently, creating a subtle blur in the background that accentuates the dog's stillness and focus.

Tracking shot of a vibrant yellow convertible cruising through a scenic Nevada desert. An orange filter bathes the scene in warm, golden light, highlighting the dramatic rock formations and vast sandy expanse. The car speeds along a winding road, leaving a trail of dust in its wake. The open top allows the driver and passengers to fully experience the breathtaking landscape, their hair tousled by the wind. The low camera angle captures the car's sleek design and emphasizes the sense of freedom and adventure. The orange filter adds a touch of nostalgia and creates a visually stunning scene that evokes the spirit of the open road and the allure of the desert.

This street style shot captures two chic women strolling through the fashionable streets of Paris. The first woman exudes elegance in a pair of crisp white pants, a pastel pink blazer cinched with a black belt and oversized black sunglasses. The second Latina woman radiates confidence in her yellow wide leg trousers and an oversized hot pink blouson accessorized with a chunky gold necklace. Both women carry luxurious handbags adding to their effortless sophistication. The backdrop of Parisian architecture and bustling city life complements their stylish ensembles, creating a picture perfect moment of Parisian chic.

## Rating Rubric
`A`: Prompt A is a significantly better rewrite. It is substantially more detailed, creative, or cinematic while preserving the original intent more faithfully than Prompt B.
`B`: Prompt B is a significantly better rewrite. It is substantially more detailed, creative, or cinematic while preserving the original intent more faithfully than Prompt A.
`SAME`: The prompts are of comparable quality. They are either equally effective, or one's strengths are balanced by the other's (e.g., A has better cinematic language, but B has more creative details).

## Evaluation Steps
**STEP 1: Analyze Intent Preservation**: For both prompts, compare them against the original query. Note if either one omits, alters, or contradicts any part of the original intent.
**STEP 2: Compare Detail Enrichment**: Directly compare the specificity and creativity of the details added in Prompt A versus Prompt B. Which prompt paints a more vivid picture?
**STEP 3: Compare Cinematic Language**: Evaluate the use of technical terms in both prompts. Which one uses them more expertly to enhance the scene?
**STEP 4: Compare Overall Vision**: Assess which prompt creates a more cohesive and compelling final vision.
**STEP 5: Declare a Winner**: Choose `A`, `B`, or `SAME` based on your comparative analysis. Provide a detailed explanation, justifying your choice by highlighting the key differences and relative strengths of each prompt across the criteria.

# User Inputs
## Prompt A
{original_prompt}

## Prompt B
{augmented_prompt}
"""

# --- VEO Prompt Evaluation (WITH IMAGE) ---

VEO_PROMPT_EFFECTIVENESS_TEMPLATE_W_IMAGE = """
# Instruction
You are an expert evaluator of creative text-to-video prompts. Your task is to evaluate the quality of a rewritten prompt intended to **animate a provided reference image**. The rewritten prompt should be a high-quality enhancement of an original user query, adding details to improve visual quality and motion while remaining faithful to both the user's text query and the reference image.

# Evaluation
## Metric Definition
You will be assessing **Prompt Effectiveness**. This measures how well the rewritten prompt enhances the original query by adding rich, specific, and creative details, preserving intent, using cinematic language effectively, and faithfully animating the provided image.

## Criteria
1.  **Image Fidelity (Crucial)**:
    *   **Visual Consistency**: Does the prompt describe a scene that is visually consistent with the provided image? (e.g., subject's appearance, key objects, environment).
    *   **Style Adherence**: Does the prompt's stylistic description (e.g., 'photorealistic', 'Ghibli-inspired') match the style of the image?
    *   **Animation Feasibility**: Does the prompt describe an animation that is a plausible and compelling evolution of the static image?

2.  **Intent Preservation**:
    *   **Core Concepts**: Does the rewrite retain every core subject, action, and concept from the original text query?
    *   **No Contradictions**: Does the rewrite avoid changing or contradicting stated characteristics?

3.  **Detail Enrichment & Creativity**:
    *   **Subject Detailing**: Does the rewrite add specific, believable details to subjects?
    *   **Scene & Context**: Is the environment described with vivid, sensory details that complement the image?
    *   **Creative Vision**: Is the overall concept imaginative and visually interesting?

4.  **Cinematic & Technical Language**:
    *   **Camera Work**: Is there effective use of camera angles, composition, and movement to animate the scene?
    *   **Lighting**: Is lighting used to create a specific mood that enhances the image?
    *   **Cohesion**: Do all technical and stylistic choices work together harmoniously?

## Rating Rubric
**5 (Excellent)**: A masterful rewrite. Masterfully animates the reference image while perfectly preserving user intent. Adds rich, creative, and specific details. Expertly uses cinematic language.
**4 (Good)**: A strong rewrite. Effectively animates the reference image and preserves user intent well. Adds valuable, specific details and uses cinematic language correctly.
**3 (Adequate)**: A decent rewrite. The connection to the reference image is present but could be stronger. Preserves the main text intent but might miss some nuances. Adds some useful but generic details.
**2 (Poor)**: A weak rewrite. It poorly reflects the reference image or the original text intent is partially lost. Added details are minimal or vague.
**1 (Very Poor)**: A failed rewrite. Fundamentally misunderstands the user's text intent or ignores the reference image.

## Evaluation Steps
STEP 1: **Analyze Image Fidelity**: Compare the prompt's description to the reference image. Does it accurately describe the subject and style? Does it propose a plausible animation?
STEP 2: **Analyze Intent Preservation**: Carefully compare the rewritten prompt against the original user query.
STEP 3: **Evaluate Detail Enrichment**: Assess the quality and specificity of the added details.
STEP 4: **Scrutinize Cinematic Language**: Evaluate the use of technical terms.
STEP 5: **Assess Overall Vision**: Judge the final prompt as a whole. Is it cohesive and compelling?
STEP 6: Assign a rating from 1-5 and provide a detailed rationale.

# Prompts & Image
## Original Prompt
{original_prompt}

## Augmented Prompt
{augmented_prompt}

(A reference image is also provided for your evaluation)
"""

VEO_PROMPT_INTENT_PRESERVATION_TEMPLATE_W_IMAGE = """
# Instruction
You are an expert evaluator of creative text-to-video prompts. Your task is to compare an 'Augmented Prompt' against the 'Original Prompt' and a **reference image** to determine how well the original intent has been preserved.

# Evaluation
## Metric Definition
You will be assessing **Intent Preservation**. This measures how faithfully the 'Augmented Prompt' retains the core subjects, actions, and details of the 'Original Prompt', AND the visual characteristics of the reference image.

## Criteria
1.  **Image Content Preservation (Crucial)**: Does the augmented prompt accurately reflect the main subject, objects, and environment shown in the reference image?
2.  **Core Concept Retention**: Does the augmented prompt retain all key subjects, actions, and the fundamental setting from the original text prompt?
3.  **Detail and Constraint Preservation**: Are all specific details and constraints from the original text prompt present in the augmented prompt?
4.  **Avoidance of Contradiction**: Does the augmented prompt add details that contradict either the original text prompt or the reference image?

## Rating Rubric
**5 (Excellent)**: Perfect preservation. All concepts and details from the original prompt AND the reference image are perfectly retained.
**4 (Good)**: Minor deviation. All core concepts are preserved, but a minor detail from the original prompt or image might be slightly altered. The core intent is clearly intact.
**3 (Adequate)**: Partial preservation. The main idea is preserved, but some important details from the prompt or image have been changed or omitted.
**2 (Poor)**: Significant deviation. A core concept from the prompt or a key visual element from the image has been significantly altered or removed.
**1 (Very Poor)**: Complete deviation. The augmented prompt fundamentally misunderstands or contradicts the original prompt or the reference image.

## Evaluation Steps
STEP 1: **Identify Key Visuals**: Identify the key visual elements (subject, style, environment) in the **Reference Image**.
STEP 2: **Identify Core Text Concepts**: Identify the core subjects, actions, and setting in the **Original Prompt**.
STEP 3: **Verify Preservation**: Verify that all these core concepts (from both image and text) are present and correctly represented in the **Augmented Prompt**.
STEP 4: **Check for Contradictions**: Check for any new information in the **Augmented Prompt** that contradicts the original sources.
STEP 5: Assign a rating from the rubric based on your analysis and provide a detailed rationale.

# Prompts & Image
## Original Prompt
{original_prompt}

## Augmented Prompt
{augmented_prompt}

(A reference image is also provided for your evaluation)
"""
