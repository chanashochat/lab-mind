before added system prompt: 
response: Hello! I'm happy to help you with whatever you need.

1b. 

1. after added system prompt with content: "You are a pirate assistant.":
response: Ahoy, matey! Welcome aboard, and may yer sails be full o' wind and yer coffers full o' doubloons!

2. after add temperature = 0:
1. Ahoy there, matey! Welcome aboard, and may yer sails be full of adventure on the high seas! 🏴‍☠️
2. Ahoy there, matey! Welcome aboard, and may yer sails be full of adventure on the high seas! 🏴‍☠️

after change temperature = 1:
1. Ahoy there, matey! Welcome aboard, and may yer sails be full of adventure on the high seas! 🏴‍☠️
2. Ahoy there, me hearty! Welcome aboard, and may yer sails be full and yer treasure plentiful!


3. 
a. raw response: '```json\n{\n  "answer": "Hello! It\'s nice to meet you.",\n  "confidence": 0.95\n}\n```'
answer:     Hello! It's nice to meet you.
confidence: 0.95

b. raw response: '```json\n{\n  "answer": "Hello! I\'m an AI assistant here to help you with any questions or tasks you might have.",\n  "confidence": 0.95\n}\n```'
answer:     Hello! I'm an AI assistant here to help you with any questions or tasks you might have.
confidence: 0.95
answer:     Hello! I'm an AI assistant here to help you with any questions or tasks you might have.
confidence: 0.95


changing the temperature had the biggest effect on the response.


4. Closed vs open

Closed (OpenAI-style API, hello_llm.py, via Claude Haiku):
Easy: zero setup beyond an API key — no download, no local compute, and the model followed instructions (system prompt, JSON-only formatting) reliably on the first try. Responses came back in a second or two.
Cost: every call leaves the machine — the prompt (and any file/PII in it) goes to a third-party server, so I have to trust their data handling. It also costs money per token, needs a live internet connection, and is subject to whatever rate limits the provider sets.

Open (local HF, local_llm.py, Qwen2.5-0.5B-Instruct via transformers):
Gained: nothing leaves my machine — good for private/regulated data — and once the weights are downloaded there's no per-call cost and it works fully offline. I also get full control over the model and decoding params.
Paid for it: even this tiny (0.5B) model took ~50s on CPU for one response, versus ~1-2s for the API call. Quality was noticeably worse too — asked for a gluten-free pizza recipe and it confidently used a flour tortilla and all-purpose flour, i.e. gluten. Setup also required installing torch/transformers and several GB of disk for cached weights, and CPU/RAM usage spiked during generation. A bigger local model would likely fix the quality gap but would cost even more in RAM/GPU and latency.


