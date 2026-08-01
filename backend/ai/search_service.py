import concurrent.futures
from django.conf import settings
from .cache_service import cache_service
from .search.duckduckgo import DuckDuckGoSearch
from .search.tavily import TavilySearch
from .search.exa import ExaSearch
from .search.brave import BraveSearch
from .source_weighter import SourceWeighter


class SearchService:
    def __init__(self):
        self._providers = None

    def _build_providers(self):
        if self._providers is not None:
            return self._providers
        providers = []

        tavily_key = getattr(settings, 'TAVILY_API_KEY', '')
        exa_key = getattr(settings, 'EXA_API_KEY', '')
        brave_key = getattr(settings, 'BRAVE_API_KEY', '')

        if tavily_key:
            providers.append(('tavily', TavilySearch(tavily_key)))
        if exa_key:
            providers.append(('exa', ExaSearch(exa_key)))
        if brave_key:
            providers.append(('brave', BraveSearch(brave_key)))

        self._providers = providers
        return providers

    def search(self, query, max_results=5):
        if not query or not query.strip():
            return [], None

        cached = cache_service.get('search', query)
        if cached is not None:
            return cached, 'cache'

        providers = self._build_providers()
        all_serialized = []
        seen_urls = set()
        used_provider = None

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_map = {
                executor.submit(provider.search, query, max_results=max_results): name
                for name, provider in providers
            }
            for future in concurrent.futures.as_completed(future_map, timeout=20):
                name = future_map[future]
                try:
                    results = future.result()
                    if results:
                        used_provider = name
                        serialized = [r.to_dict() for r in results]
                        for s in serialized:
                            url = s.get('url', '')
                            if url and url not in seen_urls:
                                seen_urls.add(url)
                                all_serialized.append(s)
                except Exception:
                    continue

        if not all_serialized:
            try:
                ddg = DuckDuckGoSearch()
                results = ddg.search(query, max_results=max_results)
                if results:
                    used_provider = 'duckduckgo'
                    all_serialized = [r.to_dict() for r in results]
            except Exception:
                pass

        if all_serialized:
            cache_service.set('search', query, all_serialized)
            return all_serialized, used_provider

        cache_service.set_empty('search', query)
        return [], None


search_service = SearchService()
