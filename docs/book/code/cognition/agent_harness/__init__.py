"""MARCIANA-ADVERSARIAL-v2 controlled agent-memory harness.

One shared agent loop — same model, same prompts, same tool contract, same
context budget — for every backend in the agent-memory track. A backend
supplies only the memory tool implementation; the harness owns everything the
model sees, so only the memory varies between rows.
"""
