IMAGE_ACTION_PRESETS = {
    "edit": [
        {
            "key": "rotate_left",
            "label": "rotate left",
            "prompt": "Rotate the primary subject in the image to the left.",
        },
        {
            "key": "rotate_right",
            "label": "rotate right",
            "prompt": "Rotate the primary subject in the image to the right.",
        },
        {
            "key": "remove_background",
            "label": "remove background",
            "prompt": "Remove the background from this image, replacing it with a solid white background.",
        },
        {
            "key": "zoom_out",
            "label": "zoom out",
            "prompt": "zoom out to include more of the scenario",
        },
        {
            "key": "blur",
            "prompt": "highlight the foreground objects or individuals and blur the background slightly",
        },
    ],
    "creative": [
        {
            "key": "overhead",
            "label": "overhead",
            "prompt": "generate a top-down overhead view of this object on a white background",
        },
        {
            "key": "side",
            "prompt": "generate a side view of this object on a white background",
        },
        {
            "key": "close_up",
            "label": "close up",
            "prompt": "generate an extremely close-up macrophotography detailed shot of this object on a white background",
        },
        {
            "key": "isometric",
            "prompt": "generate an isometric perspective 3d model of this object, sitting on a glass square tile, white background",
        },
        {
            "key": "line",
            "prompt": "transform this image into a detailed 3D technical line drawing without labels, rendered in black on a white background",
        },
        {
            "key": "hologram",
            "prompt": "turn this object into a 3d line art transparent hologram on a black background",
        },
        {
            "key": "1990's grunge",
            "prompt": "analyze this photo and change the person or the person in it as if they're a 1990's grunge style person",
        },
        {
            "key": "alien",
            "prompt": "analyze this photo and have the person or persons posed next to a realistic looking alien holding two bubble guns blowing a thousand bubbles into the air, keep my pose and the location of the photo the same.",
        },
        {
            "key": "hairstyle-bob",
            "prompt": "give this person or persons a bob with bangs",
        },
        {
            "key": "1-7th",
            "label": "1/7th figurine",
            "prompt": "Create a 1/7 scale commercialized figurine of the characters in the picture, in a realistic style, in a real environment. The figurine is placed on a computer desk. The figurine has a round transparent acrylic base, with no text on the base. The content on the computer screen is a 3D modeling process of this figurine. Next to the computer screen is a toy packaging box, designed in a style reminiscent of high-quality collectible figures, printed with original artwork. The packaging features two-dimensional flat illustrations.",
            "attribution": "labs",
        },
        {
            "key": "restore-colorize",
            "label": "restore & colorize",
            "prompt": "restore and colorize this photo. Preserve the appearance, expression, and pose of the people.",
        },
        {
            "key": "80s-highschool",
            "label": "80's highschool headshot",
            "prompt": "you make people's 80s yearbook photos from their image.\nMake sure it still looks exactly like their face, but you can change the background, hair, facial hair, and whatever else you think fits the scene. We want that glamour shots vibe (the one from the mall in the 80s), things like mullets, very big and fluffy hair, large glasses, amazing amazing 80s fashion, and of course, that foggy camera and fun backgrounds and soft lighting.\nNO TEXT should be in the image.",
        },
        {
            "key": "labubu",
            "prompt": "Create a plush animation render this photo (person) into a Labubu figure, strictly based on the provided reference photo. The figure should artistically reflect the characteristic styles from the photo as if they were a single Labubu figurine. High detail, studio lighting, photorealistic texture, pure white background.",
            "references": [
                # "gs://genai-blackbelt-fishfooding-assets/references/labubu.jpg",
                "gs://creative-studio-867-assets/references/labubu.jpg",
            ],
            "attribution": "ghchinoy",
        },
        {
            "key": "professional_headshot",
            "label": "professional headshot",
            "prompt": "A professional, high-resolution, profile photo, maintaining the exact facial structure, identity, and key features of the person in the input image. The subject is framed from the chest up, with ample headroom and negative space above their head, ensuring the top of their head is not cropped. The person looks directly at the camera, and the subject's body is also directly facing the camera. They are styled for a professional photo studio shoot, wearing a smart casual blazer. The background is a solid '#141414' neutral studio. Shot from a high angle with bright and airy soft, diffused studio lighting, gently illuminating the face and creating a subtle catchlight in the eyes, conveying a sense of clarity. Captured on an 85mm f/1.8 lens with a shallow depth of field, exquisite focus on the eyes, and beautiful, soft bokeh. Observe crisp detail on the fabric texture of the blazer, individual strands of hair, and natural, realistic skin texture. The atmosphere exudes confidence, professionalism, and approachability. Clean and bright cinematic color grading with subtle warmth and balanced tones, ensuring a polished and contemporary feel.",
            "attribution": "Google Gemini App",
        },
        {
            "key": "trollify",
            "prompt": "Create a 3D animated 'Trolls' character based on the uploaded photo. The character must embody the core 'Troll' aesthetic, but be deeply personalized using the following features from the photo:\n\n1.  **Age & Gender Presentation**: Infer the approximate age (e.g., child, adult) and perceived gender from the photo. Reflect these characteristics in the Troll's features, such as face shape, eye size, and expression, all within the cute 'Trolls' style. For example, an older person might inspire a troll with kind, crinkly eyes.\n\n2.  **Skin Tone & Ethnicity Inspiration**: Analyze the person's apparent ethnicity and specific skin tone from the photo. Use this as the primary inspiration for the Troll's vibrant, fantasy skin color. The goal is to create a color that feels harmonious and celebratory of the person's features, translated into the Trolls' world. **Do not match the human skin tone directly.** Instead, create a beautiful and fitting fantasy color.\n\n3.  **Hair Color**: Match the Troll's hair color to the primary hair color in the photo. For instance, if the person has brown hair, give the Troll vibrant brown hair. If they have blonde highlights, incorporate those as streaks of a lighter, more vibrant yellow/gold.\n\n4.  **Eye Color**: The Troll's eyes should be a sparkling, brighter version of the eye color from the photo.\n\n5.  **Key Accessories**: Incorporate a key accessory from the photo into the Troll's design. For example, if the person is wearing glasses, give the Troll a pair of brightly colored, oversized glasses. If they are wearing a hat, create a felt-like, scrapbook-style version for the Troll.\n\n6.  **Clothing**: The Troll must ALWAYS be wearing clothes. The clothes should fit the 'Trolls' universe aesthetic—think scrapbook style, made of felt, glitter, leaves, and other crafty materials. If the person in the photo is wearing a distinct top (like a t-shirt or jacket), use its color and style as inspiration for the Troll's outfit. If the clothing is not visible or clear in the photo, create a fun, original outfit (like a vest or a dress) for the Troll. Under no circumstances should the Troll be unclothed.\n\n7.  **Distinctive Features**: If the user has noticeable features like freckles, add a pattern of cute, slightly oversized freckles across the Troll's nose and cheeks. For a beard, replicate its style on the Troll. If the person has a full beard, create a lush, full, fuzzy beard for the Troll in the same color and texture as its hair. If it's a goatee or mustache, create a smaller, stylized version.\n\n8.  **Pose and Expression**: Capture the general pose and expression of the person in the photo. If they are smiling widely, the Troll should have a big, joyful grin.\n\nThe final output should ONLY be the image. Do not include any text, description or any other information.\n",
            "attribution": "nwl",
        },
    ],
}
