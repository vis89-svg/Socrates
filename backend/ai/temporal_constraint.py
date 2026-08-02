import re
from enum import Enum


class TemporalType(Enum):
    TODAY = 'today'
    LAST_7_DAYS = 'last_7_days'
    LAST_30_DAYS = 'last_30_days'
    LAST_YEAR = 'last_year'
    SEASONAL = 'seasonal'
    HISTORICAL = 'historical'
    NO_CONSTRAINT = 'no_constraint'


TEMPORAL_PATTERNS = [
    (r'\btoday\b', TemporalType.TODAY),
    (r'\bnow\b', TemporalType.TODAY),
    (r'\bcurrent\b', TemporalType.TODAY),
    (r'\bthis week\b', TemporalType.LAST_7_DAYS),
    (r'\blast 7 days\b', TemporalType.LAST_7_DAYS),
    (r'\bthis month\b', TemporalType.LAST_30_DAYS),
    (r'\blast 30 days\b', TemporalType.LAST_30_DAYS),
    (r'\bthis year\b', TemporalType.LAST_YEAR),
    (r'\blast year\b', TemporalType.LAST_YEAR),
    (r'\bseasonal\b', TemporalType.SEASONAL),
    (r'\bhistorical\b', TemporalType.HISTORICAL),
    (r'\bin 19\d{2}\b', TemporalType.HISTORICAL),
    (r'\bin 20\d{2}\b', TemporalType.HISTORICAL),
]

TEMPORAL_MODIFIERS = {
    TemporalType.TODAY: ['today', 'now', 'current', 'current weather', 'today forecast'],
    TemporalType.LAST_7_DAYS: ['last 7 days', 'this week', 'this week news', 'recent week'],
    TemporalType.LAST_30_DAYS: ['this month', 'last 30 days', 'recent month'],
    TemporalType.LAST_YEAR: ['this year', 'last year', '2026', '2025'],
    TemporalType.SEASONAL: ['seasonal', 'monsoon', 'rainy season', 'winter'],
    TemporalType.HISTORICAL: ['historical', 'in 19', 'in 20', 'founded', 'launched'],
}


class TemporalConstraintEngine:
    @staticmethod
    def extract(query):
        q = query.lower().strip()
        for pattern, temporal_type in TEMPORAL_PATTERNS:
            if re.search(pattern, q):
                return temporal_type
        return TemporalType.NO_CONSTRAINT

    @staticmethod
    def get_modifiers(temporal_type):
        return TEMPORAL_MODIFIERS.get(temporal_type, [])

    @staticmethod
    def expand_query(query, temporal_type):
        modifiers = TemporalConstraintEngine.get_modifiers(temporal_type)
        if not modifiers:
            return [query]
        expanded = []
        for modifier in modifiers:
            expanded.append(f"{query} {modifier}")
        return expanded

    @staticmethod
    def should_enforce(temporal_type):
        return temporal_type not in (TemporalType.NO_CONSTRAINT, TemporalType.SEASONAL)

    @staticmethod
    def filter_results(results, temporal_type):
        if temporal_type == TemporalType.NO_CONSTRAINT:
            return results
        if temporal_type == TemporalType.TODAY:
            return TemporalConstraintEngine._filter_by_recency(results, max_days=1)
        if temporal_type == TemporalType.LAST_7_DAYS:
            return TemporalConstraintEngine._filter_by_recency(results, max_days=7)
        if temporal_type == TemporalType.LAST_30_DAYS:
            return TemporalConstraintEngine._filter_by_recency(results, max_days=30)
        if temporal_type == TemporalType.LAST_YEAR:
            return TemporalConstraintEngine._filter_by_recency(results, max_days=365)
        return results

    @staticmethod
    def _filter_by_recency(results, max_days):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        filtered = []
        for r in results:
            pub_date = r.get('published_date', '') or r.get('date', '')
            if not pub_date:
                filtered.append(r)
                continue
            try:
                dt = datetime.strptime(pub_date[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc)
                days_old = (now - dt).days
                if days_old <= max_days:
                    filtered.append(r)
            except (ValueError, TypeError):
                filtered.append(r)
        return filtered