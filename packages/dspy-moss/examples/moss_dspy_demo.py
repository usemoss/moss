"""Demo: Moss semantic search with DSPy.

Two usage patterns:
  1. MossRM as the global DSPy retriever (dspy.configure(rm=...))
  2. MossRM passed directly as a ReAct tool
"""

import os

import dspy
from dotenv import load_dotenv

from dspy_moss import MossRM

load_dotenv(os.path.join(os.getcwd(), ".env"))

lm = dspy.LM(model="openai/gpt-4.1-mini", api_key=os.environ["OPENAI_API_KEY"])

# --- Pattern 1: configured retriever ---------------------------------

rm = MossRM(index_name="faqs")
rm.load_index()  # load into this process's memory — required before any query
dspy.configure(lm=lm, rm=rm)

retrieve = dspy.Retrieve(k=3)
result = retrieve("What is the refund policy?")
for passage in result.passages:
    print(passage[:120])

# --- Pattern 2: ReAct tool -------------------------------------------
# MossRM.forward() is already sync — pass it directly, no wrapper needed.

agent = dspy.ReAct(signature="question -> answer", tools=[rm], max_iters=5)
response = agent(question="Which payment methods do you accept?")
print(response.answer)
