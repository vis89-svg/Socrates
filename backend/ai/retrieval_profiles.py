import json
import os
from datetime import datetime, timezone

_PROFILES_PATH = os.path.join(os.path.dirname(__file__), 'retrieval_profiles.json')

_DEFAULT_PROFILE = 'general'

_INTENT_KEYWORDS = [
    ('investment', [
        'revenue', 'earnings', 'profit', 'funding round', 'ipo', 'stock', 'share price',
        'market cap', '10-k', '10-q', 'sec filing', 'shareholder', 'dividend',
        'financial results', 'annual report', 'quarterly results', 'net income',
        'valuation', 'investor', 'fundraise',
    ]),
    ('medical', [
        'health', 'disease', 'drug', 'treatment', 'symptom', 'clinical trial', 'patient',
        'vaccine', 'fda', 'medical', 'therapy', 'cancer', 'diabetes', 'dosage',
        'side effect', 'nutrition', 'wellness',
    ]),
    ('regulatory', [
        'regulation', 'regulatory', 'compliance', 'law', 'legal', 'policy', 'act 2026',
        'eu ai act', 'legislation', 'enforcement', 'rulemaking', 'sanctions',
    ]),
    ('hardware', [
        'gpu', 'cpu', 'ai chip', 'accelerator', 'chip', 'processor', 'soc',
        'h100', 'h200', 'b100', 'b200', 'b300', 'gb200', 'gb300', 'blackwell', 'hopper',
        'rubin', 'a100', 'v100', 't4', 'dgx', 'grace', 'rtx', 'tensor core',
        'mi300', 'mi325', 'mi350', 'cdna', 'instinct', 'rdna',
        'gaudi', 'habana',
        'tpu', 'trainium', 'inferentia', 'neural engine', 'apple silicon',
        'xeon', 'epyc', 'ryzen', 'core ultra', 'core i', 'snapdragon', 'm4', 'm5', 'm6',
        'memory bandwidth', 'hbm', 'nvlink', 'nvswitch', 'infiniband', 'roce',
        'tflops', 'pflops', 'bf16', 'fp8', 'int8', 'tcase', 'tdp',
        'iphone', 'galaxy', 'pixel', 'oneplus', 'smartphone', 'laptop',
    ]),
    ('technical', [
        'how to', 'tutorial', 'documentation', 'api', 'sdk', 'framework', 'language',
        'library', 'example code', 'implementation', 'programming', 'code',
        'python', 'rust', 'django', 'sqlite', 'asyncio', 'javascript', 'typescript',
        'java', 'go lang', 'golang', 'c++', 'kotlin', 'swift', 'react', 'docker',
        'kubernetes', 'linux', 'database', 'algorithm', 'function', 'class',
        'full text search', 'streaming responses', 'ownership', 'debugging',
    ]),
    ('news', [
        'latest', 'today', 'breaking', 'announcement', 'this month', 'this week',
        'current events', 'update', 'news', 'release 2026', 'just announced',
    ]),
    ('historical', [
        'history', 'historical', 'in 19', 'in 20', 'founded in', 'launched in',
        'apollo', 'eniac', 'moon landing', 'first ever', 'original', 'vintage',
        'era', 'launch details',
    ]),
    ('science', [
        'research', 'experiment', 'study', 'discovery', 'exoplanet', 'fusion',
        'quantum', 'astronomy', 'physics', 'chemistry', 'biology', 'genome',
        'telescope', 'nasa', 'particle', 'milestone', 'breakthrough',
    ]),
    ('company', [
        'company', 'overview', 'ceo', 'founder', 'headquarters', 'employees',
        'leadership', 'about us', 'profile', 'organization', 'division', 'fab',
    ]),
]

_TIEBREAK_ORDER = [
    'investment', 'medical', 'regulatory', 'hardware', 'technical',
    'news', 'historical', 'science', 'company', 'general',
]

_INTENT_ALIASES = [
    ('investment', ['investment', 'investor', 'financial', 'finance', 'stock', 'earnings report', '10-k', '10-q', 'sec', 'filing']),
    ('medical', ['medical', 'health', 'healthcare', 'clinical', 'patient', 'drug', 'pharma']),
    ('regulatory', ['regulatory', 'legal', 'compliance', 'policy', 'law', 'regulation', 'government']),
    ('hardware', ['hardware', 'chip', 'gpu', 'processor', 'semiconductor', 'specs', 'specification', 'phone', 'consumer electronics']),
    ('technical', ['technical', 'programming', 'code', 'developer', 'engineering', 'documentation', 'api', 'tutorial']),
    ('news', ['news', 'current events', 'breaking', 'announcement', 'recent']),
    ('historical', ['historical', 'history', 'past', 'archive']),
    ('science', ['science', 'scientific', 'research', 'physics', 'biology', 'astronomy']),
    ('company', ['company', 'corporate', 'organization', 'business overview']),
]


def matches_domain(url, domain):
    return _domain_in(url, domain)


def _load_profiles():
    try:
        with open(_PROFILES_PATH, encoding='utf-8') as f:
            data = json.load(f)
        profiles = data.get('profiles', {})
    except (FileNotFoundError, json.JSONDecodeError):
        profiles = {}
    return profiles or {_DEFAULT_PROFILE: {}}


def _domain_in(url, domain):
    if not url:
        return False
    host = url.lower().replace('https://', '').replace('http://', '').split('/')[0]
    if host.startswith('www.'):
        host = host[4:]
    return host == domain or host.endswith('.' + domain)


class RetrievalProfile:
    _profiles = None

    @classmethod
    def _all(cls):
        if cls._profiles is None:
            cls._profiles = _load_profiles()
        return cls._profiles

    @classmethod
    def get(cls, profile_id):
        return cls._all().get(profile_id, {})

    @classmethod
    def ids(cls):
        return list(cls._all().keys())

    @classmethod
    def resolve(cls, query, planner_intent=None):
        explicit = cls._match_alias(planner_intent) if planner_intent else None
        if explicit and explicit in cls._all():
            return explicit, cls._all()[explicit]
        matched = cls._match_keywords(query)
        if matched and matched in cls._all():
            return matched, cls._all()[matched]
        return _DEFAULT_PROFILE, cls._all()[_DEFAULT_PROFILE]

    @classmethod
    def _match_alias(cls, intent_text):
        if not intent_text:
            return None
        low = intent_text.lower()
        best = None
        for pid, aliases in _INTENT_ALIASES:
            if any(a in low for a in aliases):
                best = pid
                break
        return best

    @classmethod
    def _match_keywords(cls, query):
        low = query.lower()
        scores = {}
        for pid, keywords in _INTENT_KEYWORDS:
            score = sum(1 for kw in keywords if kw in low)
            if score > 0:
                scores[pid] = score
        if not scores:
            return None
        best = max(scores, key=lambda p: (scores[p], -_TIEBREAK_ORDER.index(p)))
        return best

    @classmethod
    def domain_in_profile(cls, url, profile_id):
        profile = cls.get(profile_id)
        for domain in profile.get('preferred_domains', []) + profile.get('boost_domains', []):
            if _domain_in(url, domain):
                return True
        return False

    @classmethod
    def effective_required(cls, profile_id, extra=None, query=None):
        required = list(cls.get(profile_id).get('required_domains') or [])
        for domain in extra or []:
            resolved = cls._resolve_vendor_domain(domain, query) if query else domain
            if resolved and resolved not in required:
                required.append(resolved)
        return required

    @classmethod
    def _resolve_vendor_domain(cls, domain, query):
        if '{vendor}' not in domain:
            return domain
        from .query_expander import QueryExpander
        vendor = QueryExpander._match_vendor((query or '').lower())
        return domain.format(vendor=vendor) if vendor else None

    @classmethod
    def is_excluded(cls, url, profile_id):
        profile = cls.get(profile_id)
        return any(_domain_in(url, d) for d in profile.get('excluded_domains', []))

    @staticmethod
    def recency_score(published_date, mode='balanced'):
        if mode == 'none':
            return 0.5
        if not published_date:
            return 0.5
        now = datetime.now(timezone.utc)
        days_old = (now - published_date).days
        if days_old <= 7:
            base = 1.0
        elif days_old <= 30:
            base = 0.9
        elif days_old <= 90:
            base = 0.8
        elif days_old <= 180:
            base = 0.6
        elif days_old <= 365:
            base = 0.4
        else:
            base = 0.2
        if mode == 'fresh':
            return min(1.0, base * 1.25)
        return base
