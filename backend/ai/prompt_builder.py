from datetime import datetime

DATE_STRING = datetime.now().strftime('%A, %B %d, %Y')
SYSTEM_PROMPT = f"""You are a helpful, harmless AI assistant. Current date: {DATE_STRING}. You provide clear, accurate answers. Think step by step."""


def build_prompt(user_message, history=None, memories=None, web_results=None):
    parts = [f'<|im_start|>system\n{SYSTEM_PROMPT}']

    if memories:
        memory_context = '\n'.join(f'- {m["content"]}' for m in memories)
        parts.append(f'\nRelevant memories:\n{memory_context}')

    if web_results:
        web_section = '\n\nCurrent web search results (use these to answer if relevant):\n'
        for i, r in enumerate(web_results, 1):
            web_section += f'{i}. {r["title"]}\n   {r["snippet"]}\n   Source: {r["url"]}\n'
        parts.append(web_section)

    if history:
        for msg in history[-10:]:
            role = msg['role']
            content = msg['content']
            parts.append(f'\n<|im_start|>{role}\n{content}')

    parts.append(f'\n<|im_start|>user\n{user_message}')
    parts.append('\n<|im_start|>assistant\n')
    return ''.join(parts)
