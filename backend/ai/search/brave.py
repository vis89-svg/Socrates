from .base import SearchProvider, SearchResult


class BraveSearch(SearchProvider):
    def __init__(self, api_key):
        self.api_key = api_key

    def search(self, query, max_results=5):
        try:
            import requests
            r = requests.get(
                'https://api.search.brave.com/res/v1/web/search',
                headers={
                    'Accept': 'application/json',
                    'Accept-Encoding': 'gzip',
                    'X-Subscription-Token': self.api_key,
                },
                params={
                    'q': query,
                    'count': max_results,
                },
                timeout=15,
            )
            if r.status_code != 200:
                return []
            data = r.json()
            results = []
            for item in data.get('web', {}).get('results', []):
                results.append(SearchResult(
                    title=item.get('title', ''),
                    snippet=item.get('description', ''),
                    url=item.get('url', ''),
                ))
            return results
        except Exception:
            return []
