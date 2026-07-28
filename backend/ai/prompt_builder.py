SYSTEM_PROMPT = """You are a helpful, harmless AI assistant. You provide clear, accurate answers. Think step by step."""


def build_prompt(user_message, history=None, memories=None):
    parts = [f'<|im_start|>system\n{SYSTEM_PROMPT}']

    if memories:
        memory_context = '\n'.join(f'- {m["content"]}' for m in memories)
        parts.append(f'\nRelevant memories:\n{memory_context}')

    if history:
        for msg in history[-10:]:
            role = msg['role']
            content = msg['content']
            parts.append(f'\n<|im_start|>{role}\n{content}')

    parts.append(f'\n<|im_start|>user\n{user_message}')
    parts.append('\n<|im_start|>assistant\n')
    return ''.join(parts)
