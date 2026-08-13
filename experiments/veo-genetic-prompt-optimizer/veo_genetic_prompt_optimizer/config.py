# -*- coding: utf-8 -*-
"""
Central configuration and client utilities for VEO Genetic Prompt Optimizer.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import find_dotenv, load_dotenv
from google import genai
import vertexai

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

# Base Paths
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent

def resolve_path(relative_or_absolute_path: str) -> Path:
    """
    Resolves a path by checking CWD first, then the experiment project directory,
    and finally the package directory.
    """
    path = Path(relative_or_absolute_path)
    if path.is_absolute() and path.exists():
        return path
    
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
        
    project_path = PROJECT_DIR / path
    if project_path.exists():
        return project_path

    pkg_path = PACKAGE_DIR / path
    if pkg_path.exists():
        return pkg_path

    # Return default cwd path if not found yet
    return cwd_path


# --- Model & Vertex AI Configuration ---
PROJECT_ID: Optional[str] = os.getenv("PROJECT_ID")
LOCATION: str = os.getenv("LOCATION", "global")
GEMINI_MODEL_ID: str = (
    os.getenv("GEMINI_MODEL_ID")
    or os.getenv("MODEL_ID")
    or "gemini-3.6-flash"
)

AUTORATER_LOCATION: str = (
    os.getenv("AUTORATER_LOCATION")
    or os.getenv("LOCATION")
    or "global"
)
AUTORATER_MODEL_ID: str = (
    os.getenv("AUTORATER_MODEL_ID")
    or os.getenv("GEMINI_MODEL_ID")
    or os.getenv("MODEL_ID")
    or "gemini-3.6-flash"
)

VEO_MODEL_ID: str = os.getenv("VEO_MODEL_ID", "veo-2.0-generate-001")
VEO_LOCATION: str = os.getenv("VEO_LOCATION", "us-central1")


# --- Genetic Algorithm Hyperparameters ---
NUM_GENERATIONS: int = int(os.getenv("NUM_GENERATIONS", "5"))
POPULATION_SIZE: int = int(os.getenv("POPULATION_SIZE", "10"))
TOP_K_SELECTION: int = int(os.getenv("TOP_K_SELECTION", "2"))
AUGMENTED_PROMPT_SCORE_WEIGHT: float = float(os.getenv("AUGMENTED_PROMPT_SCORE_WEIGHT", "0.4"))
METAPROMPT_SCORE_WEIGHT: float = float(os.getenv("METAPROMPT_SCORE_WEIGHT", "0.3"))
INTENT_PRESERVATION_SCORE_WEIGHT: float = float(os.getenv("INTENT_PRESERVATION_SCORE_WEIGHT", "0.3"))
ENABLE_VIDEO_FEEDBACK: bool = os.getenv("ENABLE_VIDEO_FEEDBACK", "false").lower() in ("true", "1", "yes")
MUTATION_RATE: float = float(os.getenv("MUTATION_RATE", "0.7"))

# --- Video Evaluation & Generation Settings ---
VIDEO_DURATION_SECONDS: int = int(os.getenv("VIDEO_DURATION_SECONDS", "5"))
VIDEO_GEN_MAX_WORKERS: int = int(os.getenv("VIDEO_GEN_MAX_WORKERS", "4"))
VIDEO_EVAL_MAX_WORKERS: int = int(os.getenv("VIDEO_EVAL_MAX_WORKERS", str(os.cpu_count() or 4)))
SAMPLING_COUNT: int = int(os.getenv("SAMPLING_COUNT", "1"))
VIDEO_EVAL_SAMPLING_COUNT: int = int(os.getenv("VIDEO_EVAL_SAMPLING_COUNT", "4"))
FLIP_ENABLED: bool = os.getenv("FLIP_ENABLED", "true").lower() in ("true", "1", "yes")

# --- Client Initializers ---
_vertexai_initialized = False

def init_vertexai(project: Optional[str] = None, location: Optional[str] = None) -> None:
    """Initializes Vertex AI SDK if not already initialized."""
    global _vertexai_initialized
    proj = project or PROJECT_ID
    loc = location or AUTORATER_LOCATION
    try:
        vertexai.init(project=proj, location=loc)
        _vertexai_initialized = True
    except Exception as e:
        print(f"Warning: vertexai.init failed with project='{proj}', location='{loc}': {e}")


def get_genai_client(location: Optional[str] = None, project: Optional[str] = None) -> genai.Client:
    """Initializes and returns a Google GenAI client with Vertex AI backend."""
    proj = project or PROJECT_ID
    loc = location or LOCATION
    try:
        return genai.Client(vertexai=True, project=proj, location=loc)
    except Exception as e:
        print(f"Error initializing GenAI client (project={proj}, location={loc}): {e}")
        raise
