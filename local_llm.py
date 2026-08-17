from transformers import pipeline

MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

generator = pipeline("text-generation", model=MODEL)

prompt = "Give me a recipe for gluten-free pizza."

result = generator(
    [{"role": "user", "content": prompt}],
    max_new_tokens=512,
    do_sample=False,
)

reply = result[0]["generated_text"][-1]["content"]
print(reply)
