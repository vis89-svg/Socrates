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
    WEATHER = 'weather'
    FINANCE = 'finance'
    MAPS = 'maps'
    COMPANY = 'company'

    SEARCH_REQUIRED = {CURRENT_EVENTS, WEB_SEARCH, WEATHER, FINANCE}

    WEATHER_INTENTS = {WEATHER}
    FAST_INTENTS = {WEATHER, FINANCE, MAPS, COMPANY}

    @classmethod
    def needs_search(cls, intent):
        return intent in cls.SEARCH_REQUIRED

    @classmethod
    def is_fast_path(cls, intent):
        return intent in cls.FAST_INTENTS

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
        r'\bprice of\b', r'\bstock\b',
    ]),
    (Intent.WEATHER, [
        r'\bweather\b', r'\btemperature\b', r'\bforecast\b',
        r'\brain\b', r'\bhumidity\b', r'\bwinds?\b',
        r'\bIMD\b', r'\bmeteorological\b', r'\bmonsoon\b',
        r'\balert\b.*\b(rain|flood|storm|cyclone)\b',
        r'\bred alert\b', r'\borange alert\b', r'\bweather warning\b',
        r'\bhow (is|are|was|will be) the weather\b',
        r'\bwhat.*(weather|temperature|rain|forecast)\b',
        r'\bweather in\b', r'\bweather at\b', r'\bweather for\b',
    ]),
    (Intent.FINANCE, [
        r'\bprice of\b', r'\bstock\b', r'\bshare\b', r'\bmarket cap\b',
        r'\brevenue\b', r'\bearnings\b', r'\bfinancial\b',
        r'\b10-K\b', r'\b10-Q\b', r'\bsec filing\b',
    ]),
    (Intent.MAPS, [
        r'\bmap\b', r'\bdirections\b', r'\blocation\b',
        r'\bdistance between\b', r'\bnearest\b', r'\bcoordinates\b',
    ]),
    (Intent.COMPANY, [
        r'\bcompany\b.*\b(profile|overview|about)\b',
        r'\bleadership\b', r'\bCEO\b', r'\bfounder\b',
        r'\bheadquarters\b', r'\bemployees\b',
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
            Intent.WEATHER: 'Weather lookup',
            Intent.FINANCE: 'Financial data lookup',
            Intent.MAPS: 'Maps and location lookup',
            Intent.COMPANY: 'Company profile lookup',
        }
        return descriptions.get(intent, 'General conversation')
