import os
from datetime import datetime


def _load_prompt(name):
    path = os.path.join(os.path.dirname(__file__), 'prompts', name)
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''


class ContextBuilder:
    @staticmethod
    def build(query, capabilities, tool_results, history=None):
        parts = []
        date_str = datetime.now().strftime('%A, %B %d, %Y')

        system = _load_prompt('system.md')
        if system:
            system = system.replace('{{DATE}}', date_str)
            parts.append(f'<|im_start|>system\n{system}')

        if tool_results.get('memories'):
            memory_prompt = _load_prompt('memory.md')
            mem_text = '\n'.join(f'- {m["content"]}' for m in tool_results['memories'])
            memory_prompt = memory_prompt.replace('{{MEMORIES}}', mem_text)
            parts.append(f'\n{memory_prompt}')

        if tool_results.get('search') and tool_results['search'].get('summary'):
            search_prompt = _load_prompt('search.md')
            search_prompt = search_prompt.replace('{{SEARCH_RESULTS}}', tool_results['search']['summary'])
            parts.append(f'\n{search_prompt}')

        if 'needs_code' in capabilities:
            coding = _load_prompt('coding.md')
            if coding:
                parts.append(f'\n{coding}')

        if tool_results.get('calculation'):
            calc = tool_results['calculation']
            parts.append(f'\n<|im_start|>system\nCalculator result: {calc["expression"]} = {calc["result"]}')

        if tool_results.get('code_result'):
            parts.append(f'\n<|im_start|>system\nCode output:\n{tool_results["code_result"]}')

        if tool_results.get('documents'):
            doc_lines = []
            for d in tool_results['documents']:
                if d.get('text'):
                    doc_lines.append(f'--- {d["name"]} ---\n{d["text"]}')
                else:
                    doc_lines.append(f'--- {d["name"]} ---\n[The user attached a file named "{d["name"]}" (type: {d.get("type", "unknown")}). It could not be read as text.]')
            doc_prompt = _load_prompt('document.md')
            if doc_prompt:
                doc_prompt = doc_prompt.replace('{{DOCUMENTS}}', '\n\n'.join(doc_lines))
                parts.append(f'\n{doc_prompt}')

        if 'needs_reasoning' in capabilities or 'needs_math' in capabilities:
            reasoning = _load_prompt('reasoning.md')
            if reasoning:
                parts.append(f'\n{reasoning}')

        if history:
            for msg in history[-10:]:
                role = msg['role'] if isinstance(msg, dict) else msg.role
                content = msg['content'] if isinstance(msg, dict) else msg.content
                parts.append(f'\n<|im_start|>{role}\n{content}')

        parts.append(f'\n<|im_start|>user\n{query}')
        parts.append('\n<|im_start|>assistant\n')

        return ''.join(parts)
