
import torch

from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

ADAPTER_PATH = "models/adapters/support-gpt-lora/final"

SYSTEM_PROMPT = """
You are SupportGPT, a helpful and professional customer support assistant.

Answer customer questions clearly, politely, and accurately.
Provide practical guidance based on the information available.
Do not claim that you have accessed customer accounts, orders, or payment
systems, or that you have performed actions such as cancellations or refunds.
If a request requires access to a real company system, explain that the
customer must use the appropriate official support channel.
Preserve any placeholders in the provided support information.
""".strip()


def main():
    print("Loading tokenizer...")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    print("Loading base model...")

    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        dtype=torch.bfloat16,
        device_map={"": 0},
        attn_implementation="sdpa",
    )

    print("Loading trained SupportGPT adapter...")

    model = PeftModel.from_pretrained(
        base_model,
        ADAPTER_PATH,
    )

    model.eval()
    model.config.use_cache = True

    questions = [
        "How can I track my order?",
        "I want to cancel my order. What should I do?",
        "How long does a refund usually take?",
        "I cannot log into my account. Can you help?",
    ]

    for question in questions:
        print("\n" + "=" * 65)
        print("CUSTOMER:", question)
        print("=" * 65)

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": question,
            },
        ]

        inputs = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        ).to("cuda")

        with torch.inference_mode():
            outputs = model.generate(
                **inputs,
                max_new_tokens=250,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]

        response = tokenizer.decode(
            new_tokens,
            skip_special_tokens=True,
        )

        print("\nSUPPORTGPT:", response)


if __name__ == "__main__":
    main()
