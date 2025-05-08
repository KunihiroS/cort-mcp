import requests
import json
from typing import List, Dict, Any, Optional

class EnhancedRecursiveThinkingChat:
    def __init__(self, api_key: str, model: str, provider: str = "openai"):
        self.api_key = api_key
        self.model = model
        self.provider = provider
        if provider == "openai":
            self.base_url = "https://api.openai.com/v1/chat/completions"
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        else:
            self.base_url = "https://openrouter.ai/api/v1/chat/completions"
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "Recursive Thinking Chat",
                "Content-Type": "application/json"
            }
        self.conversation_history = []

    def _call_api(self, messages: List[Dict], temperature: float = 0.7, stream: bool = False) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if self.provider != "openai":
            payload["reasoning"] = {"max_tokens": 10386}
        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            return f"Error: Could not get response from API: {e}"

    def think(self, prompt: str, rounds: Optional[int] = None, num_alternatives: int = 3, details: bool = False) -> Dict[str, Any]:
        thinking_history = []
        self.conversation_history.append({"role": "user", "content": prompt})
        messages = self.conversation_history.copy()
        # ベースプロンプト・レスポンス記録
        base_llm_prompt = messages[-1]["content"] if messages else prompt
        base_response = self._call_api(messages, temperature=0.7, stream=False)
        current_best = base_response
        thinking_rounds = rounds if rounds is not None else 3
        # ベース応答も履歴に記録（round=0とする）
        thinking_history.append({
            "round": 0,
            "llm_prompt": base_llm_prompt,
            "llm_response": base_response,
            "response": base_response,
            "alternatives": [],
            "selected": -1,
            "explanation": "Initial base response"
        })
        for r in range(thinking_rounds):
            alternatives = []
            alt_prompts = []
            alt_llm_prompts = []
            alt_llm_responses = []
            for i in range(num_alternatives):
                alt_prompt = f"""Original message: {prompt}\n\nCurrent response: {current_best}\n\nGenerate an alternative response that might be better. Be creative and consider different approaches.\nAlternative response:"""
                alt_messages = self.conversation_history + [{"role": "user", "content": alt_prompt}]
                alternative = self._call_api(alt_messages, temperature=0.7 + i * 0.1, stream=False)
                alternatives.append(alternative)
                alt_prompts.append(alt_prompt)
                alt_llm_prompts.append(alt_prompt)
                alt_llm_responses.append(alternative)
            eval_prompt = f"""Original message: {prompt}\n\nEvaluate these responses and choose the best one:\n\nCurrent best: {current_best}\n\nAlternatives:\n{chr(10).join([f"{i+1}. {alt}" for i, alt in enumerate(alternatives)])}\n\nWhich response best addresses the original message? Consider accuracy, clarity, and completeness.\nFirst, respond with ONLY 'current' or a number (1-{len(alternatives)}).\nThen on a new line, explain your choice in one sentence."""
            eval_messages = [{"role": "user", "content": eval_prompt}]
            evaluation = self._call_api(eval_messages, temperature=0.2, stream=False)
            selection, *explanation = evaluation.split("\n", 1)
            explanation = explanation[0] if explanation else ""
            if selection.strip().lower() == "current":
                selected_response = current_best
                selected_idx = -1
            else:
                try:
                    idx = int(selection.strip()) - 1
                    selected_response = alternatives[idx]
                    selected_idx = idx
                except Exception:
                    selected_response = current_best
                    selected_idx = -1
            thinking_history.append({
                "round": r + 1,
                "llm_prompt": alt_llm_prompts,
                "llm_response": alt_llm_responses,
                "response": selected_response,
                "alternatives": alternatives,
                "selected": selected_idx,
                "explanation": explanation
            })
            current_best = selected_response
        self.conversation_history.append({"role": "assistant", "content": current_best})
        result = {
            "response": current_best
        }
        if details:
            result["thinking_rounds"] = thinking_rounds
            result["thinking_history"] = thinking_history
        return result
