
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from configs.support_policy import SUPPORT_SYSTEM_PROMPT

class SupportGPT:

    SYSTEM_PROMPT = SUPPORT_SYSTEM_PROMPT


    def __init__(
        self,
        base_model_name="Qwen/Qwen2.5-0.5B-Instruct",
        adapter_path="models/adapters/support-gpt-lora/final",
    ):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        print("Loading SupportGPT tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(base_model_name)

        print("Loading base model...")
        dtype = torch.bfloat16 if self.device == "cuda" else torch.float32

        self.base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            dtype=dtype,
            device_map="auto" if self.device == "cuda" else None,
            attn_implementation="sdpa",
        )

        print("Loading trained LoRA adapter...")
        self.model = PeftModel.from_pretrained(
            self.base_model,
            adapter_path,
        )

        self.model.eval()
        self.model.config.use_cache = True

        print("SupportGPT is ready!")

    def generate_response(
        self,
        message,
        conversation_history=None,
        max_new_tokens=250,
    ):
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({
            "role": "user",
            "content": message,
        })

        inputs = self.tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )

        inputs = {
            key: value.to(self.model.device)
            for key, value in inputs.items()
        }

        with torch.inference_mode():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]

        return self.tokenizer.decode(
            new_tokens,
            skip_special_tokens=True,
        ).strip()
