import json
import os
from datetime import datetime

from .extractor import _parse_json
from .feature_flags import FeatureFlags
from .model_router import ModelRouter
from .retrieval_service import RetrievalService
from .calculator_service import evaluate_expression
from .page_fetcher import PageFetcher
from .code_executor import execute_code


MAX_ITERATIONS = 4
DECISION_MAX_TOKENS = 120
ANSWER_MAX_TOKENS = 1536

_AGENT_IDENTITY = (
    'You are Owl, the AI assistant for this application. Current date: {date}.\n'
    'You answer honestly: evidence over assumptions, admit uncertainty, never invent facts.'
)


def _load_prompt(name):
    path = os.path.join(os.path.dirname(__file__), 'prompts', name)
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''


def _parse_action(text):
    """Return (tool, args) if the text is a tool call, else None."""
    if not text:
        return None
    text = text.strip()
    if text.upper().startswith('TOOL'):
        text = text[len('TOOL'):].strip()
    parsed = _parse_json(text)
    if not isinstance(parsed, dict) or 'tool' not in parsed:
        return None
    tool = str(parsed.get('tool') or '').strip().lower()
    if not tool:
        return None
    args = {k: v for k, v in parsed.items() if k != 'tool'}
    return tool, args


def _tool_label(tool, args):
    if tool == 'search':
        q = (args.get('query') or '')[:60]
        return f'🔍 Searching the web for "{q}"...'
    if tool == 'calculate':
        return '🧮 Calculating...'
    if tool == 'fetch_url':
        return '🌐 Fetching page...'
    if tool == 'code':
        return '💻 Running code...'
    return 'Running tool...'


class DecisionLoop:
    """Model-driven tool-calling loop (ReAct-style).

    Each iteration asks the model to either emit a single JSON tool call or
    signal readiness to answer. Tool results are appended to the transcript,
    then the loop repeats until the model answers or the iteration cap is hit.
    """

    def __init__(self, query, history=None, user=None, conversation_id=None,
                 files_data=None, model_key='chat', web_search=None,
                 context_blocks=None, tracer=None, generate_fn=None):
        self.query = query
        self.history = history or []
        self.user = user
        self.conversation_id = conversation_id
        self.files_data = files_data or []
        self.model_key = model_key
        self.web_search = web_search
        self.context_blocks = context_blocks or []
        self.tracer = tracer
        self.generate_fn = generate_fn or ModelRouter.generate_stream

        self.transcript = []
        self.search_results = []
        self.last_provider = None
        self.tool_count = 0
        self.strikes = 0
        self.final_text = ''

    # ------------------------------------------------------------------ #
    # prompt construction
    # ------------------------------------------------------------------ #
    def _system_prompt(self, condensed=False):
        date_str = datetime.now().strftime('%A, %B %d, %Y')
        if condensed:
            system = _AGENT_IDENTITY.format(date=date_str)
        else:
            system = _load_prompt('system.md').replace('{{DATE}}', date_str)
        agent = _load_prompt('agent_tools.md')
        agent = agent.replace('{{TOOLS}}', self._tool_defs_text())
        parts = [system, agent]
        if self.web_search is True:
            parts.append(
                'The user has web search enabled. You should call the search tool before answering '
                'whenever the request could involve up-to-date information.'
            )
        return '\n\n'.join(p for p in parts if p)

    def _tool_defs_text(self):
        lines = []
        if FeatureFlags.is_enabled('ENABLE_SEARCH'):
            lines.append('- search: search the web for up-to-date information. '
                         'Args: {"query": "search query"}')
        if FeatureFlags.is_enabled('ENABLE_CALCULATOR'):
            lines.append('- calculate: evaluate a math expression exactly. '
                         'Args: {"expression": "2 + 3 * 4"}')
        if FeatureFlags.is_enabled('ENABLE_PAGE_FETCH'):
            lines.append('- fetch_url: read the text of a specific web page. '
                         'Args: {"url": "https://example.com/page"}')
        if FeatureFlags.is_enabled('ENABLE_CODE_EXECUTION'):
            lines.append('- code: run Python code in a safe sandbox (no network, no filesystem). '
                         'Args: {"code": "print(2**10)"}')
        return '\n'.join(lines) if lines else '(no tools available)'

    def _context_text(self):
        parts = list(self.context_blocks)
        if self.history:
            lines = []
            for msg in self.history[-8:]:
                role = msg['role'] if isinstance(msg, dict) else msg.role
                content = msg['content'] if isinstance(msg, dict) else msg.content
                lines.append(f'{role}: {content}')
            parts.append('Recent conversation:\n' + '\n'.join(lines))
        if self.files_data:
            doc_lines = []
            for d in self.files_data:
                text = d.get('text') or f'[File attached: {d.get("name", "file")} — not readable as text]'
                doc_lines.append(f'--- {d.get("name", "file")} ---\n{text}')
            parts.append('Attached files:\n' + '\n\n'.join(doc_lines))
        return '\n\n'.join(parts)

    def _base_prompt(self, condensed=False, max_result_chars=None):
        parts = [f'<|im_start|>system\n{self._system_prompt(condensed=condensed)}']
        ctx = self._context_text()
        if ctx:
            parts.append(f'<|im_start|>system\nContext:\n{ctx}')
        if self.transcript:
            transcript_text = '\n'.join(
                f'<|im_start|>{entry["role"]}\n{self._transcript_content(entry, max_result_chars)}'
                for entry in self.transcript
            )
            parts.append(f'<|im_start|>system\nTool activity so far:\n{transcript_text}')
        parts.append(f'<|im_start|>user\n{self.query}')
        return '\n'.join(parts)

    @staticmethod
    def _transcript_content(entry, max_result_chars):
        content = entry['content']
        if max_result_chars is None or entry['role'] != 'tool':
            return content
        return content if len(content) <= max_result_chars else content[:max_result_chars] + '\n...[truncated]'

    def _decision_prompt(self):
        return self._base_prompt(condensed=True, max_result_chars=350) + '\n<|im_start|>assistant\n'

    def _answer_prompt(self):
        return (
            self._base_prompt()
            + '\n\nAll tool calls are complete. Write your final answer to the user now. '
            + 'Every factual claim MUST come from the tool results above; if a detail is not in them, '
            + 'say it is not stated in the sources. Cite sources by URL for each claim.'
            + '\n<|im_start|>assistant\n'
        )

    # ------------------------------------------------------------------ #
    # model calls
    # ------------------------------------------------------------------ #
    def _call(self, prompt, max_tokens):
        try:
            return ''.join(self.generate_fn(prompt, model_key=self.model_key, max_tokens=max_tokens))
        except Exception:
            return ''.join(self.generate_fn(prompt, model_key='fallback', max_tokens=max_tokens))

    # ------------------------------------------------------------------ #
    # tool execution
    # ------------------------------------------------------------------ #
    def _dispatch(self, tool, args):
        try:
            if tool == 'search':
                return self._search(args.get('query'))
            if tool == 'calculate':
                return self._calculate(args.get('expression'))
            if tool == 'fetch_url':
                return self._fetch(args.get('url'))
            if tool == 'code':
                return self._code(args.get('code'))
            return 'ERROR: unknown tool'
        except Exception as exc:
            return f'ERROR: tool {tool} failed: {exc}'

    def _search(self, query):
        query = (query or '').strip()
        if not query or not FeatureFlags.is_enabled('ENABLE_SEARCH'):
            return 'ERROR: search is unavailable'
        retrieval = RetrievalService()
        info = retrieval.execute(query, intent=None, required_sources=None)
        results = info.get('results') or []
        self.search_results.extend(results)
        self.last_provider = info.get('provider')
        lines = [f'Search completed: {len(results)} results.']
        for i, r in enumerate(results[:4], 1):
            lines.append(f'{i}. {r.get("title", "Untitled")}')
            lines.append(f'   URL: {r.get("url", "")}')
            snippet = r.get('snippet') or ''
            if snippet:
                lines.append(f'   Snippet: {snippet[:300]}')
        if len(results) > 4:
            lines.append(f'... and {len(results) - 4} more results.')
        return '\n'.join(lines)

    def _calculate(self, expression):
        expression = (expression or '').strip()
        if not expression:
            return 'ERROR: no expression provided'
        result, expr = evaluate_expression(expression)
        if result is None:
            return 'ERROR: could not evaluate expression'
        return f'Calculation: {expr} = {result}'

    def _fetch(self, url):
        url = (url or '').strip()
        if not url.startswith(('http://', 'https://')):
            return 'ERROR: only http(s) URLs are allowed'
        if not PageFetcher.is_fetchable(url):
            return 'ERROR: this site cannot be fetched'
        text = PageFetcher.fetch(url)
        if not text:
            return 'ERROR: failed to fetch page (blocked, non-HTML, or unreachable)'
        return f'Page content from {url}:\n{text}'

    def _code(self, code):
        code = (code or '').strip()
        if not code:
            return 'ERROR: no code provided'
        if not FeatureFlags.is_enabled('ENABLE_CODE_EXECUTION'):
            return 'ERROR: code execution is disabled'
        result = execute_code(code)
        if not result['success']:
            return f"ERROR: {result.get('error') or result.get('stderr') or 'execution failed'}"
        stdout = result.get('stdout') or ''
        if not stdout:
            return 'Code ran successfully (no output).'
        if len(stdout) > 4000:
            stdout = stdout[:4000] + '\n...[truncated]'
        return f'Code output:\n{stdout}'

    # ------------------------------------------------------------------ #
    # main loop
    # ------------------------------------------------------------------ #
    def run(self):
        if self.tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            self.tracer.log_timed_stage('decision_loop_start', {})

        if self.web_search is True:
            yield from self._execute_tool('search', {'query': self.query})

        while self.tool_count < MAX_ITERATIONS:
            decision = self._call(self._decision_prompt(), DECISION_MAX_TOKENS)
            action = _parse_action(decision)
            if action is None:
                self.strikes += 1
                if self.strikes >= 2:
                    break
                continue
            tool, args = action
            self.strikes = 0
            if self.transcript and self.transcript[-2]['role'] == 'assistant':
                if self.transcript[-2]['content'] == json.dumps({'tool': tool, **args}):
                    self.strikes += 1
                    if self.strikes >= 2:
                        break
                    continue
            yield from self._execute_tool(tool, args)

        if self.tracer and FeatureFlags.is_enabled('ENABLE_PIPELINE_TRACE'):
            self.tracer.log_timed_stage('decision_loop_complete', {
                'tool_calls': self.tool_count,
                'strikes': self.strikes,
            })

        yield {'type': 'tool_use', 'tool': 'answer', 'label': 'Generating answer...', 'args': {}}

        self.final_text = self._call(self._answer_prompt(), ANSWER_MAX_TOKENS)
        for token in self.final_text:
            yield {'type': 'token', 'content': token}

    def _execute_tool(self, tool, args):
        self.tool_count += 1
        yield {'type': 'tool_use', 'tool': tool, 'label': _tool_label(tool, args), 'args': args}

        result_text = self._dispatch(tool, args)
        self.transcript.append({
            'role': 'assistant',
            'content': json.dumps({'tool': tool, **args}),
        })
        self.transcript.append({'role': 'tool', 'content': result_text})

        if tool == 'search':
            evidence = [
                {
                    'url': r.get('url', ''),
                    'title': (r.get('title') or 'Untitled')[:120],
                    'published_date': r.get('published_date', '') or r.get('date', '') or '',
                }
                for r in self.search_results[:10]
                if r.get('url')
            ]
            yield {
                'type': 'search_results',
                'count': len(self.search_results),
                'provider': self.last_provider,
                'evidence': evidence,
            }
