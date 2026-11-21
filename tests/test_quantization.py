
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)

MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"

def main():
    print("Checking CUDA...")
    assert torch.cuda.is_available(), "CUDA is unavailable"

    print("GPU:", torch.cuda.get_device_name(0))
    print("Loading tokenizer...")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    print("Configuring 4-bit NF4...")

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    print("Loading quantized model...")

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=quantization_config,
        device_map={"": 0},
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )

    print("\nModel loaded successfully!")
    print("4-bit:", model.is_quantized)
    print("Parameters:", sum(p.numel() for p in model.parameters()))
    print("GPU memory allocated:",
          round(torch.cuda.memory_allocated() / 1024**3, 2), "GB")

    messages = [
        {
            "role": "system",
            "content": "You are a helpful customer support assistant."
        },
        {
            "role": "user",
            "content": "How can I track my order?"
        }
    ]

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=100,
            do_sample=False,
        )

    generated_tokens = output[0][inputs["input_ids"].shape[1]:]
    answer = tokenizer.decode(
        generated_tokens,
        skip_special_tokens=True,
    )

    print("\nTest response:")
    print(answer)

    del model
    torch.cuda.empty_cache()

if __name__ == "__main__":
    main()
