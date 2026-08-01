import re
import numexpr

_HAS_MATH_CHARS = re.compile(r'[\d+\-*/().^%]')


def _extract_expression(query):
    q = query.strip()
    patterns = [
        r'(?:calculate|compute|solve|what is|evaluate|find)\s*(.+?)\s*[?\.]?\s*$',
        r'(?:calculate|compute|solve|what is|evaluate|find)\s*(.+)',
        r'^(.+?)\s*=\s*\?$',
    ]
    for p in patterns:
        m = re.search(p, q, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if candidate and _HAS_MATH_CHARS.search(candidate):
                return candidate
    if _HAS_MATH_CHARS.search(q):
        return q
    return None


def _sanitize(expr):
    expr = re.sub(r'[^0-9+\-*/().,%^e\s]', '', expr)
    expr = expr.replace('^', '**')
    return expr.strip()


def evaluate_expression(query):
    expr = _extract_expression(query)
    if expr is None:
        return None, None
    sanitized = _sanitize(expr)
    if not sanitized or not re.search(r'[\d]', sanitized):
        return None, None
    try:
        result = numexpr.evaluate(sanitized)
        if hasattr(result, '__len__') and not isinstance(result, (int, float, complex)):
            result = result.item() if result.size == 1 else result.tolist()
        return float(result) if isinstance(result, (int, float, complex)) else result, sanitized
    except (ZeroDivisionError, ValueError, TypeError, SyntaxError, MemoryError, KeyError):
        return None, None
