from ai.inference import generate_stream
from chat.models import Message


def summarize_conversation(conversation):
    messages = Message.objects.filter(conversation=conversation).values('role', 'content')
    transcript = '\n'.join(f'{m["role"]}: {m["content"]}' for m in messages)
    prompt = f'<|im_start|>system\nSummarize this conversation concisely.\n<|im_start|>user\n{transcript}\n<|im_start|>assistant\n'
    summary = ''.join(generate_stream(prompt))
    return summary
