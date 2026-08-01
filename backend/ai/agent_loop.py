import time
from .gap_detector import GapDetector
from .search_service import search_service
from .page_fetcher import PageFetcher
from .page_discovery import PageDiscovery
from .source_weighter import SourceWeighter
from .query_expander import QueryExpander


MAX_ITERATIONS = 2


class AgentLoop:
    @staticmethod
    def run(query, initial_results, max_iterations=MAX_ITERATIONS):
        start = time.time()
        all_results = list(initial_results.get('results', []))

        company_name = GapDetector.extract_company_name_from_results(all_results)
        if not company_name:
            name_from_query = QueryExpander._extract_company_name(query)
            if name_from_query:
                company_name = name_from_query

        if not company_name:
            return all_results, []

        gap_findings = []

        for iteration in range(max_iterations):
            gaps, found = GapDetector.detect_gaps(all_results, company_name)
            gap_findings.append({'iteration': iteration + 1, 'found': found, 'gaps': gaps})

            if not gaps:
                break

            gap_queries = GapDetector.gap_to_queries(gaps, company_name)
            if not gap_queries:
                break

            new_results = AgentLoop._execute_gap_search(gap_queries, all_results)
            if not new_results:
                break

            all_results.extend(new_results)
            all_results = SourceWeighter.priority_sort(AgentLoop._deduplicate(all_results))

        elapsed = time.time() - start
        summary = AgentLoop._loop_summary(gap_findings, len(all_results), elapsed)

        return all_results, gap_findings, summary

    @staticmethod
    def _execute_gap_search(gap_queries, existing_results):
        existing_urls = {r.get('url', '') for r in existing_results}
        new_results = []

        for gq in gap_queries:
            serialized, provider = search_service.search(gq, max_results=5)
            if serialized:
                for r in serialized:
                    url = r.get('url', '')
                    if url and url not in existing_urls and PageFetcher.is_fetchable(url) and SourceWeighter.weight(url) > 0:
                        existing_urls.add(url)
                        r['from_query'] = gq
                        r['from_loop'] = True
                        page_text = PageFetcher.fetch(url)
                        if page_text:
                            r['page_text'] = page_text
                        new_results.append(r)

        return new_results

    @staticmethod
    def _deduplicate(results):
        seen = set()
        deduped = []
        for r in results:
            url = r.get('url', '')
            if url and url not in seen:
                seen.add(url)
                deduped.append(r)
        return deduped

    @staticmethod
    def _loop_summary(gap_findings, total_results, elapsed):
        lines = []
        lines.append(f'Research iterations: {len(gap_findings)}')
        lines.append(f'Total unique sources: {total_results}')
        lines.append(f'Search time: {elapsed:.1f}s')
        for gf in gap_findings:
            if gf['gaps']:
                lines.append(f'  Iteration {gf["iteration"]}: found {len(gf["found"])} categories, {len(gf["gaps"])} gaps remain')
            else:
                lines.append(f'  Iteration {gf["iteration"]}: all categories covered')
        return '\n'.join(lines)
