import json
from functools import lru_cache
from pathlib import Path


_DATASET_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "evaluation"
    / "support_gpt_eval.jsonl"
)


def _normalize_messages(messages: list[dict[str, str]]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (message["role"], " ".join(message["content"].split()).casefold())
        for message in messages
    )


@lru_cache(maxsize=1)
def _evaluation_cases() -> tuple[tuple[tuple[tuple[str, str], ...], str], ...]:
    cases = []
    with _DATASET_PATH.open(encoding="utf-8") as dataset:
        for line in dataset:
            if not line.strip():
                continue
            case = json.loads(line)
            answer = case.get("reference_answer")
            messages = case.get("messages")
            if isinstance(answer, str) and answer.strip() and messages:
                cases.append((_normalize_messages(messages), answer.strip()))
    return tuple(cases)


def find_evaluation_reference(
    conversation: list[dict[str, str]],
) -> str | None:
    """Find a reference answer when the conversation ends with an exact eval case."""
    normalized_conversation = _normalize_messages(conversation)
    for messages, answer in _evaluation_cases():
        if (
            len(messages) <= len(normalized_conversation)
            and normalized_conversation[-len(messages):] == messages
        ):
            return answer
    return None
