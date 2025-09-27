import re
from typing import List, Optional, Union
import httpx

class Cerebras:
    URL = "https://api.cerebras.ai/v1/chat/completions"
    def __init__(self, api_key: str, system_prompt: str, preferred_model: Optional[str] = None):
        if not api_key:
            raise ValueError(f"Missing api key!")

        if not system_prompt:
            raise ValueError(f"System prompt is missing!")

        self.api_key = api_key.strip()
        self.prompt = system_prompt.strip()

        if preferred_model:
            self.model = preferred_model
        else:
            self.model = None

    def _create_messages(self, text: Union[str, List[str]]):
        messages = [{
            "role": "system",
            "content": self.prompt
        }]

        if not isinstance(text, list):
            text = [text]

        for message in text:
            messages.append({
                "role": "user",
                "content": message
            })

        return messages

    def get_llm_response(self, text: Union[str, List[str]], model: Optional[str] = None):
        messages = self._create_messages(text)

        model = model or self.model
        if not model:
            raise ValueError(f"Model to use is unspecified!")

        body = {
            "model": model,
            "max_tokens": 5000,
            "temperature": 0.2,
            "top_p": 0.8,
            "messages": messages,
        }

        response = httpx.post(self.URL, headers={"Authorization": f"Bearer {self.api_key}"}, json=body)
        response.raise_for_status()

        llm_response = response.json().get("choices", [])[0].get("message", {}).get("content").strip()
        return self.parse_llm_response(llm_response)

    @classmethod
    def parse_llm_response(cls, llm_response: str):
        llm_response = llm_response.strip()
        if not llm_response:
            return "", 1  # default if empty

        # Try to split into "score text"
        parts = re.split(r"\s+", llm_response, 1)

        # Case 1: "score text"
        if len(parts) == 2:
            score_candidate, rest = parts
            try:
                return rest.strip(), float(score_candidate)
            except ValueError:
                return llm_response, 1

        # Case 2: "score" only
        if len(parts) == 1:
            token = parts[0]
            try:
                return "", float(token)  # score only
            except ValueError:
                return token, 1  # text only fallback
            
        return "", 1
