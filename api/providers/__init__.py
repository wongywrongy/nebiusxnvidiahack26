"""Live providers: Token Factory (Nemotron) and Tavily. Pipeline code reaches them through
llm.router and web.WebClient, which answer from fixtures in mock mode."""


class ProviderError(RuntimeError):
    pass


class AuthError(ProviderError):
    """401/403: the key is missing, wrong or not allowed. Never retried or worked around."""


class RateLimited(ProviderError):
    """429 (or Tavily's 432/433 plan limits) after backoff. Never worked around."""


def failure_reason(error: Exception) -> str:
    """Public stage failures should explain what to do, without exposing a provider response."""
    from ..config import redact

    if isinstance(error, RateLimited):
        provider = "Tavily" if "Tavily" in str(error) else "Token Factory"
        return f"{provider} rate limit; try again in a minute"
    if isinstance(error, AuthError):
        return "The provider could not authenticate; ask the site owner to check its configuration"
    if isinstance(error, ProviderError):
        if "MAX_OUTPUT_TOKENS" in str(error):
            return "The reply was cut off at the token limit"
        provider = "Tavily" if "Tavily" in str(error) else "Token Factory"
        return f"{provider} could not complete this check; try again in a minute"
    return redact(str(error))[:300]
