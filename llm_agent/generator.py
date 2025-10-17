# llm_agent/generator.py
import os
import requests

def generate_app_code(prompt: str) -> str:
    """
    Uses AI Pipe to generate Python FastAPI app code from a natural-language brief.
    """

    api_url = os.getenv("AI_PIPE_API_URL")
    api_key = os.getenv("AI_PIPE_API_KEY")

    if not api_url or not api_key:
        raise ValueError("Missing AI_PIPE_API_URL or AI_PIPE_API_KEY environment variables.")

    full_prompt = f"""
    You are an AI developer that writes fully working FastAPI apps.
    Generate complete, minimal, and runnable Python code for:
    {prompt}

    Include all necessary imports and ensure the code runs with:
        uvicorn app:app --reload
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gpt-4o-mini",  # or model specified by AI Pipe
        "messages": [
            {"role": "system", "content": "You are a professional Python app generator."},
            {"role": "user", "content": full_prompt},
        ],
        "temperature": 0.4,
    }

    response = requests.post(api_url, headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(f"AI Pipe request failed: {response.status_code} {response.text}")

    data = response.json()

    # Adjust depending on AI Pipe’s exact schema — most follow OpenAI's structure
    try:
        code = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected AI Pipe response: {data}")

    return code.strip()

