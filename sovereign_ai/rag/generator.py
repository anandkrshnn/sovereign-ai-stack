import torch
import threading
from typing import List, Dict, Optional, Generator
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

from .config import (
    DEFAULT_MODEL, 
    GEN_MAX_NEW_TOKENS, 
    GEN_TEMPERATURE, 
    GEN_TOP_P,
    DEFAULT_SYSTEM_PROMPT
)

class QwenGenerator:
    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def _load(self):
        """Lazy-load the model and tokenizer."""
        if self.model is None:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                device_map="auto",
                torch_dtype="auto",
                trust_remote_code=True
            ).eval()

    def generate(self, messages: List[Dict[str, str]]) -> str:
        """Synchronous generation."""
        self._load()
        
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)

        generated_ids = self.model.generate(
            **model_inputs,
            max_new_tokens=GEN_MAX_NEW_TOKENS,
            temperature=GEN_TEMPERATURE,
            top_p=GEN_TOP_P,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]

        return self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

    def stream_generate(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        """Streaming generation using TextIteratorStreamer."""
        self._load()

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        generation_kwargs = dict(
            **model_inputs,
            streamer=streamer,
            max_new_tokens=GEN_MAX_NEW_TOKENS,
            temperature=GEN_TEMPERATURE,
            top_p=GEN_TOP_P,
            pad_token_id=self.tokenizer.eos_token_id
        )

        # Run generation in a separate thread
        thread = threading.Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        yield from streamer
