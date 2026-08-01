import os
import re
from datetime import datetime

from .feature_flags import FeatureFlags
from .model_router import ModelRouter
from .extractor import _parse_json

_TRIVIAL_PATTERN = re.compile(
    r'^(hi|hello|hey|thanks|thank you|ok|okay|bye|good ?morning|good ?afternoon|good ?evening|good ?night)[!.?\s]*$',
    re.IGNORECASE,
)

_TOOL_MAP = {
    'search': 'needs_search',
    'calculator': 'needs_math',
    'code': 'needs_code',
    'code_executor': 'needs_code',
    'documents': 'needs_documents',
    'memory': 'needs_memory',
}

_ROUTES = ('chat', 'coding', 'reasoning')


def _load_prompt(name):
    path = os.path.join(os.path.dirname(__file__), 'prompts', name)
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''


class QueryPlanner:
    @staticmethod
    def plan(query, history=None):
        if not FeatureFlags.is_enabled('ENABLE_QUERY_PLANNER'):
            return None

        q = query.strip()
        if not q or _TRIVIAL_PATTERN.match(q):
            return None

        prompt_template = _load_prompt('query_planner.md')
        if not prompt_template:
            return None

        date_str = datetime.now().strftime('%A, %B %d, %Y')
        prompt = prompt_template.replace('{{DATE}}', date_str)
        prompt += f'\n\nUser request:\n{q}\n\nJSON plan:'

        raw_output = ''
        try:
            for token in ModelRouter.generate_stream(prompt, model_key='planner', max_tokens=150):
                raw_output += token
        except Exception:
            return None

        parsed = _parse_json(raw_output)
        if not parsed:
            return None

        return QueryPlanner._normalize(parsed, query)

    @staticmethod
    def _normalize(parsed, original_query):
        rewritten = parsed.get('rewritten_query')
        tools = []
        for t in parsed.get('tools') or []:
            if isinstance(t, str):
                cap = _TOOL_MAP.get(t.strip().lower())
                if cap and cap not in tools:
                    tools.append(cap)

        route = parsed.get('model_route')
        if route not in _ROUTES:
            route = None

        needs_search = parsed.get('needs_search')
        if not isinstance(needs_search, bool):
            needs_search = None

        required_sources = []
        for src in parsed.get('required_sources') or []:
            if not isinstance(src, str):
                continue
            clean = src.strip().lower()
            if clean.startswith('site:'):
                clean = clean[len('site:'):]
            clean = clean.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
            if clean and clean not in required_sources and len(required_sources) < 6:
                required_sources.append(clean)

        return {
            'rewritten_query': rewritten if isinstance(rewritten, str) and rewritten.strip() else original_query,
            'intent': parsed.get('intent') if isinstance(parsed.get('intent'), str) else 'chat',
            'needs_search': needs_search,
            'tools': tools,
            'model_route': route,
            'required_sources': required_sources,
        }
