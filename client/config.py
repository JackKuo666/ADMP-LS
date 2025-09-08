import os
import json
from dotenv import load_dotenv

load_dotenv()
env = os.getenv

# Model mapping
MODEL_OPTIONS = {
    'OpenAI': 'gpt-4o',
    'Antropic': 'claude-3-5-sonnet-20240620',
    'Google': 'gemini-2.0-flash-001',
    'Bedrock': 'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
    'Groq' : 'meta-llama/llama-4-scout-17b-16e-instruct'
    }

# Streamlit defaults
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 1.0

# Environment variable configurations for default settings
DEFAULT_ENV_CONFIG = {
    'OpenAI': {
        'api_key': env('OPENAI_API_KEY'),
        'base_url': env('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    },
    'Antropic': {
        'api_key': env('ANTHROPIC_API_KEY'),
        'base_url': env('ANTHROPIC_BASE_URL', 'https://api.anthropic.com')
    },
    'Google': {
        'api_key': env('GOOGLE_API_KEY'),
        'base_url': env('GOOGLE_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta')
    },
    'Bedrock': {
        'region_name': env('AWS_REGION', 'us-east-1'),
        'aws_access_key': env('AWS_ACCESS_KEY_ID'),
        'aws_secret_key': env('AWS_SECRET_ACCESS_KEY')
    },
    'Groq': {
        'api_key': env('GROQ_API_KEY'),
        'base_url': env('GROQ_BASE_URL', 'https://api.groq.com/openai/v1')
    }
}

# Load server configuration
config_path = os.path.join(os.path.dirname(__file__), 'servers_config.json')
if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        SERVER_CONFIG = json.load(f)
else:
    # Fallback: try relative to current working directory
    config_path = os.path.join('.', 'servers_config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            SERVER_CONFIG = json.load(f)
    else:
        # Default empty configuration if file not found
        SERVER_CONFIG = {"mcpServers": {}}