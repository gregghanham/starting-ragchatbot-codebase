#!/Users/gregghanham/Courses/AI/DeepLearning/starting_codebase/.venv/bin/python3

from dotenv import load_dotenv
from pathlib import Path
import os
from anthropic import Anthropic
from config import config

# Always resolve from project root
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

resp = client.messages.create(
    model=config.ANTHROPIC_MODEL,
    max_tokens=20,
    messages=[{"role": "user", "content": "Reply with OK"}],
)

print(resp.content[0].text)
