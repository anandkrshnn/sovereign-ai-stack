from sovereign_ai import SovereignEvaluator

def run_verified_query():
    # 1. Initialize the Evaluator (The "Verified Airlock")
    # This loads the DeBERTa-v3 model (approx 80ms latency)
    print("Loading NLI Evaluator...")
    evaluator = SovereignEvaluator()
    
    # 2. Scenario: A query and context are provided, but the LLM answer is a hallucination
    query = "What is the patient's heart rate?"
    context = "Observation 10:45 AM: The patient is resting. BP 120/80. Respiration 16/min."
    hallucinated_answer = "The patient's heart rate is 72 bpm." # Not in context!
    
    print(f"\n--- Scenario 1: Hallucination ---")
    print(f"Query: {query}")
    print(f"Context: {context}")
    print(f"Answer: {hallucinated_answer}")
    
    # 3. Evaluate grounding
    result = evaluator.evaluate(query=query, context=context, answer=hallucinated_answer)
    
    print(f"\nGrounding Score: {result['grounding_score']}")
    print(f"Faithfulness Score: {result['faithfulness_score']}")
    print(f"Passed Airlock: {result['passed']}") # Expected: False
    
    # 4. Scenario: Correct answer
    correct_answer = "The heart rate is not mentioned in the provided observation."
    print(f"\n--- Scenario 2: Correct Answer ---")
    print(f"Answer: {correct_answer}")
    
    result_correct = evaluator.evaluate(query=query, context=context, answer=correct_answer)
    print(f"Grounding Score: {result_correct['grounding_score']}")
    print(f"Passed Airlock: {result_correct['passed']}") # Expected: True

if __name__ == "__main__":
    run_verified_query()
