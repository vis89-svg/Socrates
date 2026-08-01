import re


_TIMELY_KEYWORDS = [
    'latest', 'today', 'news', 'price', 'weather', 'stock', 'election',
    'score', 'result', 'current', 'recent', 'now', 'live', 'update',
    'status', 'forecast', '2026', '2025', 'breaking', 'headline',
    'announce', 'launch', 'release', 'report', 'data', 'statistics',
]

_PATTERNS = {
    'needs_code': [
        r'\bcode\b', r'\bfunction\b', r'\bdebug\b', r'\bimplementation\b',
        r'\brefactor\b', r'\bwrite a\b.*\b(function|class|program|script)\b',
        r'\bpython\b', r'\bjavascript\b', r'\btypescript\b', r'\bhtml\b',
        r'\bcss\b', r'\breact\b', r'\bapi\b', r'\bsql\b',
        r'\balgorithm\b', r'\bbug\b', r'\berror\b', r'\bfix\b',
        r'\bdeploy\b', r'\bgit\b', r'\brepo\b',
    ],
    'needs_reasoning': [
        r'\bcompare and contrast\b', r'\banalyze\b', r'\bevaluate\b',
        r'\bwhy is\b', r'\bwhat if\b', r'\bimplications\b',
        r'\bpros and cons\b', r'\badvantages and disadvantages\b',
        r'\bcritical\b', r'\bthink step by step\b', r'\bexplain why\b',
        r'\breasoning\b', r'\bdeduce\b', r'\binfer\b',
    ],
    'needs_search': [
        r'\bnews\b', r'\bupdate on\b', r'\bwhat happened\b',
        r'\blatest\b', r'\bcurrent\b', r'\bhappening now\b',
        r'\btoday\b', r'\bthis week\b', r'\bthis month\b',
        r'\bsearch for\b', r'\bfind information about\b',
        r'\blook up\b', r'\bprice of\b', r'\bweather\b', r'\bstock\b',
        r'\bscore\b', r'\bresult\b',
        r'\bresearch\b', r'\bwho is\b', r'\bwhat is\b.*\bcompany\b',
        r'\btell me about\b', r'\binformation about\b',
        r'\bdetails about\b', r'\boverview of\b',
        r'\bcompany profile\b', r'\bheadquarters\b', r'\bsocial media\b',
    ],
    'needs_documents': [
        r'\bsummarize\b', r'\breview this\b', r'\banalyze this\b',
        r'\bextract\b', r'\bwhat does this (document|file|pdf|text)\b',
        r'\bexplain this\b', r'\bread this\b',
    ],
    'needs_math': [
        r'\bcalculate\b', r'\bcompute\b', r'\bsolve\b', r'\bequation\b',
        r'\bformula\b', r'\bderivative\b', r'\bintegral\b', r'\bmatrix\b',
        r'\bprobability\b', r'\bstatistics\b', r'\bregression\b',
        r'\bmath\b', r'\balgebra\b', r'\bgeometry\b', r'\bcalculus\b',
        r'\bplus\b', r'\bminus\b', r'\btimes\b', r'\bdivided by\b',
    ],
    'needs_vision': [
        r'\bimage\b', r'\bpicture\b', r'\bphoto\b', r'\bwhat.*see\b',
        r'\bdescribe.*image\b', r'\bdiagram\b', r'\bchart\b',
        r'\bgraph\b', r'\bscreenshot\b',
    ],
}


class TaskAnalyzer:
    @staticmethod
    def analyze(query):
        q = query.lower().strip()
        capabilities = set()

        for cap, patterns in _PATTERNS.items():
            for p in patterns:
                if re.search(p, q):
                    capabilities.add(cap)
                    break

        has_timely = any(kw in q for kw in _TIMELY_KEYWORDS)
        if has_timely:
            capabilities.add('needs_search')

        if not capabilities:
            capabilities.add('general')

        return capabilities
