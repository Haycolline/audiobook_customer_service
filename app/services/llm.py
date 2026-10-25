from openai import OpenAI

from app.config import settings

_client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)


def generate(messages: list[dict[str, str]]) -> str:
    resp = _client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        temperature=0.3,
    )
    return resp.choices[0].message.content or ""
