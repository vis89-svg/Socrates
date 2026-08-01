import time
from .base import SearchProvider, SearchResult


class DuckDuckGoSearch(SearchProvider):
    def __init__(self, max_retries=3, retry_delay=1.5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def search(self, query, max_results=5):
        for attempt in range(self.max_retries):
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    raw = list(ddgs.text(query, max_results=max_results))
                    if not raw:
                        if attempt < self.max_retries - 1:
                            time.sleep(self.retry_delay * (attempt + 1))
                            continue
                        return []
                    results = []
                    for r in raw:
                        results.append(SearchResult(
                            title=r.get('title', ''),
                            snippet=r.get('body', ''),
                            url=r.get('href', ''),
                        ))
                    return results
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                continue
        return []
