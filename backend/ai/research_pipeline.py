import logging
import time

from .extractor import Extractor
from .verifier import FactVerifier
from .source_weighter import SourceWeighter
from .model_router import ModelRouter
from .field_gaps import FieldGapResearcher

MAX_SUMMARY_RESULTS = 12
MAX_PAGE_EXCERPT = 800


def _extract_generate(prompt, max_tokens=None):
    last_error = None
    for attempt in range(2):
        try:
            yield from ModelRouter.generate_stream(prompt, model_key='extract', max_tokens=max_tokens,
                                                   allow_fallback=True)
            return
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                logging.getLogger('ai.pipeline').warning(
                    'extract attempt 1 failed (%s), retrying once', exc.__class__.__name__)
                time.sleep(3)
    raise last_error


class ResearchPipeline:
    @staticmethod
    def run(search_result, query, tracer=None):
        search_summary = search_result.get('summary', '')
        all_results = search_result.get('results', [])

        if not search_summary:
            return None, None, []

        weighted = SourceWeighter.priority_sort(all_results)
        search_result['results'] = weighted
        search_result['count'] = len(weighted)
        weighted_summary = ResearchPipeline._rebuild_summary(search_result, weighted)
        search_result['summary'] = weighted_summary

        schema = Extractor.select_schema(query)
        try:
            extracted = Extractor.extract(weighted_summary, _extract_generate, tracer=tracer, schema=schema)
        except Exception:
            logging.getLogger('ai.pipeline').exception('extraction failed for query: %s', query[:80])
            return None, None, weighted
        if not extracted:
            return None, None, weighted
        if tracer is not None:
            tracer.log_timed_stage('extraction_complete', {
                'schema': schema,
                'fields_found': sum(1 for v in extracted.values() if v and v.get('value') is not None),
            })

        try:
            verified = FactVerifier.verify(extracted, weighted, tracer=tracer, query=query)
        except Exception:
            logging.getLogger('ai.pipeline').exception('verification failed for query: %s', query[:80])
            return None, None, weighted
        if tracer is not None:
            tracer.log_timed_stage('verification_complete', {
                'high': sum(1 for v in verified.values() if v.get('confidence') == 'high'),
            })

        company_name = ResearchPipeline._company_name(verified, query)
        underverified = FieldGapResearcher.underverified_fields(verified)
        if schema == 'company' and company_name and underverified:
            new_results = FieldGapResearcher.research(company_name, underverified, weighted)
            if new_results:
                merged = SourceWeighter.priority_sort(ResearchPipeline._dedupe(weighted + new_results))

                new_info = dict(search_result)
                new_info['results'] = new_results
                new_summary = ResearchPipeline._rebuild_summary(new_info, new_results)

                try:
                    new_extracted = Extractor.extract_missing(new_summary, underverified, _extract_generate, tracer=tracer)
                except Exception:
                    logging.getLogger('ai.pipeline').exception('gap-fill extraction failed for query: %s', query[:80])
                    new_extracted = None
                if new_extracted:
                    if tracer is not None:
                        tracer.log_timed_stage('gap_fill_complete', {
                            'fields_filled': sum(1 for v in new_extracted.values() if v and v.get('value') is not None),
                        })
                    merged_extracted = {**extracted}
                    for f, v in new_extracted.items():
                        if v and v.get('value') is not None:
                            merged_extracted[f] = v
                    verified = FactVerifier.verify(merged_extracted, merged, tracer=tracer, query=query)
                    weighted = merged
                    search_result['results'] = merged
                    search_result['count'] = len(merged)
                    search_result['summary'] = ResearchPipeline._rebuild_summary(search_result, merged)

        url_to_index = {
            r.get('url', ''): i + 1
            for i, r in enumerate(weighted[:MAX_SUMMARY_RESULTS])
            if r.get('url')
        }
        dataset_text = FactVerifier.build_dataset(verified, url_to_index)

        return dataset_text, verified, weighted

    @staticmethod
    def _company_name(verified, query):
        entry = verified.get('company_name')
        if entry and entry.get('value'):
            return str(entry['value'])
        from .query_expander import QueryExpander
        return QueryExpander._extract_company_name(query)

    @staticmethod
    def _dedupe(results):
        seen = set()
        deduped = []
        for r in results:
            url = r.get('url', '')
            if url and url not in seen:
                seen.add(url)
                deduped.append(r)
        return deduped

    @staticmethod
    def _rebuild_summary(search_result, weighted_results):
        parts = []
        parts.append('Web search results:')
        parts.append('')
        for i, r in enumerate(weighted_results[:MAX_SUMMARY_RESULTS], 1):
            title = r.get('title', 'Untitled')
            snippet = r.get('snippet', '')
            url = r.get('url', '')
            parts.append(f'--- Result {i}: {title} ---')
            parts.append(f'URL: {url}')
            if snippet:
                parts.append(f'Snippet: {snippet[:200]}')
            if r.get('page_text'):
                parts.append('Page content:')
                parts.append(r['page_text'][:MAX_PAGE_EXCERPT])
            parts.append('')
        return '\n'.join(parts)
