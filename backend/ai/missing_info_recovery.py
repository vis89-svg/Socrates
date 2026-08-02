import time

from .retrieval_service import RetrievalService
from .observability import Observability
from .feature_flags import FeatureFlags
from .required_fields import RequiredFields


MAX_RECOVERY_ATTEMPTS = 2
RECOVERY_KEYWORDS = {
    'temperature': ['temperature', 'temp', 'celsius', 'fahrenheit', '°C', '°F'],
    'condition': ['weather', 'condition', 'sunny', 'rainy', 'cloudy', 'overcast'],
    'humidity': ['humidity', 'moisture', 'damp'],
    'wind': ['wind', 'windy', 'gust'],
    'alert': ['alert', 'warning', 'cyclone', 'flood', 'rain alert'],
    'forecast': ['forecast', 'tomorrow', 'next day', 'coming days'],
    'rain_probability': ['rain', 'chance of rain', 'precipitation', 'rainfall'],
}


class MissingInfoRecovery:
    @staticmethod
    def check_and_recover(intent, provided_fields, query, tracer=None):
        missing = RequiredFields.get_missing_fields(intent, provided_fields)
        if not missing:
            return provided_fields, []

        recovered = dict(provided_fields)
        recovery_searches = []

        for field_id in missing:
            keywords = RECOVERY_KEYWORDS.get(field_id, [field_id])
            for attempt in range(MAX_RECOVERY_ATTEMPTS):
                recovery_query = f"{query} {' '.join(keywords)}"
                if tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
                    tracer.log_timed_stage('recovery_search', {
                        'field': field_id,
                        'attempt': attempt + 1,
                        'query': recovery_query,
                    })

                retrieval = RetrievalService()
                result = retrieval.execute(recovery_query, max_results=3)

                if result.get('results'):
                    recovered[field_id] = {
                        'source': 'recovery_search',
                        'query': recovery_query,
                        'results': result['results'][:3],
                        'attempt': attempt + 1,
                    }
                    recovery_searches.append({
                        'field': field_id,
                        'query': recovery_query,
                        'attempt': attempt + 1,
                        'found': True,
                    })
                    break
                else:
                    recovery_searches.append({
                        'field': field_id,
                        'query': recovery_query,
                        'attempt': attempt + 1,
                        'found': False,
                    })

        return recovered, recovery_searches

    @staticmethod
    def format_recovery_report(recovery_searches):
        if not recovery_searches:
            return ''
        lines = ['**Information Recovery Report**']
        for search in recovery_searches:
            status = 'Found' if search['found'] else 'Not found'
            lines.append(f"- {search['field']}: {status} (attempt {search['attempt']})")
        return '\n'.join(lines)