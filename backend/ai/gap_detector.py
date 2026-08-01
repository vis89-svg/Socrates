import re
from urllib.parse import urlparse


_GAP_SIGNALS = {
    'official_website': [
        lambda url, title, snippet: not re.search(r'(linkedin|facebook|twitter|tracxn|crunchbase|zoominfo)', url.lower())
        and not re.search(r'(news|blog|press)', url.lower())
        and not any(p in url.lower() for p in ['/about', '/team', '/careers', '/contact'])
    ],
    'linkedin': [
        lambda url, title, snippet: 'linkedin.com' in url.lower() and '/company/' in url.lower(),
    ],
    'about_page': [
        lambda url, title, snippet: any(p in url.lower() for p in ['/about', '/about-us', '/about_us', '/company']),
        lambda url, title, snippet: 'about' in title.lower() or 'about us' in title.lower(),
    ],
    'leadership': [
        lambda url, title, snippet: any(p in url.lower() for p in ['/team', '/leadership', '/management', '/board']),
        lambda url, title, snippet: any(kw in title.lower() for kw in ['team', 'leadership', 'founder', 'ceo', 'management']),
    ],
    'careers': [
        lambda url, title, snippet: any(p in url.lower() for p in ['/careers', '/jobs', '/join']),
        lambda url, title, snippet: any(kw in title.lower() for kw in ['careers', 'jobs', 'join us']),
    ],
    'products': [
        lambda url, title, snippet: any(p in url.lower() for p in ['/products', '/services', '/solutions']),
        lambda url, title, snippet: any(kw in title.lower() for kw in ['products', 'services', 'solutions']),
    ],
    'contact': [
        lambda url, title, snippet: any(p in url.lower() for p in ['/contact', '/contact-us']),
        lambda url, title, snippet: 'contact' in title.lower(),
    ],
    'news_press': [
        lambda url, title, snippet: any(p in url.lower() for p in ['/news', '/press', '/blog']),
        lambda url, title, snippet: any(kw in title.lower() for kw in ['news', 'press release', 'blog']),
    ],
}


class GapDetector:
    @staticmethod
    def detect_gaps(results, company_name):
        found_signals = set()
        for r in results:
            url = r.get('url', '') or ''
            title = r.get('title', '') or ''
            snippet = r.get('snippet', '') or ''
            for gap_name, checkers in _GAP_SIGNALS.items():
                for check in checkers:
                    if check(url, title, snippet):
                        found_signals.add(gap_name)
                        break

        all_gaps = set(_GAP_SIGNALS.keys())
        missing = all_gaps - found_signals

        gap_priority = []
        priority_order = ['official_website', 'linkedin', 'about_page', 'products', 'leadership', 'careers', 'contact', 'news_press']
        for g in priority_order:
            if g in missing:
                gap_priority.append(g)

        return gap_priority, list(found_signals)

    @staticmethod
    def gap_to_queries(gaps, company_name):
        if not company_name:
            return []
        queries = []
        gap_query_map = {
            'official_website': [f'{company_name} official website', f'{company_name} .com'],
            'linkedin': [f'{company_name} LinkedIn'],
            'about_page': [f'{company_name} about us company information'],
            'leadership': [f'{company_name} CEO founder leadership team'],
            'careers': [f'{company_name} careers jobs employment'],
            'products': [f'{company_name} products services offerings'],
            'contact': [f'{company_name} contact email phone address'],
            'news_press': [f'{company_name} news 2026 press release'],
        }
        for g in gaps:
            if g in gap_query_map:
                for q in gap_query_map[g]:
                    q_lower = q.lower()
                    if q_lower not in queries:
                        queries.append(q)
        return queries

    @staticmethod
    def extract_company_name_from_results(results):
        for r in results:
            title = r.get('title', '')
            url = r.get('url', '')
            domain = urlparse(url).netloc.lower().removeprefix('www.')
            if domain and '.' in domain and not any(d in domain for d in ['google', 'facebook', 'linkedin', 'twitter']):
                candidate = domain.split('.')[0]
                if len(candidate) > 2:
                    return candidate.capitalize()
        return None
