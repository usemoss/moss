"""Show the difference Moss makes: the same questions, the same LLM, with and
without Moss grounding.

Each question is answered twice by the same model with the same system prompt.
The only difference is whether the Moss grounding block (exactly what the TEN
`main_python` control extension injects per turn via
`MossSessionManager.query_context`) is prepended to the user's turn.

Prereqs:
    pip install ten-moss openai python-dotenv    # ten-moss editable until published
    python create_index.py                        # build the MOSS_INDEX_NAME index first

Env (via .env or exported):
    MOSS_PROJECT_ID, MOSS_PROJECT_KEY, MOSS_INDEX_NAME, OPENAI_API_KEY, OPENAI_MODEL

Usage:
    python compare.py                     # default question set
    python compare.py "your question?"    # one or more custom questions
    python compare.py --json report.json  # also write structured results
"""

import argparse
import asyncio
import json
import os

from openai import AsyncOpenAI
from ten_moss import MossSessionManager

try:  # python-dotenv is optional
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(*a, **k):
        """No-op fallback when python-dotenv is not installed."""
        return False


SYSTEM = (
    "You are the customer-support assistant for an online store. "
    "Answer the customer's question directly and concisely (1-2 sentences)."
)

DEFAULT_QUESTIONS = [
    "How long do refunds take?",
    "Can I cancel my order after I place it?",
    "Which payment methods can I use?",
    "Do you offer price matching?",
    "How fast is express shipping?",
]


async def _answer(client: AsyncOpenAI, model: str, user_content: str) -> str:
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_content},
        ],
        temperature=0,
        max_tokens=150,
    )
    return (resp.choices[0].message.content or "").strip()


async def run(questions: list[str], json_path: str | None) -> None:
    """Answer each question without Moss and with Moss; print the pair."""
    load_dotenv()
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    moss = MossSessionManager(
        project_id=os.environ["MOSS_PROJECT_ID"],
        project_key=os.environ["MOSS_PROJECT_KEY"],
        index_name=os.environ.get("MOSS_INDEX_NAME", "ten-moss-demo"),
    )
    await moss.open()

    rows = []
    for q in questions:
        without = await _answer(client, model, q)
        grounding = await moss.query_context(q)
        grounded_turn = f"{grounding}\n\n[Current User Question]\n{q}" if grounding else q
        with_moss = await _answer(client, model, grounded_turn)
        rows.append(
            {"question": q, "without_moss": without, "with_moss": with_moss, "grounding": grounding}
        )
        print(f"\n### {q}")
        print(f"  WITHOUT Moss: {without}")
        print(f"  WITH Moss:    {with_moss}")

    if json_path:
        with open(json_path, "w") as f:
            json.dump({"model": model, "system_prompt": SYSTEM, "rows": rows}, f, indent=2)
        print(f"\nsaved -> {json_path}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Compare LLM answers without vs with Moss grounding.")
    parser.add_argument("questions", nargs="*", help="custom questions (defaults to a built-in set)")
    parser.add_argument("--json", dest="json_path", help="write structured results to this path")
    args = parser.parse_args()
    asyncio.run(run(args.questions or DEFAULT_QUESTIONS, args.json_path))


if __name__ == "__main__":
    main()
