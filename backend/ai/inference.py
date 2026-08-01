from .model_loader import get_model


def generate_stream(prompt, max_tokens=None):
    model = get_model()
    if max_tokens is None:
        total_chars = len(prompt)
        if total_chars > 5000:
            max_tokens = 2048
        elif total_chars > 2000:
            max_tokens = 1536
        else:
            max_tokens = 1024
    stream = model(
        prompt,
        max_tokens=max_tokens,
        temperature=0.6,
        top_p=0.9,
        min_p=0.05,
        repeat_penalty=1.1,
        stop=['<|im_end|>', '<|im_start|>'],
        stream=True,
    )
    for output in stream:
        yield output['choices'][0]['text']
