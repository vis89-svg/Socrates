import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404

FRONTEND_DIST = Path(settings.BASE_DIR).parent / 'frontend' / 'dist'


def frontend(request, path=''):
    if path.startswith('api/') or path.startswith('share/') or path.startswith('admin/') or path.startswith('uploads/'):
        raise Http404
    if path:
        candidate = (FRONTEND_DIST / path).resolve()
        if candidate.is_relative_to(FRONTEND_DIST.resolve()) and candidate.is_file():
            content_type = mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream'
            return FileResponse(candidate.open('rb'), content_type=content_type)
    index = FRONTEND_DIST / 'index.html'
    if index.is_file():
        return FileResponse(index.open('rb'), content_type='text/html')
    raise Http404('Frontend not built. Run `npm run build` in the frontend directory.')
