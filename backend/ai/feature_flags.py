from django.conf import settings


class FeatureFlags:
    @staticmethod
    def is_enabled(flag):
        defaults = {
            'ENABLE_SEARCH': True,
            'ENABLE_MEMORY': True,
            'ENABLE_VISION': False,
            'ENABLE_CODE_EXECUTION': False,
            'ENABLE_CALCULATOR': False,
            'ENABLE_OBSERVABILITY': True,
            'ENABLE_QUERY_PLANNER': True,
            'ENABLE_PIPELINE_TRACE': True,
            'ENABLE_AGENT_LOOP': True,
            'ENABLE_PAGE_FETCH': True,
            'ENABLE_WEATHER_IMD': True,
            'ENABLE_WEATHER': True,
        }
        value = getattr(settings, flag, None)
        if value is not None:
            return value
        return defaults.get(flag, False)
