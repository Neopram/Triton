import httpx
import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


async def query_deepseek(prompt: str) -> str:
    if not DEEPSEEK_API_KEY:
        raise ValueError("Missing DeepSeek API key in environment variables.")

    payload = {
        "model": "deepseek-coder",
        "messages": [
            {"role": "system", "content": "You are a maritime business intelligence assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 1000
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(DEEPSEEK_API_URL, json=payload, headers=headers)

    if response.status_code != 200:
        raise RuntimeError(f"DeepSeek API error {response.status_code}: {response.text}")

    result = response.json()
    return result["choices"][0]["message"]["content"].strip()
