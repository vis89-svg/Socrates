from .base import SearchProvider, SearchResult


class TavilySearch(SearchProvider):
    def __init__(self, api_key):
        self.api_key = api_key

    def search(self, query, max_results=5):
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=self.api_key)
            response = client.search(query=query, max_results=max_results)
            results = []
            for r in response.get('results', []):
                results.append(SearchResult(
                    title=r.get('title', ''),
                    snippet=r.get('content', ''),
                    url=r.get('url', ''),
                    published_date=r.get('published_date', ''),
                ))
            return results
        except Exception:
            return []
