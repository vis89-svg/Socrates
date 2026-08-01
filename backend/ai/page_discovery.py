from urllib.parse import urlparse, urljoin


_PAGE_TYPES = [
    'about', 'about-us', 'about_us', 'company',
    'team', 'leadership', 'management', 'board',
    'careers', 'jobs', 'join-us',
    'contact', 'contact-us',
    'products', 'services', 'solutions',
    'news', 'press', 'blog',
    'investors', 'investor-relations',
]


class PageDiscovery:
    @staticmethod
    def discover(base_url):
        discovered = []
        base = base_url.rstrip('/')

        for path in _PAGE_TYPES:
            url = urljoin(base + '/', path)
            discovered.append({
                'url': url,
                'type': PageDiscovery._classify(path),
                'path': path,
            })

        return discovered

    @staticmethod
    def _classify(path):
        path_lower = path.lower().replace('-', '_').replace(' ', '_')
        if path_lower in ('about', 'about_us', 'about-us', 'company'):
            return 'about'
        if path_lower in ('team', 'leadership', 'management', 'board'):
            return 'leadership'
        if path_lower in ('careers', 'jobs', 'join_us', 'join-us'):
            return 'careers'
        if path_lower in ('contact', 'contact_us', 'contact-us'):
            return 'contact'
        if path_lower in ('products', 'services', 'solutions'):
            return 'products'
        if path_lower in ('news', 'press', 'blog'):
            return 'news'
        if path_lower in ('investors', 'investor_relations', 'investor-relations'):
            return 'investors'
        return 'other'

    @staticmethod
    def get_base_domain(url):
        parsed = urlparse(url)
        return f'{parsed.scheme}://{parsed.netloc}'

    @staticmethod
    def is_same_domain(url1, url2):
        return urlparse(url1).netloc.lower() == urlparse(url2).netloc.lower()
