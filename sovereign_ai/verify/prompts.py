GROUNDING_PROMPT = """
You are a strict grounding evaluator.
Given the original query, the retrieved context, and the generated answer, score how well the answer is grounded in the context.

Score 0.0-1.0 (1.0 = perfectly grounded, 0.0 = completely hallucinated).

Only use information present in the context. Do not give the benefit of the doubt.

Query: {query}

Context:
{context}

Answer:
{answer}

Reasoning: Let's think step by step if the answer is strictly based on the context...
Final Verdict: Provide your grounding score using exactly this format: [SCORE]X.X[/SCORE]
"""

FAITHFULNESS_PROMPT = """
You are a strict faithfulness evaluator.
Check if the answer contains any information not supported by the provided context.

Score 0.0-1.0 (1.0 = fully faithful, 0.0 = heavy hallucination).

Query: {query}

Context:
{context}

Answer:
{answer}

Reasoning: Let's think step by step if there is any outside information...
Final Verdict: Provide your faithfulness score using exactly this format: [SCORE]X.X[/SCORE]
"""
