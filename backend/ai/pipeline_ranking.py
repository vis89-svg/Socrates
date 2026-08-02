from datetime import datetime, timezone


def rank_weather(results):
    """Rank weather results: current conditions > warnings > forecasts > historical."""
    scored = []
    for r in results:
        score = 0
        title = r.get('title', '').lower()
        snippet = r.get('snippet', '').lower()
        url = r.get('url', '')

        if any(kw in title or kw in snippet for kw in ['current', 'today', 'now', 'real-time']):
            score += 10
        if any(kw in title or kw in snippet for kw in ['warning', 'alert', 'red', 'orange', 'cyclone', 'flood']):
            score += 8
        if any(kw in title or kw in snippet for kw in ['imd', 'mausam', 'meteorological']):
            score += 6
        if any(kw in title or kw in snippet for kw in ['forecast', 'tomorrow', 'next']):
            score += 4
        if any(kw in title or kw in snippet for kw in ['temperature', 'temp', '°c', '°f']):
            score += 5
        if any(kw in title or kw in snippet for kw in ['rain', 'humidity', 'wind']):
            score += 3
        if 'wikipedia' in url:
            score -= 5
        if 'reddit' in url:
            score -= 10

        pub_date = r.get('published_date', '')
        if pub_date:
            try:
                dt = datetime.strptime(pub_date[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc)
                days_old = (datetime.now(timezone.utc) - dt).days
                if days_old <= 1:
                    score += 5
                elif days_old <= 7:
                    score += 3
                elif days_old <= 30:
                    score += 1
            except (ValueError, TypeError):
                pass

        scored.append((score, r))

    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored]


def rank_finance(results):
    """Rank finance results: official sources > recent quarterly data > news."""
    scored = []
    for r in results:
        score = 0
        title = r.get('title', '').lower()
        snippet = r.get('snippet', '').lower()
        url = r.get('url', '')

        if any(kw in title or kw in snippet for kw in ['sec.gov', '10-k', '10-q', 'quarterly', 'annual report']):
            score += 10
        if any(kw in title or kw in snippet for kw in ['earnings', 'revenue', 'profit', 'net income']):
            score += 8
        if any(kw in title or kw in snippet for kw in ['bloomberg', 'reuters', 'sec.gov', 'investor']):
            score += 6
        if any(kw in title or kw in snippet for kw in ['share price', 'market cap', 'valuation']):
            score += 5
        if 'wikipedia' in url:
            score -= 5
        if 'reddit' in url:
            score -= 10

        pub_date = r.get('published_date', '')
        if pub_date:
            try:
                dt = datetime.strptime(pub_date[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc)
                days_old = (datetime.now(timezone.utc) - dt).days
                if days_old <= 7:
                    score += 5
                elif days_old <= 30:
                    score += 3
                elif days_old <= 90:
                    score += 1
            except (ValueError, TypeError):
                pass

        scored.append((score, r))

    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored]


def rank_company(results):
    """Rank company results: official profiles > news > Wikipedia."""
    scored = []
    for r in results:
        score = 0
        title = r.get('title', '').lower()
        snippet = r.get('snippet', '').lower()
        url = r.get('url', '')

        if any(kw in title or kw in snippet for kw in ['about us', 'company profile', 'leadership', 'ceo']):
            score += 8
        if any(kw in title or kw in snippet for kw in ['linkedin', 'crunchbase', 'bloomberg']):
            score += 5
        if 'wikipedia' in url:
            score += 2
        if 'reddit' in url:
            score -= 5

        scored.append((score, r))

    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored]


def rank_research(results):
    """Rank research results: authoritative sources > recent > comprehensive."""
    scored = []
    for r in results:
        score = 0
        title = r.get('title', '').lower()
        snippet = r.get('snippet', '').lower()
        url = r.get('url', '')

        if any(kw in title or kw in snippet for kw in ['study', 'research', 'clinical trial', 'peer-reviewed']):
            score += 8
        if any(kw in title or kw in snippet for kw in ['who.int', 'cdc.gov', 'nih.gov', 'nature.com', 'nejm.org']):
            score += 10
        if 'wikipedia' in url:
            score += 1
        if 'reddit' in url:
            score -= 5

        pub_date = r.get('published_date', '')
        if pub_date:
            try:
                dt = datetime.strptime(pub_date[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc)
                days_old = (datetime.now(timezone.utc) - dt).days
                if days_old <= 365:
                    score += 3
                elif days_old <= 730:
                    score += 1
            except (ValueError, TypeError):
                pass

        scored.append((score, r))

    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored]


PIPELINE_RANKERS = {
    'weather': rank_weather,
    'finance': rank_finance,
    'company': rank_company,
    'research': rank_research,
}


def rank_results(intent, results):
    ranker = PIPELINE_RANKERS.get(intent)
    if ranker:
        return ranker(results)
    return results