import requests
from urllib.parse import urlparse


class PageFetcher:
    TIMEOUT = 10
    MAX_CHARS = 2000

    @staticmethod
    def fetch(url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            r = requests.get(url, headers=headers, timeout=PageFetcher.TIMEOUT)
            r.raise_for_status()
            content_type = r.headers.get('Content-Type', '')
            if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                return None

            import trafilatura
            text = trafilatura.extract(r.text, include_links=True, include_tables=True, no_fallback=False)
            if not text or not text.strip():
                text = PageFetcher._fallback_extract(r.text)

            if text and len(text) > PageFetcher.MAX_CHARS:
                text = text[:PageFetcher.MAX_CHARS] + '\n...[truncated]'

            return text.strip() if text and text.strip() else None
        except Exception:
            return None

    @staticmethod
    def _fallback_extract(html):
        import re
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        lines = text.split('\n')
        cleaned = [line.strip() for line in lines if len(line.strip()) > 40]
        return '\n'.join(cleaned)

    @staticmethod
    def is_fetchable(url):
        domain = urlparse(url).netloc.lower()
        blocked = ['youtube.com', 'facebook.com', 'instagram.com', 'tiktok.com']
        return not any(b in domain for b in blocked)
