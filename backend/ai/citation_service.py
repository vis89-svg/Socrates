import re


class CitationService:
    @staticmethod
    def domain_of(url):
        match = re.match(r'https?://(?:www\.)?([^/]+)', url or '')
        return match.group(1) if match else ''

    @staticmethod
    def extract(response_text, search_results):
        if not search_results:
            return []

        from .source_weighter import SourceWeighter

        url_by_index = {}
        for i, r in enumerate(search_results, 1):
            url = r.get('url', '')
            title = r.get('title', '')
            if url:
                url_by_index[str(i)] = {
                    'title': title,
                    'url': url,
                    'domain': CitationService.domain_of(url),
                    'authority': SourceWeighter.tier_label(url),
                }

        used_indices = set()
        for match in re.finditer(r'\[Source\s+(\d+)\]', response_text, re.IGNORECASE):
            idx = match.group(1)
            if idx in url_by_index:
                used_indices.add(idx)

        for match in re.finditer(r'\[(\d+)\]', response_text):
            idx = match.group(1)
            if idx in url_by_index:
                used_indices.add(idx)

        citations = []
        seen_urls = set()
        for idx in sorted(used_indices, key=int):
            entry = url_by_index[idx]
            if entry['url'] not in seen_urls:
                citations.append({
                    'index': int(idx),
                    'title': entry['title'],
                    'url': entry['url'],
                    'domain': entry['domain'],
                    'authority': entry['authority'],
                })
                seen_urls.add(entry['url'])

        return citations

    @staticmethod
    def format_citations(citations):
        if not citations:
            return ''
        labels = {
            'high_authority': 'official/government',
            'medium_authority': 'high-authority',
            'general': 'general',
            'blocked': 'blocked',
        }
        parts = ['\n\n**Sources:**']
        for c in citations:
            tier = labels.get(c.get('authority'), '')
            suffix = f' ({tier})' if tier else ''
            parts.append(f'\n[{c["index"]}] {c["title"]} — {c["url"]}{suffix}')
        return ''.join(parts)
