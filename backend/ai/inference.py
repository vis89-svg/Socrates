from .model_loader import get_model


def generate_stream(prompt):
    model = get_model()
    stream = model(
        prompt,
        max_tokens=2048,
        temperature=0.7,
        top_p=0.9,
        stop=['<|im_start|>', '<|im_end|>'],
        stream=True,
    )
    for output in stream:
        yield output['choices'][0]['text']
