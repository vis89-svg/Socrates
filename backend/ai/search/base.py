from abc import ABC, abstractmethod


class SearchResult:
    def __init__(self, title, snippet, url, published_date=''):
        self.title = title
        self.snippet = snippet
        self.url = url
        self.published_date = published_date

    def to_dict(self):
        d = {'title': self.title, 'snippet': self.snippet, 'url': self.url}
        if self.published_date:
            d['published_date'] = self.published_date
        return d


class SearchProvider(ABC):
    @abstractmethod
    def search(self, query, max_results=5):
        pass
