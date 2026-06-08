from langchain_openai import ChatOpenAI
from backend.config import settings

def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """
    Returns an instance of ChatOpenAI configured with environment settings.
    This works with OpenAI API or any OpenAI-compatible custom endpoints (Ollama, LM Studio, Groq, etc.).
    """
    api_key = settings.openai_api_key or "placeholder_key"
    
    # Check if a custom API base is defined in settings
    api_base = settings.openai_api_base
    if api_base == "https://api.openai.com/v1" and not settings.openai_api_key:
        # If no key is set and it points to OpenAI, we run in a safe mock mode
        # or we will let it raise a clear warning in the console
        pass
        
    return ChatOpenAI(
        model=settings.openai_model,
        openai_api_key=api_key,
        openai_api_base=api_base,
        temperature=temperature
    )
