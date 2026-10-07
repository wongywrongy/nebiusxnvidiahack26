"""Live providers: Token Factory (Nemotron) and Tavily. Pipeline code reaches them through
llm.router and web.WebClient, which answer from fixtures in mock mode."""


class ProviderError(RuntimeError):
    pass


class AuthError(ProviderError):
    """401/403: the key is missing, wrong or not allowed. Never retried or worked around."""


class RateLimited(ProviderError):
    """429 (or Tavily's 432/433 plan limits) after backoff. Never worked around."""
