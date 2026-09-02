from app.retrieve import RetrievedChunk


def generate_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """Call DeepSeek with the question and retrieved chunks; return answer text.

    Prompt constraints: answer only from the provided chunks; if they are
    insufficient or conflicting, say so; do not invent policies, steps,
    grades, or sources. This module does not retrieve, judge hits, or
    produce source links.
    """
    raise NotImplementedError
