import json
import os
import re

from django.core.management.base import BaseCommand

from ai.golden_facts import GoldenFacts
from ai.extractor import Extractor
from ai.retrieval_service import RetrievalService
from ai.research_pipeline import _extract_generate


def _bare_domain(url):
    return re.sub(r'^https?://(www\.)?', '', url or '').split('/')[0].split('?')[0]


def _extract_entity_metadata(entity_key, entity):
    domain = _bare_domain(entity['website'])
    queries = [
        f'{entity["name"]} founded headquarters CEO about',
        f'site:{domain} about company history leadership',
        f'site:{domain} about us founded headquarters',
    ]
    seen = set()
    results = []
    for q in queries:
        info = RetrievalService().execute(q, max_results=3)
        for r in info.get('results', []):
            if r.get('url') and r['url'] not in seen:
                seen.add(r['url'])
                results.append(r)
        if len(results) >= 6:
            break

    summary = RetrievalService._build_summary(results)
    return Extractor.extract(summary, _extract_generate, schema='company')


class Command(BaseCommand):
    help = 'Propose updates to golden_facts.json from official-source searches (--apply to write)'

    def add_arguments(self, parser):
        parser.add_argument('--entity', type=str, default=None, help='refresh a single entity key')
        parser.add_argument('--apply', action='store_true', help='write proposed changes to golden_facts.json')

    def handle(self, *args, **options):
        entities = GoldenFacts.entities()
        keys = [options['entity']] if options['entity'] else list(entities)
        changes = {}

        for key in keys:
            entity = entities[key]
            self.stdout.write(f'\n[{key}] {entity["name"]} (official: {entity["website"]})')
            try:
                extracted = _extract_entity_metadata(key, entity)
            except Exception as exc:
                self.stderr.write(f'  ERROR: {exc}')
                continue
            for field, golden_field in {'founded': 'founded', 'headquarters': 'headquarters',
                                        'ceo': 'ceo'}.items():
                entry = extracted.get(field)
                value = entry.get('value') if entry else None
                if not value:
                    continue
                old = entity.get(golden_field)
                if old and old.lower() in str(value).lower():
                    self.stdout.write(f'  {field}: unchanged ({old})')
                    continue
                changes.setdefault(key, {})[golden_field] = str(value)
                self.stdout.write(f'  {field}: {old or "(none)"} -> {value}')

        if not changes:
            self.stdout.write('\nNo changes proposed.')
            return

        if not options['apply']:
            self.stdout.write('\n(no changes written; rerun with --apply to commit)')
            return

        path = os.path.join(os.path.dirname(__file__), '..', 'golden_facts.json')
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        for key, fields in changes.items():
            for field, value in fields.items():
                data['entities'][key][field] = value
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.stdout.write(f'\nUpdated {len(changes)} entities in {path}')
