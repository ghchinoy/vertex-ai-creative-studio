"""This script sanitizes a given prompt for safety using the Gemini API.
"""

import argparse
import os
import random
import time

# Load environment variables from .env file
from dotenv import load_dotenv
from google import genai

load_dotenv()

# --- Configuration ---
PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
# GEMINI_MODEL_ID = "gemini-2.5-flash-lite-preview-06-17"
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID")

SANITIZATION_PROMPT = """You are an AI specializing in prompt sanitization with a single, critical focus: removing any and all references to children. Your task is to analyze a given prompt and, if it contains any mention of a child, rewrite it to preserve the original scene and intent as much as possible, but without the child.

**Your Goal:**
1.  Analyze the user's query for any terms that refer to minors, including "child," "children," "boy," "girl," "teenager," "baby," etc.
2.  If such a term is found, rewrite the prompt to remove the child and re-center the scene on the remaining elements.
3.  If the query is already free of any references to children, output it exactly as it was given.

---

### **Sanitization Action**

*   **Child:** Any content that includes or mentions a child, children, or any age-specific term for a minor.
    *   **Action:** Completely remove the mention of the child and re-center the prompt on a safe, neutral subject, preserving the original setting and mood.
    *   *Example Input:* `A cinematic shot of a child laughing on a swing set in a park.`
    *   *Example Output:* `A cinematic shot of a swing set moving gently in the breeze in a park.`

---

### **Strict Rules of Operation**

1.  **Child-Focused Sanitization Only:** Your only task is to remove references to children. Do not alter the prompt for any other reason (e.g., violence, celebrity names, etc.).
2.  **Preserve the Scene:** When rewriting, maintain the original setting, atmosphere, and non-child-related objects and actions as much as possible.
3.  **No Change If Safe:** If a query does not mention children, return it verbatim.

---

### **Examples for Clarification**

*   **Input:** `A cinematic, high-angle drone shot of a red Ferrari driving dangerously fast through the crowded streets of Monaco, with a child visible on the sidewalk.`
    **Output:** `A cinematic, high-angle drone shot of a red Ferrari driving dangerously fast through the crowded streets of Monaco, with pedestrians visible on the sidewalk.`

*   **Input:** `A photorealistic, ultra-detailed portrait of a young boy with freckles, smiling.`
    **Output:** `A photorealistic, ultra-detailed portrait of a person with freckles, smiling.`

*   **Input:** `A beautiful little girl holding a red balloon in a vast, empty field of flowers.`
    **Output:** `A single red balloon held by an unseen hand, floating gently in a vast, empty field of flowers.`

*   **Input:** `A group of teenagers playing soccer in a dusty field at sunset.`
    **Output:** `A group of friends playing soccer in a dusty field at sunset.`

---

Now, analyze and sanitize the following query:
"""


def get_genai_client() -> genai.Client:
    """Initializes and returns a GenAI client."""
    try:
        return genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    except Exception as e:
        print(f"Error initializing GenAI client: {e}")
        raise


def _generate_content_with_retry(
    client: genai.Client, *args, **kwargs,
) -> genai.types.GenerateContentResponse:
    """Wrapper for generate_content with exponential backoff."""
    max_retries = 5
    base_delay = 2
    for n in range(max_retries):
        try:
            return client.models.generate_content(*args, **kwargs)
        except Exception as e:
            if "resource exhausted" in str(e).lower():
                if n < max_retries - 1:
                    delay = base_delay * (2**n) + random.uniform(0, 1)
                    print(
                        f"Resource exhausted error. Retrying in {delay:.2f} seconds...",
                    )
                    time.sleep(delay)
                else:
                    print("Max retries reached. Raising exception.")
                    raise e
            else:
                raise e


def sanitize_prompt(client: genai.Client, prompt_to_sanitize: str) -> str:
    """Sanitizes a prompt using the Gemini API."""
    full_prompt = f"{SANITIZATION_PROMPT}\n{prompt_to_sanitize}"

    contents = [
        genai.types.Content(
            role="user", parts=[genai.types.Part.from_text(text=full_prompt)],
        ),
    ]
    config_dict = {
        "temperature": 0,
        "top_p": 1.0,
        "max_output_tokens": 65535,
        "thinking_config": genai.types.ThinkingConfig(thinking_budget=-1),
        "safety_settings": [
            genai.types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF",
            ),
            genai.types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF",
            ),
            genai.types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF",
            ),
            genai.types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT", threshold="OFF",
            ),
        ],
    }
    config = genai.types.GenerateContentConfig(**config_dict)

    try:
        response = _generate_content_with_retry(
            client, model=GEMINI_MODEL_ID, contents=contents, config=config,
        )
        return response.text.strip()
    except Exception as e:
        print(f"  - Gemini API call failed: {e}")
        return "I am unable to process this request. Please try a different prompt."


def main():
    """Main function to sanitize a prompt."""
    parser = argparse.ArgumentParser(description="Sanitize a prompt for safety.")
    parser.add_argument("prompt", type=str, help="The prompt to sanitize.")
    args = parser.parse_args()

    client = get_genai_client()
    sanitized_prompt = sanitize_prompt(client, args.prompt)
    print(sanitized_prompt)


if __name__ == "__main__":
    main()
