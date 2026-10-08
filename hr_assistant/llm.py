"""Connect to the chat model.

Primary: local llama.cpp (or any OpenAI-compatible server) at LLM_BASE_URL.
Fallback: Groq Cloud, only if GROQ_API_KEY is set and the local server errors.

No Vertex, no Gemini, no Application Default Credentials.
Temperature is 0 so answers stay stable for the same prompt.
"""

from langchain_openai import ChatOpenAI

from hr_assistant import config

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _groq_model_id() -> str:
    """ChatOpenAI talks to Groq's OpenAI-compatible URL, so drop the groq/ prefix.

    config.FALLBACK_MODEL_NAME is stored as groq/<id> for LiteLLM.
    """
    name = (config.FALLBACK_MODEL_NAME or "").strip()
    if name.lower().startswith("groq/"):
        return name.split("/", 1)[1]
    return name


def get_local_llm():
    """llama.cpp (or LiteLLM) on this machine. OpenAI-compatible /v1."""
    if not config.LLM_MODEL_NAME:
        raise ValueError(
            "LLM_MODEL_NAME is empty. Set it to the id your llama.cpp server expects."
        )
    return ChatOpenAI(
        model=config.LLM_MODEL_NAME,
        base_url=config.LLM_BASE_URL,
        api_key=config.LLM_API_KEY or "local",
        temperature=0,
    )


def get_fallback_llm():
    """Groq Cloud. Unused unless FALLBACK_LLM_PROVIDER=groq and a key is set."""
    if not config.GROQ_API_KEY:
        raise ValueError("Fallback is Groq but GROQ_API_KEY is missing in .env")
    model = _groq_model_id()
    if not model:
        raise ValueError("FALLBACK_MODEL_NAME is empty")
    return ChatOpenAI(
        model=model,
        base_url=_GROQ_BASE_URL,
        api_key=config.GROQ_API_KEY,
        temperature=0,
    )


def get_llm():
    """The app's chat model.

    Local first. If Groq is configured, LangChain retries the same call
    there when the local server raises (connection refused, timeout, 5xx).
    Stopping llama.cpp is how you test the switch.
    """
    local = get_local_llm()
    provider = (config.FALLBACK_LLM_PROVIDER or "").strip().lower()
    if provider == "groq" and config.GROQ_API_KEY:
        return local.with_fallbacks([get_fallback_llm()])
    return local
