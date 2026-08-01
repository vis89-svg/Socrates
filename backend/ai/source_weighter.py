from urllib.parse import urlparse
import re

TIER1_DOMAINS = {
    '.gov', '.edu', 'sec.gov', 'edgar.',
    'nvidia.com', 'amd.com', 'intel.com', 'apple.com', 'microsoft.com',
    'google.com', 'aws.amazon.com', 'cloud.google.com', 'azure.microsoft.com',
}

TIER2_DOMAINS = {
    'reuters.com', 'bloomberg.com', 'wsj.com', 'ft.com', 'economist.com',
    'anandtech.com', 'tomshardware.com', 'servethehome.com', 'techpowerup.com',
    'anandtech.com', 'arstechnica.com', 'theverge.com', 'engadget.com',
    'ieee.org', 'acm.org', 'acmqueue.com', 'queue.acm.org',
    'nvidianews.nvidia.com', 'investor.nvidia.com', 'developer.nvidia.com',
    'amd.com', 'www.amd.com', 'ir.amd.com',
    'intc.com', 'newsroom.intel.com', 'intel.ly',
    'hpcwire.com', 'nextplatform.com', 'top500.org', 'green500.org',
    'wikichip.org', 'chipsandcheese.com', 'semianalysis.com', 'candidateresearch.com',
    'berg.ru', 'fuse.wikichip.org',
}

TIER3_DOMAINS = {
    'wikipedia.org', 'crunchbase.com', 'tracxn.com', 'zoominfo.com',
    'techcrunch.com', 'forbes.com', 'venturebeat.com', 'zdnet.com',
    'computerworld.com', 'infoworld.com', 'networkworld.com',
    'annualreport.', 'investorrelations.', 'sec.gov', 'edgar.',
}

SOCIAL_DOMAINS = {
    'linkedin.com', 'twitter.com', 'x.com', 'facebook.com', 'instagram.com',
    'youtube.com', 'tiktok.com', 'reddit.com', 'medium.com', 'substack.com',
    'blogspot.com', 'wordpress.com',
}

BLOCKED_DOMAINS = {
    'youtube.com', 'facebook.com', 'instagram.com', 'tiktok.com', 'x.com',
    'pinterest.com', 'quora.com', 'stackexchange.com', 'stackoverflow.com',
}


class SourceWeighter:
    _cache = {}

    @classmethod
    def weight(cls, url):
        if url in cls._cache:
            return cls._cache[url]
        domain = urlparse(url).netloc.lower()
        domain = domain.removeprefix('www.')

        if any(b in domain for b in BLOCKED_DOMAINS):
            cls._cache[url] = 0
            return 0

        if any(domain.endswith(t) or t in domain for t in TIER1_DOMAINS):
            cls._cache[url] = 100
            return 100

        if any(t in domain for t in TIER2_DOMAINS):
            cls._cache[url] = 80
            return 80

        if any(t in domain for t in TIER3_DOMAINS):
            cls._cache[url] = 60
            return 60

        if any(t in domain for t in SOCIAL_DOMAINS):
            cls._cache[url] = 15
            return 15

        cls._cache[url] = 25
        return 25

    @classmethod
    def tier_label(cls, url):
        w = cls.weight(url)
        if w >= 80:
            return 'high_authority'
        if w >= 60:
            return 'medium_authority'
        if w >= 25:
            return 'general'
        if w >= 15:
            return 'social'
        return 'blocked'

    @classmethod
    def priority_sort(cls, results):
        scored = []
        for r in results:
            url = r.get('url', '')
            w = cls.weight(url)
            if w > 0:
                scored.append((w, r))
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored]
