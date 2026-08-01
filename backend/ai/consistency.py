import re
from datetime import datetime, timezone

from .feature_flags import FeatureFlags


def _parse_date(date_str):
    if not date_str:
        return None
    if re.fullmatch(r'(?:19|20)\d{2}', str(date_str).strip()):
        return datetime(int(str(date_str).strip()), 1, 1, tzinfo=timezone.utc)
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ', '%Y/%m/%d', '%d %b %Y', '%b %d, %Y', '%B %d, %Y', '%B %Y', '%b %Y'):
        try:
            return datetime.strptime(date_str[:19], fmt[:19]).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _find_dates_in_text(text):
    if not text:
        return []
    found = []
    iso = re.findall(r'(?:19|20)\d{2}-\d{2}-\d{2}', text)
    found.extend(iso)
    month_day = re.findall(r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
                           r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|'
                           r'Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}', text, flags=re.IGNORECASE)
    found.extend(month_day)
    year = re.findall(r'\b(?:19|20)\d{2}\b', text)
    found.extend(year)
    return found

class ConsistencyChecker:
    @staticmethod
    def check(verified):
        checks = []
        entries = {f: e for f, e in (verified or {}).items() if e and e.get('value') is not None}

        ConsistencyChecker._check_memory_type(entries, checks)
        ConsistencyChecker._check_future_release(entries, checks)
        ConsistencyChecker._check_stale_latest(entries, checks)
        ConsistencyChecker._check_generation_order(entries, checks)
        ConsistencyChecker._check_price_status(entries, checks)
        ConsistencyChecker._check_availability_release(entries, checks)

        return checks

    @staticmethod
    def _check_memory_type(entries, checks):
        for field in ('memory_type', 'memory'):
            entry = entries.get(field)
            if not entry:
                continue
            value = str(entry['value']).lower()
            has_hbm = 'hbm' in value
            has_gddr = 'gddr' in value
            has_ddr = 'ddr' in value and 'gddr' not in value
            if has_hbm and (has_gddr or has_ddr):
                checks.append({
                    'field': field,
                    'rule': 'memory_type_contradiction',
                    'status': 'fail',
                    'detail': f'Value mixes incompatible memory technologies: {value[:80]}',
                })
            elif has_hbm or has_gddr:
                checks.append({
                    'field': field,
                    'rule': 'memory_type_present',
                    'status': 'pass',
                    'detail': f'Memory technology stated: {value[:60]}',
                })

    @staticmethod
    def _check_future_release(entries, checks):
        entry = entries.get('release_date')
        if not entry:
            return
        dates = _find_dates_in_text(str(entry['value']))
        parsed = [_parse_date(d) for d in dates]
        parsed = [d for d in parsed if d]
        if not parsed:
            return
        newest = max(parsed)
        now = datetime.now(timezone.utc)
        days_future = (newest - now).days
        if days_future > 30:
            checks.append({
                'field': 'release_date',
                'rule': 'future_release',
                'status': 'warn',
                'detail': f'Release date {newest.date()} is {days_future} days in the future; treat as announced/unreleased',
            })
        elif days_future > 0:
            checks.append({
                'field': 'release_date',
                'rule': 'future_release',
                'status': 'pass',
                'detail': f'Release date {newest.date()} is imminent',
            })

    @staticmethod
    def _check_stale_latest(entries, checks):
        latest_claim = False
        for field, entry in entries.items():
            value = str(entry.get('value', '')).lower()
            if any(kw in value for kw in ('latest', 'newest', 'current generation', 'flagship')):
                latest_claim = True
                break
        if not latest_claim:
            return
        all_dates = []
        for field, entry in entries.items():
            for d in entry.get('published_dates') or []:
                parsed = _parse_date(d)
                if parsed:
                    all_dates.append(parsed)
        if not all_dates:
            return
        newest = max(all_dates)
        age_days = (datetime.now(timezone.utc) - newest).days
        if age_days > 730:
            checks.append({
                'field': ', '.join(f for f, e in entries.items() if 'latest' in str(e.get('value', '')).lower()),
                'rule': 'stale_latest_claim',
                'status': 'fail',
                'detail': f'Report claims "latest/current" but newest supporting source is {age_days // 365} years old ({newest.date()})',
            })
        elif age_days > 365:
            checks.append({
                'field': 'status',
                'rule': 'stale_latest_claim',
                'status': 'warn',
                'detail': f'"Latest" claim relies on sources up to {age_days // 30} months old',
            })

    @staticmethod
    def _check_generation_order(entries, checks):
        prev = entries.get('previous_generation')
        cur = entries.get('release_date')
        if not prev or not cur:
            return
        prev_dates = [_parse_date(d) for d in _find_dates_in_text(str(prev['value']))]
        cur_dates = [_parse_date(d) for d in _find_dates_in_text(str(cur['value']))]
        prev_dates = [d for d in prev_dates if d]
        cur_dates = [d for d in cur_dates if d]
        if not prev_dates or not cur_dates:
            return
        if min(prev_dates) >= min(cur_dates):
            checks.append({
                'field': 'previous_generation',
                'rule': 'generation_order',
                'status': 'fail',
                'detail': f'Predecessor released {min(prev_dates).date()} not before current generation {min(cur_dates).date()}',
            })

    @staticmethod
    def _check_price_status(entries, checks):
        price = entries.get('price')
        status = entries.get('status')
        if not price:
            return
        status_text = str(status['value']).lower() if status else ''
        available = any(kw in status_text for kw in ('available', 'shipping', 'current', 'in stock', 'released'))
        unreleased = any(kw in status_text for kw in ('unreleased', 'announced', 'pre-order', 'preorder', 'upcoming', 'coming'))
        if price and (status is None or unreleased):
            checks.append({
                'field': 'price',
                'rule': 'speculative_price',
                'status': 'warn',
                'detail': f'Price extracted ({str(price["value"])[:40]}) but product status is {status_text or "unknown"}; pricing may be speculative',
            })
        elif price and available:
            checks.append({
                'field': 'price',
                'rule': 'speculative_price',
                'status': 'pass',
                'detail': 'Price extracted and product reported available',
            })

    @staticmethod
    def _check_availability_release(entries, checks):
        availability = entries.get('availability')
        release = entries.get('release_date')
        if not availability:
            return
        avail_text = str(availability['value']).lower()
        available_now = any(kw in avail_text for kw in ('available', 'shipping', 'in stock'))
        if not release or not available_now:
            return
        dates = [_parse_date(d) for d in _find_dates_in_text(str(release['value']))]
        dates = [d for d in dates if d]
        if not dates:
            return
        if min(dates) > datetime.now(timezone.utc):
            checks.append({
                'field': 'availability',
                'rule': 'availability_release_contradiction',
                'status': 'fail',
                'detail': f'Reported available now but release date {min(dates).date()} is in the future',
            })

    @staticmethod
    def annotate(verified):
        checks = ConsistencyChecker.check(verified)
        by_field = {}
        for c in checks:
            by_field.setdefault(c['field'], []).append(c)
        for field, field_checks in by_field.items():
            entry = verified.get(field)
            if entry:
                entry['checks'] = field_checks
        return checks
