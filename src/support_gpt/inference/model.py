
import os
from pathlib import Path

import torch
from huggingface_hub import snapshot_download
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

from configs.support_policy import SUPPORT_SYSTEM_PROMPT


class SupportGPT:
    SYSTEM_PROMPT = SUPPORT_SYSTEM_PROMPT
    MAX_NEW_TOKENS = 200

    def __init__(self, base_model_name="Qwen/Qwen2.5-0.5B-Instruct"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.adapter_source = self._resolve_adapter_source()
        token = os.getenv("HF_TOKEN") or None

        print("Loading SupportGPT tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            base_model_name,
            token=token,
        )

        print("Loading base model...")
        use_bfloat16 = (
            self.device.type == "cuda"
            and torch.cuda.is_bf16_supported()
        )
        dtype = torch.bfloat16 if use_bfloat16 else torch.float32

        self.base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            dtype=dtype,
            token=token,
            device_map="auto" if self.device.type == "cuda" else None,
        )

        print("Loading trained LoRA adapter...")
        self.model = PeftModel.from_pretrained(
            self.base_model,
            self.adapter_source,
        )

        if self.device.type == "cpu":
            self.model.to(self.device)
        self.model.eval()
        self.model.config.use_cache = True

        print("SupportGPT is ready!")

    @staticmethod
    def _resolve_adapter_source() -> str:
        local_path = os.getenv("SUPPORTGPT_ADAPTER_PATH", "").strip()
        if local_path:
            path = Path(local_path).expanduser()
            if not path.is_dir():
                raise FileNotFoundError(
                    "SUPPORTGPT_ADAPTER_PATH does not point to a directory."
                )
            return str(path)

        repo_id = os.getenv("SUPPORTGPT_ADAPTER_REPO", "").strip()
        if not repo_id:
            raise ValueError(
                "Set SUPPORTGPT_ADAPTER_PATH or SUPPORTGPT_ADAPTER_REPO "
                "to load the fine-tuned adapter."
            )

        snapshot_path = snapshot_download(
            repo_id=repo_id,
            token=os.getenv("HF_TOKEN") or None,
        )
        return str(snapshot_path)

    def generate_response(
        self,
        message,
        conversation_history=None,
        max_new_tokens=MAX_NEW_TOKENS,
    ):
        max_new_tokens = max(1, min(max_new_tokens, self.MAX_NEW_TOKENS))
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]

        if conversation_history:
            messages.extend(conversation_history[-10:])

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
