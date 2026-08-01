import hashlib
from diskcache import Cache


cache = Cache('search_cache')


def _key(query):
    return hashlib.sha256(query.lower().strip().encode()).hexdigest()


def get(query):
    return cache.get(_key(query))


def set(query, results, ttl=1800):
    cache.set(_key(query), results, expire=ttl)


def set_empty(query, ttl=300):
    cache.set(_key(query), [], expire=ttl)


def clear():
    cache.clear()
