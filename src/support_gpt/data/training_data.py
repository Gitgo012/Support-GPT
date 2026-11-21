"""Policy-aware cleanup and deterministic splitting for support SFT data."""

import hashlib
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.response_validator import (
    PLACEHOLDER_PATTERN,
    UNSUPPORTED_ACTION_PATTERNS,
)


PLACEHOLDER_FIELD_PATTERN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
UNSUPPORTED_ACTION_PATTERNS_FOR_TRAINING = (
    *UNSUPPORTED_ACTION_PATTERNS,
    re.compile(
        r"\b(?:i|we)(?:\s+(?:can|will|could|would|am going to)|'ll)\s+"
        r"(?:(?:be happy to|be glad to|definitely|certainly|help(?: you)?"
        r"(?:\s+to)?|assist you (?:in|with))\s+)*"
        r"(?:check|look up|verify|retriev(?:e|ing)|access|locat(?:e|ing))\b"
        r"[^.!?\r\n]{0,80}\b"
        r"(?:your|the|specific|exact|necessary|account|order|booking|refund|"
        r"payment|invoice|fee|charges?|transaction|status|records?|information)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i|we)(?:\s+(?:can|will|could|would|am going to)|'ll)\s+"
        r"(?:(?:be happy to|be glad to|definitely|certainly|help(?: you)?"
        r"(?:\s+to)?)\s+)*"
        r"(?:check|look up|verify|retriev(?:e|ing)|access|locat(?:e|ing))\s+"
        r"(?:it|this|that)\s+(?:for you|on your behalf)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:allow|give) me (?:a )?(?:moment|minute)\b"
        r"[^.!?\r\n]{0,80}\b(?:assist you in |help you )?"
        r"(?:locat(?:e|ing)|retriev(?:e|ing)|look(?:ing)? up|"
        r"check(?:ing)?|access(?:ing)?)\b"
        r"[^.!?\r\n]{0,60}\b(?:invoice|order|account|refund|payment|"
        r"subscription|transaction|fee|charges?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i|we)(?:\s+(?:will|can|have|am going to|am|are)|'ll)\s+"
        r"(?:(?:be\s+(?:happy|glad)\s+to|definitely|certainly|promptly|"
        r"quickly|easily)\s+)*"
        r"(?:(?:be able to|help(?: you)?(?:\s+to)?)\s+)?"
        r"(?:initiate|submit|process|issue|approve|cancel(?:ed|led)?|"
        r"refund|reverse|change|update|modify|edit|delete|remove|add|"
        r"retrieve|transfer|connect|route|escalate|"
        r"make\s+(?:the\s+)?(?:necessary\s+)?"
        r"(?:changes?|updates?|corrections?|adjustments?))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:your\s+)?(?:refund|order|cancellation|subscription|payment|charge)"
        r"\s+(?:will be|is being)\s+"
        r"(?:processed|completed|approved|cancelled|canceled|issued|initiated)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i|we)\s+(?:cancelled|canceled|processed|issued|approved|refunded)"
        r"\s+(?:(?:the|your)\s+)?"
        r"(?:refund|order|cancellation|subscription|payment|charge|account)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:they|our team|(?:customer\s+)?support(?:\s+team)?)\s+"
        r"(?:will|can|may)\s+"
        r"(?:update|change|cancel|process|issue|approve|refund|reverse|"
        r"modify|edit|delete|remove|add|complete)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwhile\s+(?:i|we)\s+(?:transfer|connect|route|escalate)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bto\s+(?:quickly\s+|promptly\s+)?connect you with\s+"
        r"(?:the\s+|a\s+|an\s+)?(?:right\s+)?"
        r"(?:human|live|customer service|representative|agent|operator|person)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:please\s+)?(?:allow|give|bear with) me (?:a )?"
        r"(?:moment|minute)\b[^.!?\r\n]{0,60}\b"
        r"(?:transfer|connect|route|escalate)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:i|we)(?:\s+(?:will|can)|'ll)\s+make sure\b"
        r"[^.!?\r\n]{0,60}\b(?:updated|changed|cancelled|canceled|"
        r"processed|completed|corrected)\b",
        re.IGNORECASE,
    ),
)

UNSUPPORTED_COMPANY_CLAIM_PATTERNS = (
    re.compile(
        r"\bour\b[^.!?\r\n]{0,45}\b"
        r"(?:support|service|team|representatives?|agents?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bour\b[^.!?\r\n]{0,45}\b"
        r"(?:company|business|brand|organization|priority|newsletter|system|"
        r"records?|attention|customers?|policy|payment|refund|return|shipping|"
        r"delivery|billing|subscription|transaction|terms|conditions|process|"
        r"options?|methods?|goal|platform|mission|commitment|values?|"
        r"products?|services?|catalog|offerings?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwe\s+value\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:contact(?:ed|ing)?|call(?:ed|ing)?|email(?:ed|ing)?|"
        r"reach(?:ing)? out to|get(?:ting)? in touch with)\s+us\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bour\s+(?:official\s+)?"
        r"(?:website|site|app|portal|dashboard|account|profile|settings|"
        r"order history|billing|subscription|online store)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwe\s+(?:offer|accept|provide|allow|support|have)\b"
        r"[^.!?\r\n]{0,80}\b"
        r"(?:refunds?|returns?|payment methods?|payment options?|"
        r"payment modalities?|credit cards?|toll[- ]free|"
        r"shipping|delivery|warrant(?:y|ies)|guarantees?|subscriptions?|"
        r"newsletters?|business hours|store locations?|products?|services?|"
        r"catalog|offerings?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwe\s+have\b[^.!?\r\n]{0,80}\b"
        r"(?:options?|choices?|a range|a selection|a catalog|solutions?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:our|the company's)\s+"
        r"(?:refund|return|shipping|delivery|cancellation|payment|warranty|"
        r"subscription|privacy)\s+polic(?:y|ies)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwe\s+(?:accept|support|offer)\b[^.!?\r\n]{0,80}\b"
        r"(?:visa|mastercard|american express|paypal|apple pay|google pay)\b",
        re.IGNORECASE,
    ),
)

UNSUPPORTED_POLICY_PATTERNS = (
    re.compile(
        r"\b\d+\s*(?:[-–]\s*)?(?:business\s+)?"
        r"(?:days?|hours?|weeks?|months?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:[$€£]\s?\d+(?:[.,]\d{1,2})?"
        r"|\b\d+(?:[.,]\d{1,2})?\s?(?:USD|EUR|GBP)\b"
        r"|\b\d{1,3}\s*%)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:our|the company's)\s+"
        r"(?:refund|return|shipping|delivery|cancellation|payment|warranty|"
        r"subscription|privacy)\s+polic(?:y|ies)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwe\s+(?:offer|have|provide)\b[^.!?\r\n]{0,80}\b"
        r"(?:refund|return|money[- ]back|warrant(?:y|ies)|guarantee)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:https?://\S+|www\.\S+|"
        r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|"
        r"(?<!\w)(?:\+?\d[\s().-]*){10,}(?!\w))",
        re.IGNORECASE,
    ),
)

SAFE_RESOURCE_PLACEHOLDERS = {
    "account recovery page url",
    "customer support email",
    "customer support hours",
    "customer support phone number",
    "forgot access key",
    "forgot password",
    "forgot pin",
    "login page url",
    "online company portal info",
    "online order interaction",
    "order tracking",
    "store location",
    "website url",
}

PLACEHOLDER_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\r?\n+")
NUMBERED_OR_BULLETED_LIST = re.compile(r"(?m)(?:^|\s)(?:\d+[.)]|[-*•])\s+")
FEATURE_REFERENCE_PATTERN = re.compile(
    r"\b(?:website|site|app|portal|dashboard|"
    r"account\s+(?:settings|page|area|history|portal|dashboard)|"
    r"profile(?:\s+page)?|order\s+(?:history|page)|purchase\s+history|"
    r"payment\s+options?|accepted\s+payment\s+methods?|"
    r"billing\s+(?:history|area|section|settings)|"
    r"subscription\s+(?:area|settings|page|portal)|payment\s+settings|"
    r"newsletter\s+(?:form|page|settings))\b",
    re.IGNORECASE,
)
ACCOUNT_ACCESS_PATTERN = re.compile(
    r"\b(?:log\s*in|sign\s*in|go to|navigate to|open|visit|access|check)\b"
    r"[^.!?]{0,80}\b(?:your|the|an)\s+account\b",
    re.IGNORECASE,
)
FEATURE_AVAILABILITY_QUALIFIER = re.compile(
    r"\b(?:if available|if provided|if offered|if it exists|if there is one|"
    r"if the (?:seller|service|company|app|website|carrier) "
    r"(?:offers|provides|has)|"
    r"if (?:your|the|an) account (?:has|includes|offers)|"
    r"if you (?:later )?(?:have|used|created) an "
    r"(?:online )?account)\b",
    re.IGNORECASE,
)
CONDITIONAL_FEATURE_QUESTION = re.compile(
    r"\b(?:check|see|find out|confirm|determine)\s+whether\b",
    re.IGNORECASE,
)
USER_PROMPT_NORMALIZATION = re.compile(r"\s+")


def normalize_user_prompt(text: str) -> str:
    return USER_PROMPT_NORMALIZATION.sub(" ", text).strip().casefold()


def contains_unsupported_action_claim(text: str) -> bool:
    return any(
        pattern.search(text)
        for pattern in UNSUPPORTED_ACTION_PATTERNS_FOR_TRAINING
    )


def unsupported_target_reason(text: str) -> str | None:
    review_text = PLACEHOLDER_FIELD_PATTERN.sub("", text)
    if contains_unsupported_action_claim(review_text):
        return "unsupported_action_claim"
    if any(pattern.search(review_text) for pattern in UNSUPPORTED_POLICY_PATTERNS):
        return "unsupported_policy_claim"
    if any(
        pattern.search(review_text)
        for pattern in UNSUPPORTED_COMPANY_CLAIM_PATTERNS
    ):
        return "unsupported_company_claim"
    for sentence in PLACEHOLDER_SENTENCE_SPLIT.split(review_text):
        if (
            (
                FEATURE_REFERENCE_PATTERN.search(sentence)
                or ACCOUNT_ACCESS_PATTERN.search(sentence)
            )
            and not FEATURE_AVAILABILITY_QUALIFIER.search(sentence)
            and not CONDITIONAL_FEATURE_QUESTION.search(sentence)
        ):
            return "unsupported_feature_assumption"
    return None


def _generic_resource_guidance(fields: set[str]) -> str:
    if fields.intersection(
        {
            "customer support email",
            "customer support hours",
            "customer support phone number",
        }
    ):
        return "Contact the company through its official support channel for current information."
    if fields.intersection(
        {
            "account recovery page url",
            "forgot access key",
            "forgot password",
            "forgot pin",
            "login page url",
        }
    ):
        return "Use the service's official account-recovery options, if available, or contact its support team."
    if "store location" in fields:
        return "Check the company's official website, if available, for current store information."
    if "order tracking" in fields:
        return "Check the carrier's official tracking page, if available."
    if fields.intersection(
        {"online company portal info", "online order interaction"}
    ):
        return "Check the seller's official order information, if available, or contact its support channel."
    return "Check the company's official website, if available, for current information."


def sanitize_completion(
    response: str,
) -> tuple[str | None, str | None, bool]:
    """Rewrite only safe resource placeholders; reject uncertain targets."""
    response = response.strip()
    if not response:
        return None, "empty_completion", False
    unsafe_reason = unsupported_target_reason(response)
    if unsafe_reason:
        return None, unsafe_reason, False

    fields = {
        field.strip().casefold()
        for field in PLACEHOLDER_FIELD_PATTERN.findall(response)
    }
    if not fields:
        return response, None, False
    if not fields.issubset(SAFE_RESOURCE_PLACEHOLDERS):
        return None, "non_resource_placeholder", False
    if NUMBERED_OR_BULLETED_LIST.search(response):
        return None, "complex_resource_placeholder", False

    parts = PLACEHOLDER_SENTENCE_SPLIT.split(response)
    placeholder_parts = [
        index
        for index, part in enumerate(parts)
        if PLACEHOLDER_PATTERN.search(part)
    ]
    if len(placeholder_parts) != 1:
        return None, "complex_resource_placeholder", False
    fields_in_sentence = {
        field.strip().casefold()
        for field in PLACEHOLDER_FIELD_PATTERN.findall(
            parts[placeholder_parts[0]]
        )
    }
    parts[placeholder_parts[0]] = _generic_resource_guidance(fields_in_sentence)
    cleaned = " ".join(part.strip() for part in parts if part.strip())

    if (
        not cleaned
        or PLACEHOLDER_PATTERN.search(cleaned)
        or unsupported_target_reason(cleaned)
    ):
        return None, "unsafe_after_rewrite", False
    return cleaned, None, True


def clean_example(
    instruction: str,
    response: str,
) -> tuple[str | None, str | None, bool]:
    instruction = instruction.strip()
    if not instruction:
        return None, "empty_instruction", False
    if PLACEHOLDER_PATTERN.search(instruction):
        return None, "prompt_placeholder", False
    cleaned, reason, rewritten = sanitize_completion(response)
    if cleaned is None:
        return None, reason, False
    return cleaned, None, rewritten


def split_by_user_prompt(
    records: list[dict[str, Any]],
    validation_fraction: float,
    seed: int,
    train_only_prompts: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1.")

    category_groups: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in records:
        messages = record.get("prompt")
        if not isinstance(messages, list) or not messages:
            raise ValueError("Each record must have a non-empty prompt.")
        final_message = messages[-1]
        if final_message.get("role") != "user":
            raise ValueError("Each prompt must end with a user message.")
        prompt = normalize_user_prompt(final_message["content"])
        category = str(record.get("category", "__all__"))
        category_groups[category][prompt].append(record)

    reserved_train_prompts = {
        normalize_user_prompt(prompt)
        for prompt in (train_only_prompts or set())
    }
    validation_prompts: set[str] = set()
    for category in sorted(category_groups):
        prompts = category_groups[category]
        category_rows = sum(
            len(records_for_prompt)
            for records_for_prompt in prompts.values()
        )
        target_validation_rows = max(
            1,
            round(category_rows * validation_fraction),
        )
        ordered_prompts = sorted(
            set(prompts).difference(reserved_train_prompts),
            key=lambda prompt: hashlib.sha256(
                f"{seed}\0{category}\0{prompt}".encode("utf-8")
            ).hexdigest(),
        )
        validation_count = sum(
            len(prompts[prompt])
            for prompt in validation_prompts.intersection(prompts)
        )
        for prompt in ordered_prompts:
            if validation_count >= target_validation_rows:
                break
            if prompt not in validation_prompts:
                validation_prompts.add(prompt)
                validation_count += len(prompts[prompt])

    train = [
        record
        for record in records
        if normalize_user_prompt(record["prompt"][-1]["content"])
        not in validation_prompts
    ]
    validation = [
        record
        for record in records
        if normalize_user_prompt(record["prompt"][-1]["content"])
        in validation_prompts
    ]
    if not train or not validation:
        raise ValueError("The grouped split must produce non-empty train/validation sets.")

    train_prompts = {
        normalize_user_prompt(record["prompt"][-1]["content"])
        for record in train
    }
    validation_prompts_actual = {
        normalize_user_prompt(record["prompt"][-1]["content"])
        for record in validation
    }
    if train_prompts & validation_prompts_actual:
        raise RuntimeError("Identical user prompts crossed the data split.")
    return train, validation


def oversample_training_categories(
    records: list[dict[str, Any]],
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Moderately boost rare categories without removing any training rows."""
    category_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        category_records[str(record.get("category", "__all__"))].append(record)
    if not category_records:
        raise ValueError("Cannot balance an empty training dataset.")

    largest_category = max(len(items) for items in category_records.values())
    rng = random.Random(seed)
    balanced = list(records)
    added_by_category: dict[str, int] = {}
    for category in sorted(category_records):
        items = category_records[category]
        target_count = math.ceil(math.sqrt(len(items) * largest_category))
        additions = target_count - len(items)
        if additions > 0:
            balanced.extend(rng.choices(items, k=additions))
            added_by_category[category] = additions
    return balanced, added_by_category


def validate_training_jsonl(path: Path) -> int:
    """Fail closed if a candidate training file contains unsafe targets."""
    count = 0
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{line_number}: invalid JSON: {exc}"
                ) from exc

            prompt = record.get("prompt")
            completion = record.get("completion")
            if (
                not isinstance(prompt, list)
                or not prompt
                or prompt[-1].get("role") != "user"
                or not isinstance(prompt[-1].get("content"), str)
            ):
                raise ValueError(
                    f"{path}:{line_number}: prompt must end with a user message"
                )
            if PLACEHOLDER_PATTERN.search(prompt[-1]["content"]):
                raise ValueError(
                    f"{path}:{line_number}: user prompt contains a placeholder"
                )
            if (
                not isinstance(completion, list)
                or not completion
                or completion[0].get("role") != "assistant"
                or not isinstance(completion[0].get("content"), str)
            ):
                raise ValueError(
                    f"{path}:{line_number}: completion must contain assistant text"
                )
            target = completion[0]["content"]
            if PLACEHOLDER_PATTERN.search(target):
                raise ValueError(
                    f"{path}:{line_number}: assistant target contains a placeholder"
                )
            unsafe_reason = unsupported_target_reason(target)
            if unsafe_reason:
                raise ValueError(
                    f"{path}:{line_number}: assistant target contains "
                    f"{unsafe_reason}"
                )
            count += 1

    if not count:
        raise ValueError(f"Training file is empty: {path}")
    return count
