import re

SEARCH_KEYWORDS = [
    'latest', 'today', 'news', 'price', 'weather', 'stock', 'election',
    'score', 'result', 'current', 'recent', 'now', 'live', 'update',
    'status', 'forecast', '2026', '2025', 'breaking', 'headline',
    'announce', 'launch', 'release', 'report', 'data', 'statistics',
]

TIMELESS_PATTERNS = [
    r'\bexplain\b', r'\bdefine\b', r'\bwhat is\b', r'\bwhat are\b',
    r'\bhow does\b', r'\bhow do\b', r'\bwhy is\b', r'\bwhy does\b',
    r'\bcompare\b', r'\bdifference between\b', r'\btutorial\b',
    r'\bexample\b', r'\bintroduction\b', r'\boverview of\b',
    r'\bconcept\b', r'\btheory\b', r'\bprinciple\b', r'\bmeaning\b',
]


def needs_search(query):
    q = query.lower().strip()

    has_timeless = any(re.search(p, q) for p in TIMELESS_PATTERNS)
    has_timely = any(kw in q for kw in SEARCH_KEYWORDS)

    if has_timeless and not has_timely:
        return False

    if has_timely:
        return True

    if len(q.split()) <= 3:
        return True

    return False
