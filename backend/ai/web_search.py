from django.conf import settings
from .intent_check import needs_search
from .search.cache import get as cache_get, set as cache_set, set_empty as cache_set_empty
from .search.duckduckgo import DuckDuckGoSearch

_SEARCH_PROVIDER = None


def _get_provider():
    global _SEARCH_PROVIDER
    if _SEARCH_PROVIDER is not None:
        return _SEARCH_PROVIDER

    provider_name = getattr(settings, 'SEARCH_PROVIDER', 'duckduckgo')

    if provider_name == 'tavily':
        from .search.tavily import TavilySearch
        api_key = getattr(settings, 'TAVILY_API_KEY', '')
        _SEARCH_PROVIDER = TavilySearch(api_key=api_key)
    else:
        _SEARCH_PROVIDER = DuckDuckGoSearch()

    return _SEARCH_PROVIDER


def search_web(query, max_results=5):
    if not query or not query.strip():
        return []

    if not needs_search(query):
        return []

    cached = cache_get(query)
    if cached is not None:
        return cached

    provider = _get_provider()
    results = provider.search(query, max_results=max_results)

    if results:
        cache_set(query, [r.to_dict() for r in results])
    else:
        cache_set_empty(query)

    return [r.to_dict() for r in results]
