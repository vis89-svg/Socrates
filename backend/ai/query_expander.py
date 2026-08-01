import re
from datetime import datetime

_CURRENT_YEAR = datetime.now().year
_NEXT_YEAR = _CURRENT_YEAR + 1

_RESEARCH_TYPES = [
    ('company', [
        'company', 'technologies', 'tech', 'corp', 'inc', 'ltd', 'pvt',
        'headquarters', 'ceo', 'founder', 'products', 'social media',
        'linkedin', 'employees', 'revenue', 'overview', 'profile',
    ]),
    ('news', [
        'news', 'latest', 'today', 'breaking', 'happening', 'update',
        'current events', 'this week', 'this month',
    ]),
    ('comparison', [
        ' vs ', 'compare', 'versus', 'difference between',
    ]),
    ('technical', [
        'how to', 'tutorial', 'documentation', 'api', 'sdk', 'framework',
        'language', 'library', 'example code', 'implementation',
    ]),
    ('ai_hardware', [
        'gpu', 'ai chip', 'accelerator', 'h100', 'h200', 'b100', 'b200',
        'b300', 'gb200', 'gb300', 'blackwell', 'hopper', 'rubin', 'a100',
        'v100', 't4', 'dgx', 'grace', 'rtx', 'tensor core',
        'mi300', 'mi325', 'mi350', 'cdna', 'instinct', 'rdna',
        'gaudi', 'gaudi2', 'gaudi3', 'habana',
        'tpu', 'trainium', 'inferentia', 'neural engine', 'apple silicon',
        'xeon', 'epyc', 'ryzen', 'core ultra', 'core i', 'snapdragon',
        'maia', 'cobalt', 'chip', 'm4', 'm5', 'neural engine', 'apple silicon',
        'memory bandwidth', 'hbm', 'hbm2e', 'hbm3', 'hbm3e',
        'nvlink', 'nvswitch', 'infiniband', 'roce',
        'tflops', 'pflops', 'bf16', 'fp8', 'int8',
        'llm training', 'inference', 'fine-tuning',
    ]),
]

_COMPANY_TEMPLATES = [
    '{name} official website',
    '{name} LinkedIn',
    '{name} about us',
    '{name} leadership team',
    '{name} careers jobs',
    '{name} products services',
    '{name} news {year}',
    '{name} contact',
]

_NEWS_TEMPLATES = [
    '{query} {year}',
    '{query} latest update',
    '{query} today',
    '{query} {year} announcement',
]

_COMPARISON_TEMPLATES = [
    '{a} vs {b} comparison {year}',
    '{a} {b} differences {year}',
    '{a} vs {b} {year}',
    '{a} versus {b} benchmark {year}',
]

_TECHNICAL_TEMPLATES = [
    '{query} tutorial',
    '{query} documentation',
    '{query} examples',
    '{query} best practices',
]

_AI_HARDWARE_TEMPLATES = [
    '{query} {year} specifications',
    '{query} {year} release date',
    '{query} {year} benchmark',
    '{query} {year} price',
    '{query} {next_year} roadmap',
    '{query} architecture details {year}',
    '{query} performance {year}',
    '{query} vs competitors {year}',
    'latest {query} {year}',
    '{query} announcement {year}',
]

_GENERAL_TEMPLATES = [
    '{query} {year}',
    '{query} latest',
]

_VENDOR_SITE_MAP = [
    ('nvidia', 'nvidia.com'),
    ('amd', 'amd.com'),
    ('intel', 'intel.com'),
    ('apple', 'apple.com'),
    ('google', 'cloud.google.com'),
    ('microsoft', 'microsoft.com'),
    ('qualcomm', 'qualcomm.com'),
    ('arm', 'arm.com'),
    ('aws', 'aws.amazon.com'),
    ('tsmc', 'tsmc.com'),
    ('samsung', 'samsung.com'),
    ('ibm', 'ibm.com'),
]

_PRODUCT_VENDOR_MAP = {
    'nvidia': ('blackwell', 'hopper', 'amper', 'a100', 'a200', 'v100', 't4', 'h100',
               'h200', 'b100', 'b200', 'b300', 'rtx', 'nvlink', 'cuda', 'dlss',
               'gb200', 'gb300', 'dgx', 'jetson', 'grace', 'tensor core', 'tensor cores'),
    'amd': ('mi300', 'mi325', 'mi350', 'mi355', 'mi400', 'cdna', 'instinct', 'rdna',
            'zen', 'epyc', 'ryzen', 'radeon', 'versa'),
    'intel': ('gaudi', 'habana', 'xeon', 'arc', 'battlemage', 'lunar lake', 'arrow lake',
              'granite rapids', 'panther lake', 'alder lake', 'raptor lake', 'core ultra',
              'core i'),
    'google': ('tpu', 'pali', 'gemma', 'jax', 'v6e', 'v7', 'v5e'),
    'aws': ('trainium', 'inferentia', 'graviton', 'nitro'),
    'qualcomm': ('snapdragon', 'x elite', 'orion', 'ocu'),
    'apple': ('neural engine', 'm4', 'm5', 'm6', 'apple silicon'),
    'microsoft': ('maia', 'cobalt', 'softai'),
}

_OFFICIAL_TEMPLATES = [
    '{query} official specifications {year}',
    '{query} datasheet {year}',
    '{query} press release {year}',
    '{query} product page {year}',
]


class QueryExpander:
    @staticmethod
    def expand(query, profile=None):
        q = query.lower().strip()
        if not q:
            return [query]

        research_type = QueryExpander._detect_type(q)
        queries = [query]

        if research_type == 'company':
            name = QueryExpander._extract_company_name(q)
            if name:
                for tmpl in _COMPANY_TEMPLATES:
                    expanded = tmpl.format(name=name, year=_CURRENT_YEAR)
                    if expanded.lower() not in queries:
                        queries.append(expanded)

        elif research_type == 'news':
            for tmpl in _NEWS_TEMPLATES:
                expanded = tmpl.format(query=q, year=_CURRENT_YEAR)
                if expanded.lower() != q:
                    queries.append(expanded)

        elif research_type == 'comparison':
            parts = re.split(r'\b(?:vs\.?|versus|compare)\b', q, flags=re.IGNORECASE)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) >= 2:
                a, b = parts[0], parts[-1]
                for tmpl in _COMPARISON_TEMPLATES:
                    expanded = tmpl.format(a=a, b=b, year=_CURRENT_YEAR)
                    if expanded.lower() not in queries:
                        queries.append(expanded)
            QueryExpander._append_official_queries(q, queries)

        elif research_type in ('ai_hardware', 'technical'):
            QueryExpander._append_official_queries(q, queries)

            tmpls = _AI_HARDWARE_TEMPLATES if research_type == 'ai_hardware' else _TECHNICAL_TEMPLATES
            for tmpl in tmpls:
                expanded = tmpl.format(query=q, year=_CURRENT_YEAR, next_year=_NEXT_YEAR)
                if expanded.lower() != q:
                    queries.append(expanded)

        else:
            for tmpl in _GENERAL_TEMPLATES:
                expanded = tmpl.format(query=q, year=_CURRENT_YEAR)
                if expanded.lower() != q:
                    queries.append(expanded)

        QueryExpander._append_profile_queries(q, queries, profile)

        return queries[:15]

    @staticmethod
    def _match_vendor(q):
        for vendor, domain in _VENDOR_SITE_MAP:
            if vendor in q or any(p in q for p in _PRODUCT_VENDOR_MAP.get(vendor, ())):
                return vendor
        return None

    @staticmethod
    def _resolve_domain(domain, q):
        if '{vendor}' not in domain:
            return domain
        vendor = QueryExpander._match_vendor(q)
        if not vendor:
            return None
        return domain.format(vendor=vendor)

    @staticmethod
    def _append_profile_queries(q, queries, profile):
        if not profile:
            return
        resolved = [QueryExpander._resolve_domain(d, q) for d in (profile.get('preferred_domains') or [])]
        preferred = [d for d in resolved if d]
        required = [d for d in (profile.get('required_domains') or []) if d]
        keywords = profile.get('keywords') or []
        existing = {x.lower() for x in queries}

        def add(query_text):
            if query_text.lower() not in existing:
                queries.append(query_text)
                existing.add(query_text.lower())

        if profile.get('restrictive'):
            queries[:] = [query for query in queries[:1]]
            existing = {x.lower() for x in queries}
            for domain in required + preferred:
                add(f'site:{domain} {q} {_CURRENT_YEAR}')
            for kw in keywords:
                add(f'{q} {kw} {_CURRENT_YEAR}')
            for kw in keywords[:2]:
                for domain in (required + preferred)[:3]:
                    add(f'site:{domain} {q} {kw} {_CURRENT_YEAR}')
            return

        profile_sites = []
        for domain in required + preferred:
            text = f'site:{domain} {q} {_CURRENT_YEAR}'
            if text.lower() not in existing:
                profile_sites.append(text)
        queries[1:1] = profile_sites
        existing.update(t.lower() for t in profile_sites)
        for kw in keywords:
            add(f'{q} {kw} {_CURRENT_YEAR}')

    @staticmethod
    def _append_official_queries(q, queries):
        matched = [f'site:{domain}' for vendor, domain in _VENDOR_SITE_MAP
                   if vendor in q or any(p in q for p in _PRODUCT_VENDOR_MAP.get(vendor, ()))][:4]
        for site_op in matched:
            queries.append(f'{site_op} {q} {_CURRENT_YEAR}')
        for tmpl in _OFFICIAL_TEMPLATES:
            queries.append(tmpl.format(query=q, year=_CURRENT_YEAR))

    @staticmethod
    def _detect_type(q):
        scores = {}
        for rtype, keywords in _RESEARCH_TYPES:
            score = sum(1 for kw in keywords if kw in q)
            if score > 0:
                scores[rtype] = score
        if not scores:
            return 'general'
        return max(scores, key=scores.get)

    @staticmethod
    def _extract_company_name(q):
        noise = {'tell', 'me', 'about', 'search', 'for', 'find', 'information',
                 'details', 'the', 'a', 'an', 'what', 'is', 'are', 'give',
                 'provide', 'show', 'look', 'up', 'research', 'company',
                 'technologies', 'tech', 'private', 'limited', 'corporation',
                 'ltd', 'pvt', 'and', 'their', 'its', 'some', 'any'}
        words = q.split()
        name_words = []
        for w in words:
            cleaned = w.strip('.,!?;:\'"()[]{}')
            if cleaned and cleaned not in noise:
                name_words.append(cleaned)
        if not name_words:
            return None
        name = ' '.join(name_words[:5]).replace('  ', ' ')
        while any(name.lower().endswith(n) for n in [' to', ' for', ' of', ' in', ' on', ' at', ' by']):
            parts_rs = name.rsplit(None, 1)
            if len(parts_rs) < 2:
                break
            name = parts_rs[0]
        return name.strip()
