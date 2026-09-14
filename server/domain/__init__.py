"""Pure financial domain: no I/O, no network, no async, no clock reads.

`as_of` is always passed in. That is what lets the whole planner be tested
without an LLM, a microphone, or a running server.
"""
