import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Model Settings
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
FACT_CHECK_MODEL = "openai/gpt-4o-mini"
SUMMARIZATION_MODEL = "openai/gpt-4o-mini"

# Workflow Settings
CONFIDENCE_THRESHOLD = 0.8
MAX_RETRIES = 1
ADD_MAX_RESULTS = 2

# Validate required environment variables
if not SERPER_API_KEY:
    raise ValueError("SERPER_API_KEY environment variable is not set")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY environment variable is not set")
