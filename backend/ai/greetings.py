import re

_GREETING_PATTERNS = [
    re.compile(r'^(hi+|hii+|hello+|hey+|yo+|sup+|hola+|namaste+)(\s+there)?[\s!.,?]*$', re.I),
    re.compile(r'^(good\s+(morning|afternoon|evening)|gm|goodnight|gn|goodbye|bye+|cya|see\s+ya)[\s!.,?]*$', re.I),
    re.compile(r'^(thank\s*you+|thanks+|thx+|ty+)[\s!.,?]*$', re.I),
    re.compile(r'^(ok|okay+|k|kk|sure|no\s+problem|np|done|great|cool|awesome)[\s!.,?]*$', re.I),
    re.compile(r'^(how\s+are\s+you(\s+doing)?|howdy|what\'?s\s+up|wassup|whats\s+up)[\s!.,?]*$', re.I),
]

_DEFAULT_REPLY = 'Hey! How can I help you today?'

_REPLIES = {
    'hello': 'Hello! How can I help you today?',
    'thanks': "You're welcome! Anything else I can help with?",
    'bye': 'Goodbye! Come back anytime.',
    'how_are_you': "I'm running well! What can I help you with?",
    'ok': 'Got it! What else?',
}


def greeting_reply(query):
    """Return a canned reply for pure greetings/acknowledgements, or None."""
    query = (query or '').strip()
    if not query or len(query) > 40:
        return None
    for index, pattern in enumerate(_GREETING_PATTERNS):
        if pattern.match(query):
            if index == 2:
                return _REPLIES['thanks']
            if index == 3:
                return _REPLIES['ok']
            if index == 4:
                return _REPLIES['how_are_you']
            lower = query.lower()
            if any(word in lower for word in ('goodbye', 'good bye', 'bye', 'cya')):
                return _REPLIES['bye']
            return _REPLIES['hello']
    return None
