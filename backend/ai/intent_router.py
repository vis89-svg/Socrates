import re


class Intent:
    GENERAL = 'general'
    CODING = 'coding'
    MATH = 'math'
    REASONING = 'reasoning'
    CURRENT_EVENTS = 'current_events'
    WEB_SEARCH = 'web_search'
    DOCUMENT_ANALYSIS = 'document_analysis'
    IMAGE_ANALYSIS = 'image_analysis'
    CREATIVE = 'creative'

    SEARCH_REQUIRED = {CURRENT_EVENTS, WEB_SEARCH}

    @classmethod
    def needs_search(cls, intent):
        return intent in cls.SEARCH_REQUIRED

    @classmethod
    def model_key(cls, intent):
        mapping = {
            cls.CODING: 'coding',
            cls.MATH: 'reasoning',
            cls.REASONING: 'reasoning',
            cls.CREATIVE: 'creative',
        }
        return mapping.get(intent, 'default')


_TIMELY_KEYWORDS = [
    'latest', 'today', 'news', 'price', 'weather', 'stock', 'election',
    'score', 'result', 'current', 'recent', 'now', 'live', 'update',
    'status', 'forecast', '2026', '2025', 'breaking', 'headline',
    'announce', 'launch', 'release', 'report', 'data', 'statistics',
]

_PATTERNS = [
    (Intent.CODING, [
        r'\bcode\b', r'\bfunction\b', r'\bdebug\b', r'\bimplementation\b',
        r'\brefactor\b', r'\bwrite a .* (function|class|program|script)\b',
        r'\bpython\b', r'\bjavascript\b', r'\btypescript\b', r'\bhtml\b',
        r'\bcss\b', r'\breact\b', r'\bapi\b', r'\brest\b', r'\bsql\b',
        r'\balgorithm\b', r'\bbug\b', r'\berror\b', r'\bfix\b',
    ]),
    (Intent.MATH, [
        r'\bcalculate\b', r'\bcompute\b', r'\bsolve\b', r'\bequation\b',
        r'\bformula\b', r'\bderivative\b', r'\bintegral\b', r'\bmatrix\b',
        r'\bprobability\b', r'\bstatistics\b', r'\bregression\b',
        r'\bmath\b', r'\balgebra\b', r'\bgeometry\b', r'\bcalculus\b',
    ]),
    (Intent.REASONING, [
        r'\bcompare and contrast\b', r'\banalyze\b', r'\bevaluate\b',
        r'\bwhy is\b', r'\bwhat if\b', r'\bimplications\b',
        r'\bpros and cons\b', r'\badvantages and disadvantages\b',
        r'\bcritical\b', r'\bthink step by step\b',
    ]),
    (Intent.CURRENT_EVENTS, [
        r'\bnews\b', r'\bupdate on\b', r'\bwhat happened\b',
        r'\blatest\b', r'\bcurrent\b.*\bevent\b', r'\bhappening now\b',
        r'\btoday\b', r'\bthis week\b', r'\bthis month\b', r'\b202[56]\b',
    ]),
    (Intent.WEB_SEARCH, [
        r'\bsearch for\b', r'\bfind information about\b',
        r'\blook up\b', r'\bwhat is the (latest|current|recent)\b',
        r'\btell me about\b.*\b(current|recent|today|now)\b',
        r'\bprice of\b', r'\bweather\b', r'\bstock\b',
    ]),
    (Intent.DOCUMENT_ANALYSIS, [
        r'\bsummarize\b', r'\breview this\b', r'\banalyze this\b',
        r'\bextract\b', r'\bwhat does this (document|file|pdf|text)\b',
        r'\bexplain this\b',
    ]),
    (Intent.IMAGE_ANALYSIS, [
        r'\bimage\b', r'\bpicture\b', r'\bphoto\b', r'\bwhat.*see\b',
        r'\bdescribe.*image\b', r'\bdiagram\b', r'\bchart\b',
    ]),
]


class IntentRouter:
    @staticmethod
    def detect(query):
        q = query.lower().strip()

        for intent, patterns in _PATTERNS:
            for p in patterns:
                if re.search(p, q):
                    return intent

        has_timely = any(kw in q for kw in _TIMELY_KEYWORDS)
        if has_timely:
            return Intent.CURRENT_EVENTS

        return Intent.GENERAL

    @staticmethod
    def describe(intent):
        descriptions = {
            Intent.GENERAL: 'General conversation',
            Intent.CODING: 'Coding and programming',
            Intent.MATH: 'Mathematics and calculation',
            Intent.REASONING: 'Logical reasoning and analysis',
            Intent.CURRENT_EVENTS: 'Current events and timely information',
            Intent.WEB_SEARCH: 'Web search request',
            Intent.DOCUMENT_ANALYSIS: 'Document analysis',
            Intent.IMAGE_ANALYSIS: 'Image analysis',
        }
        return descriptions.get(intent, 'General conversation')
