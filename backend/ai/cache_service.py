import hashlib
from diskcache import Cache

_cache = Cache('orchestrator_cache')


def _key(namespace, query):
    raw = f'{namespace}:{query.lower().strip()}'
    return hashlib.sha256(raw.encode()).hexdigest()


class CacheService:
    def get(self, namespace, query):
        return _cache.get(_key(namespace, query))

    def set(self, namespace, query, value, ttl=1800):
        _cache.set(_key(namespace, query), value, expire=ttl)

    def set_empty(self, namespace, query, ttl=300):
        _cache.set(_key(namespace, query), [], expire=ttl)

    def clear(self):
        _cache.clear()


cache_service = CacheService()
