import json
import os
import time

from django.core.management.base import BaseCommand

from ai.tests.test_regression import CORPUS_PATH, load_corpus, load_expected_intent
from ai.query_expander import QueryExpander
from ai.extractor import Extractor
from ai.retrieval_service import RetrievalService
from ai.research_pipeline import ResearchPipeline
from ai.retrieval_profiles import RetrievalProfile


class Command(BaseCommand):
    help = 'Run the regression suite over the prompt corpus (--live for full pipeline runs)'

    def add_arguments(self, parser):
        parser.add_argument('--live', action='store_true', help='run full pipeline (search + extraction) per prompt')
        parser.add_argument('--category', type=str, default=None, help='restrict to one corpus category')
        parser.add_argument('--limit', type=int, default=None, help='max prompts to process')
        parser.add_argument('--out', type=str, default=None, help='save live results JSON to this path')

    def handle(self, *args, **options):
        corpus = load_corpus()
        if options['category']:
            corpus = [p for p in corpus if p['category'] == options['category']]
        if options['limit']:
            corpus = corpus[:options['limit']]

        self.stdout.write(f'Corpus: {len(corpus)} prompts\n')

        if not options['live']:
            self._offline(corpus)
            return
        self._live(corpus, options['out'])

    def _offline(self, corpus):
        expected = load_expected_intent()
        failures = []
        for p in corpus:
            prompt = p['prompt']
            expanded = QueryExpander.expand(prompt)
            schema = Extractor.select_schema(prompt)
            profile_id, _ = RetrievalProfile.resolve(prompt)
            checks = []
            if p['category'] in ('ai_hardware', 'cpu'):
                checks.append(('site_queries', any(q.startswith('site:') for q in expanded)))
                checks.append(('schema_hardware', schema == 'hardware'))
            elif p['category'] in ('companies',):
                checks.append(('schema_company', schema == 'company'))
            else:
                checks.append(('expands', len(expanded) >= 2))
            if prompt in expected:
                checks.append(('intent', profile_id == expected[prompt]))
            failed = [name for name, ok in checks if not ok]
            status = 'PASS' if not failed else 'FAIL ' + ','.join(failed)
            if failed:
                failures.append((p, failed))
            self.stdout.write(f'[{p["category"]:>12}] {status}  {prompt}  intent={profile_id}')

        self.stdout.write(f'\n{len(corpus) - len(failures)}/{len(corpus)} passed')
        if failures:
            self.stderr.write('FAILED REGRESSIONS PRESENT')

    def _live(self, corpus, out_path):
        results = []
        for i, p in enumerate(corpus, 1):
            prompt = p['prompt']
            self.stdout.write(f'\n[{i}/{len(corpus)}] {p["category"]}: {prompt}')
            try:
                t0 = time.time()
                info = RetrievalService().execute(prompt, max_results=5)
                search_ms = int((time.time() - t0) * 1000)
                merged = {'results': info['results'], 'summary': info['summary']}
                t1 = time.time()
                dataset_text, verified, weighted = ResearchPipeline.run(merged, prompt)
                pipeline_ms = int((time.time() - t1) * 1000)
                if dataset_text is None:
                    raise RuntimeError('extraction failed: ' + (verified if isinstance(verified, str) else 'no extraction result'))
                fields = {f: e for f, e in (verified or {}).items() if e and e.get('value') is not None}
                with_sources = sum(1 for e in fields.values() if e.get('sources'))
                confs = [e['confidence'] for e in fields.values() if e.get('confidence') != 'none']
                checks = []
                for e in fields.values():
                    checks.extend(e.get('checks') or [])
                expected_intent = load_expected_intent().get(prompt)
                coverage = info.get('coverage') or {}
                report = {
                    'category': p['category'],
                    'prompt': prompt,
                    'schema': Extractor.select_schema(prompt),
                    'intent': info.get('intent'),
                    'intent_ok': expected_intent is None or info.get('intent') == expected_intent,
                    'coverage_required': coverage.get('required', []),
                    'coverage_found': coverage.get('found', []),
                    'coverage_missing': coverage.get('missing', []),
                    'search_count': info['count'],
                    'search_ms': search_ms,
                    'pipeline_ms': pipeline_ms,
                    'extraction_ok': dataset_text is not None and fields != {},
                    'fields_extracted': len(fields),
                    'fields_with_sources': with_sources,
                    'avg_confidence': round(sum({'high': 1, 'medium': 0.5, 'low': 0.25}.get(c, 0) for c in confs) / len(confs), 2) if confs else 0,
                    'checks_total': len(checks),
                    'checks_fail': sum(1 for c in checks if c['status'] == 'fail'),
                    'checks_warn': sum(1 for c in checks if c['status'] == 'warn'),
                }
                results.append(report)
                self.stdout.write(f'  schema={report["schema"]} intent={report["intent"]} fields={report["fields_extracted"]} '
                                  f'with_sources={report["fields_with_sources"]} avg_conf={report["avg_confidence"]} '
                                  f'coverage={len(report["coverage_required"])}/{len(report["coverage_required"]) - len(report["coverage_missing"])}'
                                  f'{" missing:" + ",".join(report["coverage_missing"]) if report["coverage_missing"] else ""} '
                                  f'checks={report["checks_total"]}(f{report["checks_fail"]}/w{report["checks_warn"]}) '
                                  f'{report["search_ms"] + report["pipeline_ms"]}ms')
            except Exception as exc:
                results.append({'category': p['category'], 'prompt': prompt, 'error': str(exc)})
                self.stderr.write(f'  ERROR: {exc}')

        ok = sum(1 for r in results if not r.get('error') and r.get('extraction_ok'))
        self.stdout.write(f'\nLIVE RUN: {ok}/{len(results)} with parseable extraction')
        if out_path:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            self.stdout.write(f'saved to {out_path}')
