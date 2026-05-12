"""Unified LLM interface.

All modules call `complete(prompt)` — the provider is selected via
REVIEWTRACE_LLM_PROVIDER (anthropic | openai | google | deepseek).

Install extras for non-default providers:
  pip install "reviewtrace[openai]"     # also covers deepseek
  pip install "reviewtrace[google]"
  pip install "reviewtrace[all-llm]"
"""

from reviewtrace.config.settings import (
    ANTHROPIC_API_KEY,
    DEEPSEEK_API_KEY,
    GOOGLE_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
)


def complete(prompt: str, max_tokens: int = 1024) -> str:
    """Send a prompt and return the response text.

    Raises RuntimeError if the provider's API key is not configured.
    """
    if LLM_PROVIDER == "anthropic":
        return _complete_anthropic(prompt, max_tokens)
    elif LLM_PROVIDER == "openai":
        return _complete_openai(prompt, max_tokens)
    elif LLM_PROVIDER == "google":
        return _complete_google(prompt, max_tokens)
    elif LLM_PROVIDER == "deepseek":
        return _complete_deepseek(prompt, max_tokens)
    else:
        raise ValueError(
            f"Unknown LLM provider: '{LLM_PROVIDER}'. "
            "Set REVIEWTRACE_LLM_PROVIDER to: anthropic | openai | google | deepseek"
        )

# Provider implementations
def _complete_anthropic(prompt: str, max_tokens: int) -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic package not installed: pip install anthropic")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    for block in message.content:
        if block.type == "text":
            return block.text
    return ""


def _complete_openai(prompt: str, max_tokens: int) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    try:
        import openai
    except ImportError:
        raise ImportError('openai package not installed: pip install "reviewtrace[openai]"')

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def _complete_deepseek(prompt: str, max_tokens: int) -> str:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY is not set.")
    try:
        import openai
    except ImportError:
        raise ImportError('openai package not installed: pip install "reviewtrace[openai]"')

    client = openai.OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )
    response = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


def _complete_google(prompt: str, max_tokens: int) -> str:
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set.")
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError('google-generativeai not installed: pip install "reviewtrace[google]"')

    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(
        model_name=LLM_MODEL,
        generation_config=genai.GenerationConfig(max_output_tokens=max_tokens),
    )
    response = model.generate_content(prompt)
    return response.text
