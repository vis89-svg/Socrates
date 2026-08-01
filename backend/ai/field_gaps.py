from .search_service import search_service
from .page_fetcher import PageFetcher
from .source_weighter import SourceWeighter

MAX_NEW_RESULTS = 12
MAX_PAGE_FETCHES = 8
MAX_GAP_FIELDS = 6

_FIELD_QUERIES = {
    'founded': ['{name} founded year history official website'],
    'headquarters': ['{name} headquarters office address official'],
    'leadership': ['{name} chairman CEO leadership team official'],
    'ceo': ['{name} CEO president official'],
    'employees': ['{name} number of employees total workforce'],
    'revenue': ['{name} revenue net income annual report'],
    'budget': ['{name} annual budget'],
    'description': ['{name} about company profile official'],
    'products': ['{name} product families portfolio list'],
    'technologies': ['{name} core technologies technology stack'],
    'research_domains': ['{name} research areas domains'],
    'major_projects': ['{name} major projects flagship programs'],
    'achievements': ['{name} awards achievements milestones'],
    'locations': ['{name} locations offices global presence'],
    'clients': ['{name} customers clients industries served'],
    'partners': ['{name} partners collaborations joint ventures'],
    'contact': ['{name} contact email phone'],
    'social_links': ['{name} official LinkedIn page'],
}


class FieldGapResearcher:
    @staticmethod
    def underverified_fields(verified):
        underverified = []
        for field, entry in verified.items():
            if field not in _FIELD_QUERIES:
                continue
            if not entry or entry.get('value') is None:
                underverified.append(field)
            elif entry.get('confidence') in ('low', 'none'):
                underverified.append(field)
        return underverified[:MAX_GAP_FIELDS]

    @staticmethod
    def build_queries(company_name, fields):
        queries = []
        for f in fields:
            for tmpl in _FIELD_QUERIES.get(f, []):
                q = tmpl.format(name=company_name)
                if q not in queries:
                    queries.append(q)
        return queries[:12]

    @staticmethod
    def research(company_name, fields, existing_results=None):
        queries = FieldGapResearcher.build_queries(company_name, fields)
        if not queries:
            return []

        existing_urls = {r.get('url', '') for r in (existing_results or [])}
        new_results = []

        for q in queries:
            if len(new_results) >= MAX_NEW_RESULTS:
                break
            serialized, provider = search_service.search(q, max_results=5)
            if not serialized:
                continue
            for r in serialized:
                if len(new_results) >= MAX_NEW_RESULTS:
                    break
                url = r.get('url', '')
                if not url or url in existing_urls:
                    continue
                if SourceWeighter.weight(url) == 0 or not PageFetcher.is_fetchable(url):
                    continue
                existing_urls.add(url)
                r['from_query'] = q
                r['from_gap_search'] = True
                if len(new_results) < MAX_PAGE_FETCHES:
                    page_text = PageFetcher.fetch(url)
                    if page_text:
                        r['page_text'] = page_text
                new_results.append(r)

        return new_results
