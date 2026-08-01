import re
import time
import concurrent.futures
from datetime import datetime, timezone
from django.conf import settings
from .search_service import search_service
from .query_expander import QueryExpander
from .page_fetcher import PageFetcher
from .page_discovery import PageDiscovery
from .source_weighter import SourceWeighter
from .observability import Observability
from .feature_flags import FeatureFlags
from .retrieval_profiles import RetrievalProfile, matches_domain


MAX_PAGE_FETCHES = 10
MAX_PAGE_EXCERPT = getattr(settings, 'MAX_PAGE_EXCERPT', 500)
RECENCY_WINDOW_DAYS = 365


def _parse_date(date_str):
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ', '%Y/%m/%d', '%d %b %Y', '%b %d, %Y'):
        try:
            return datetime.strptime(date_str[:19], fmt[:19]).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _recency_score(published_date, mode='balanced'):
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
    if mode == 'none':
        return 0.5
    return base


_DATE_PATTERNS = [
    (r'(?:published|posted|updated|last modified|released)[:\s]+((?:19|20)\d{2}-\d{2}-\d{2})', '%Y-%m-%d'),
    (r'(?:published|posted|updated|last modified|released)[:\s]+((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+(?:19|20)\d{2})', None),
    (r'\b((?:19|20)\d{2}-\d{2}-\d{2})\b', '%Y-%m-%d'),
    (r'<meta[^>]+(?:property="article:published_time"|name="date"|name="publish_date")[^>]+content="([^"]+)"', None),
]


def _extract_date_from_text(text):
    if not text:
        return None
    for pattern, fmt in _DATE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1).strip()
        if fmt:
            try:
                return datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        parsed = _parse_date(raw)
        if parsed:
            return parsed.strftime('%Y-%m-%d')
    return None


class RetrievalService:
    MAX_COVERAGE_SEARCHES = 4

    def execute(self, query, max_results=5, tracer=None, intent=None, required_sources=None):
        start = time.time()

        profile_id, profile = RetrievalProfile.resolve(query, intent)
        required = RetrievalProfile.effective_required(profile_id, extra=required_sources, query=query)
        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('intent_resolved', {'intent': profile_id, 'planner_intent': intent,
                                                       'required_domains': required})

        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('query_expansion', {'original_query': query, 'expanded_count': 0})

        expanded = QueryExpander.expand(query, profile=profile)
        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('query_expansion', {'original_query': query, 'expanded_queries': expanded})

        seen_urls = set()
        all_results = []
        provider_counts = {}

        for eq in expanded:
            results, provider = search_service.search(eq, max_results=max_results)
            if provider:
                provider_counts[provider] = provider_counts.get(provider, 0) + 1
            if results:
                for r in results:
                    url = r.get('url', '')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        r['from_query'] = eq
                        all_results.append(r)

        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('raw_search', {'results_count': len(all_results), 'providers': dict(provider_counts)})

        raw_count = len(all_results)
        all_results = self._dedupe(all_results)
        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('dedupe', {'before': raw_count, 'after': len(all_results)})
        search_time_ms = int((time.time() - start) * 1000)
        ranked = SourceWeighter.priority_sort(self._rank(all_results, query, profile))[:15]

        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            ranking_data = []
            for i, r in enumerate(ranked):
                url = r.get('url', '')
                pub_date = r.get('published_date', '') or r.get('date', '')
                ranking_data.append({
                    'rank': i + 1,
                    'url': url,
                    'title': r.get('title', '')[:80],
                    'published_date': pub_date,
                    'source_weight': SourceWeighter.weight(url),
                    'tier': SourceWeighter.tier_label(url),
                })
            tracer.log_timed_stage('ranking', {'ranked_count': len(ranked), 'results': ranking_data})

        all_results, coverage = self._ensure_coverage(all_results, required, query, max_results=max_results,
                                                     profile=profile, search_fn=search_service.search)
        ranked = SourceWeighter.priority_sort(self._rank(all_results, query, profile))[:15]

        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('coverage_validation', coverage)
            tracer.log_timed_stage('ranking_after_coverage', {'ranked_count': len(ranked)})

        pages_to_fetch = self._select_pages_to_fetch(ranked, seen_urls)
        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('page_selection', {'selected_urls': pages_to_fetch})

        page_texts = self._fetch_pages_parallel(pages_to_fetch)
        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            fetch_data = [{'url': url, 'text_length': len(text)} for url, text in page_texts]
            tracer.log_timed_stage('page_fetch', {'fetched_count': len(page_texts), 'urls': fetch_data})

        for url, text in page_texts:
            for r in ranked:
                if r.get('url') == url:
                    r['page_text'] = text
                    if not r.get('published_date') and not r.get('date'):
                        fallback = _extract_date_from_text(text[:4000])
                        if fallback:
                            r['published_date'] = fallback
                    break

        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            dated = sum(1 for r in ranked if r.get('published_date') or r.get('date'))
            tracer.log_timed_stage('published_date_fallback', {'results_with_dates': dated, 'total': len(ranked)})

        summary = self._build_summary(ranked, coverage=coverage)

        if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            tracer.log_timed_stage('summary_built', {'summary_length': len(summary)})

        return {
            'results': ranked,
            'provider': max(provider_counts, key=provider_counts.get) if provider_counts else None,
            'count': len(ranked),
            'time_ms': search_time_ms,
            'summary': summary,
            'intent': profile_id,
            'temporal_mode': profile.get('temporal', 'balanced'),
            'coverage': coverage,
        }

    @staticmethod
    def _coverage_report(results, required):
        found = []
        for domain in required:
            if any(matches_domain(r.get('url', ''), domain) for r in results):
                found.append(domain)
        missing = [d for d in required if d not in found]
        return {'required': list(required), 'found': found, 'missing': missing}

    @staticmethod
    def _ensure_coverage(all_results, required, query, max_results=5, profile=None, search_fn=None):
        if not required:
            return all_results, RetrievalService._coverage_report(all_results, required)
        target_count = len(required)
        coverage = RetrievalService._coverage_report(all_results, required)
        if not coverage['missing']:
            return all_results, coverage

        seen_urls = {r.get('url', '') for r in all_results if r.get('url')}
        merged = list(all_results)
        for domain in coverage['missing'][:RetrievalService.MAX_COVERAGE_SEARCHES]:
            site_query = f'site:{domain} {query}'
            try:
                results, _ = (search_fn or search_service.search)(site_query, max_results=max_results)
            except Exception:
                continue
            if results:
                for r in results:
                    url = r.get('url', '')
                    if url and url not in seen_urls and matches_domain(url, domain):
                        seen_urls.add(url)
                        r['from_query'] = site_query
                        merged.append(r)
        if len(merged) > len(all_results):
            merged = RetrievalService._dedupe(merged)
        return merged, RetrievalService._coverage_report(merged, required)

    @staticmethod
    def _canonicalize_url(url):
        if not url:
            return ''
        url = re.sub(r'[?&](?:utm_[a-z0-9_]+|fbclid|gclid|gclsrc|dclid|spm|ref|ref_src|mc_cid|mc_eid|mkt_tok|vero_id|itm_source|itm_medium)=[^&#]*', '', url)
        url = url.split('#')[0]
        url = url.rstrip('/')
        return url.lower()

    @staticmethod
    def _dedupe(results):
        best = {}
        for r in results:
            url = r.get('url', '')
            canon = RetrievalService._canonicalize_url(url)
            title_norm = re.sub(r'[^a-z0-9]+', ' ', r.get('title', '')).lower().strip()
            if canon:
                key = ('url', canon)
            elif title_norm:
                key = ('title', title_norm)
            else:
                continue
            existing = best.get(key)
            if existing is None:
                if canon:
                    r['url'] = canon
                best[key] = r
            else:
                if SourceWeighter.weight(url) > SourceWeighter.weight(existing.get('url', '')):
                    if canon:
                        r['url'] = canon
                    best[key] = r
                elif not existing.get('snippet') and r.get('snippet'):
                    if canon:
                        r['url'] = canon
                    best[key] = r
        return list(best.values())

    def _select_pages_to_fetch(self, ranked, already_seen):
        candidates = []
        for r in ranked:
            url = r.get('url', '')
            if url and PageFetcher.is_fetchable(url) and SourceWeighter.weight(url) > 0:
                candidates.append(r)

        selected = []
        seen_domains = set()

        for r in candidates:
            if len(selected) >= MAX_PAGE_FETCHES:
                break
            url = r.get('url', '')
            domain = re.sub(r'^https?://(www\.)?', '', url).split('/')[0]
            if domain not in seen_domains:
                seen_domains.add(domain)
                selected.append(url)

        selected_set = set(selected)
        for r in candidates:
            if len(selected) >= MAX_PAGE_FETCHES:
                break
            url = r.get('url', '')
            if url not in selected_set:
                selected.append(url)
                selected_set.add(url)

        if candidates:
            top_url = candidates[0].get('url', '')
            base = PageDiscovery.get_base_domain(top_url)
            discovered = PageDiscovery.discover(base)
            for d in discovered:
                if d['url'] not in selected_set:
                    if len(selected) >= MAX_PAGE_FETCHES:
                        break
                    selected.append(d['url'])
                    selected_set.add(d['url'])

        return selected

    def _fetch_pages_parallel(self, urls):
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_map = {executor.submit(PageFetcher.fetch, url): url for url in urls}
            for future in concurrent.futures.as_completed(future_map, timeout=30):
                url = future_map[future]
                try:
                    text = future.result()
                    if text:
                        results.append((url, text))
                except Exception:
                    pass
        return results

    def _rank(self, results, query, profile=None):
        keywords = query.lower().split()
        current_year = datetime.now().year
        year_keywords = {str(current_year), str(current_year - 1), 'latest', 'new', 'announced', 'released', 'unveiled'}
        temporal_mode = (profile or {}).get('temporal', 'balanced')

        vendor = QueryExpander._match_vendor(query.lower())
        boost_domains = []
        preferred_domains = []
        for domain in (profile or {}).get('boost_domains', []):
            boost_domains.append(domain.format(vendor=vendor) if '{vendor}' in domain and vendor else domain)
        for domain in (profile or {}).get('preferred_domains', []):
            if '{vendor}' in domain:
                if vendor:
                    preferred_domains.append(domain.format(vendor=vendor))
            else:
                preferred_domains.append(domain)
        excluded_domains = (profile or {}).get('excluded_domains', [])

        def domain_of(url):
            return re.sub(r'^https?://(www\.)?', '', (url or '')).lower().split('/')[0]

        def in_list(url, domains):
            d = domain_of(url)
            return any(d == x or d.endswith('.' + x) for x in domains)

        scored = []
        for r in results:
            score = 0
            title = r.get('title', '').lower()
            snippet = r.get('snippet', '').lower()

            for kw in keywords:
                if kw in title:
                    score += 3
                if kw in snippet:
                    score += 1

            for yk in year_keywords:
                if yk in title or yk in snippet:
                    score += 2
                    break

            if in_list(r.get('url', ''), excluded_domains):
                score *= 0.05
            if in_list(r.get('url', ''), boost_domains):
                score += 4
            if in_list(r.get('url', ''), preferred_domains):
                score += 2

            pub_date = _parse_date(r.get('published_date', '') or r.get('date', ''))
            recency = _recency_score(pub_date, temporal_mode)
            score = score * (0.7 + 0.3 * recency)

            scored.append((score, r))

        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored]

    @staticmethod
    def _build_summary(results, coverage=None):
        parts = []
        parts.append('Web search results:')
        parts.append('')
        for i, r in enumerate(results[:10], 1):
            title = r.get('title', 'Untitled')
            snippet = r.get('snippet', '')
            url = r.get('url', '')
            parts.append(f'--- Source {i}: {title} ---')
            parts.append(f'URL: {url}')
            if snippet:
                parts.append(f'Content: {snippet[:250]}')
            if r.get('page_text'):
                parts.append('Full page excerpt:')
                parts.append(r['page_text'][:MAX_PAGE_EXCERPT])
            parts.append('')
        if coverage and coverage.get('required'):
            parts.append('Source coverage report:')
            parts.append(f"Required authorities: {', '.join(coverage['required'])}")
            if coverage['found']:
                parts.append(f"Found: {', '.join(coverage['found'])}")
            if coverage['missing']:
                parts.append(f"Searched but no relevant results found: {', '.join(coverage['missing'])}")
            parts.append('')
        return '\n'.join(parts)
