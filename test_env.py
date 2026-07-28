from dotenv import load_dotenv
import os

load_dotenv()
print("ENV_LOADED:", "ANTHROPIC_API_KEY" in os.environ)
