import json
import os
import re

try:
    import openai
except ImportError:  # pragma: no cover
    openai = None


print("openai_utils: loaded")


def is_openai_enabled() -> bool:
    if openai is None:
        print("openai_utils: OpenAI library not installed")
        return False

    api_type = os.getenv("OPENAI_API_TYPE", "").lower()
    key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    version = os.getenv("OPENAI_API_VERSION")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    enabled = all([api_type == "azure", key, endpoint, version, deployment])
    if not enabled:
        print("openai_utils: Azure OpenAI configuration missing or incomplete")
    return enabled


def _configure_client():
    if openai is None:
        raise ImportError("openai package is not installed")

    openai.api_type = os.getenv("OPENAI_API_TYPE", "azure")
    openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    openai.api_version = os.getenv("OPENAI_API_VERSION", "")
    openai.api_key = os.getenv("AZURE_OPENAI_API_KEY", "")


def parse_json_response(response_text: str) -> dict:
    try:
        trimmed = response_text.strip()
        if not trimmed.startswith("{"):
            trimmed = trimmed[trimmed.index("{") : trimmed.rindex("}") + 1]
        return json.loads(trimmed)
    except Exception as exc:
        print(f"openai_utils: failed to parse JSON response: {exc}")
        raise


def query_openai(prompt: str, deployment: str | None = None, max_tokens: int = 512, temperature: float = 0.0) -> str:
    if not is_openai_enabled():
        raise ValueError("OpenAI is not configured")

    _configure_client()
    deployment = deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT")

    print(f"openai_utils: querying Azure OpenAI deployment={deployment}")

    response = openai.responses.create(
        model=deployment,
        input=prompt,
        max_output_tokens=max_tokens,
        temperature=temperature,
    )

    text = getattr(response, "output_text", None)
    if text is None:
        try:
            text = "".join(
                item.get("content", "")
                for item in getattr(response, "output", [])
                if item.get("type") == "output_text"
            )
        except Exception:
            text = str(response)

    print(f"openai_utils: got response length={len(text)}")
    return text.strip()


def query_openai_json(prompt: str, deployment: str | None = None, max_tokens: int = 512, temperature: float = 0.0) -> dict:
    text = query_openai(prompt, deployment=deployment, max_tokens=max_tokens, temperature=temperature)
    return parse_json_response(text)
