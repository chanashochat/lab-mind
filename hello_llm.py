import os
import json
from pydantic import BaseModel
from openai import OpenAI


class Answer(BaseModel):
    answer: str
    confidence: float

client = OpenAI(
    base_url="https://api.anthropic.com/v1/",
    api_key=os.environ["ANTHROPIC_API_KEY"],
)

response = client.chat.completions.create(
    model="claude-haiku-4-5-20251001",
    messages=[
        {
            "role": "system",
            "content": (
                "Reply with JSON only. Your response must be a single JSON object "
                "with exactly two fields: "
                "\"answer\" (a string) and \"confidence\" (a number between 0 and 1)."
            ),
        },
        {"role": "user", "content": "Say hello in one sentence."},
    ],
    temperature=0.8,
)

raw = response.choices[0].message.content or ""
print("raw response:", repr(raw))  # debug: see exactly what came back

# strip markdown code fences if the model wrapped the JSON
if raw.startswith("```"):
    raw = raw.split("```")[1]
    if raw.startswith("json"):
        raw = raw[4:]
raw = raw.strip()

# (a) Raw JSON: parse with json module and print individual fields
data = json.loads(raw)
print("answer:    ", data["answer"])
print("confidence:", data["confidence"])

# (b) Pydantic: validate shape and types — raises ValidationError on bad data
answer = Answer.model_validate_json(raw)
print("answer:    ", answer.answer)
print("confidence:", answer.confidence)
