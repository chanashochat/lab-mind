import os
import sys
from openai import OpenAI

client = OpenAI(
    base_url="https://api.anthropic.com/v1/",
    api_key=os.environ["ANTHROPIC_API_KEY"],
)

SYSTEM_PROMPT = """\
You are a document question-answering assistant. Follow these rules strictly:

1. Answer ONLY using information found in the document provided by the user.
   Do not use outside knowledge or guess.
2. After your answer, quote the exact passage from the document that supports it,
   introduced with "Reference: ".
3. If the answer is not in the document, reply with exactly this sentence and nothing else:
   "I can't find that in the document."
"""

def load_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def ask(document: str, question: str) -> str:
    user_message = f"Document:\n{document}\n\nQuestion: {question}"
    response = client.chat.completions.create(
        model="claude-haiku-4-5-20251001",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
    )
    return response.choices[0].message.content or ""

def main():
    if len(sys.argv) >= 3:
        file_path = sys.argv[1]
        question = sys.argv[2]
    elif len(sys.argv) == 2:
        file_path = sys.argv[1]
        question = input("Question: ")
    else:
        file_path = input("File path: ")
        question = input("Question: ")

    document = load_file(file_path)
    answer = ask(document, question)
    print(answer)

if __name__ == "__main__":
    main()
