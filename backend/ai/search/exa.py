from .base import SearchProvider, SearchResult


class ExaSearch(SearchProvider):
    def __init__(self, api_key):
        self.api_key = api_key

    def search(self, query, max_results=5):
        try:
            import requests
            r = requests.post(
                'https://api.exa.ai/search',
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'query': query,
                    'numResults': max_results,
                },
                timeout=15,
            )
            if r.status_code != 200:
                return []
            data = r.json()
            results = []
            for item in data.get('results', []):
                results.append(SearchResult(
                    title=item.get('title', ''),
                    snippet=item.get('snippet', item.get('text', '')),
                    url=item.get('url', ''),
                ))
            return results
        except Exception:
            return []
