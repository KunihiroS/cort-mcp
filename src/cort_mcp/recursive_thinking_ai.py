import requests
import json
import logging
from typing import List, Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

class EnhancedRecursiveThinkingChat:
    def __init__(self, api_key: str, model: str, provider: str = "openai"):
        """Initialize the Enhanced Recursive Thinking Chat.
        
        Args:
            api_key: The API key for the provider
            model: The model name to use
            provider: The provider to use ("openai" or "openrouter")
        """
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
        """Make an API call to the provider.
        
        Args:
            messages: The messages to send to the API
            temperature: The temperature to use
            stream: Whether to stream the response
            
        Returns:
            The response from the API
        """
        logger.debug(f"Making API call with {len(messages)} messages, temperature={temperature}")
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if self.provider != "openai":
            payload["reasoning"] = {"max_tokens": 10386}
        try:
            logger.debug(f"Sending request to {self.base_url}")
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content'].strip()
            logger.debug(f"Received response with {len(content)} characters")
            return content
        except Exception as e:
            logger.error(f"API Error: {e}")
            return f"Error: Could not get response from API: {e}"

    def _determine_thinking_rounds(self, prompt: str) -> int:
        """Let the model decide how many rounds of thinking are needed.
        
        Args:
            prompt: The user's prompt
            
        Returns:
            The number of rounds to think (between 1 and 5)
        """
        meta_prompt = f"""Given this message: "{prompt}"
        
How many rounds of iterative thinking (1-5) would be optimal to generate the best response?
Consider the complexity and nuance required.
Respond with just a number between 1 and 5."""
        
        messages = [{"role": "user", "content": meta_prompt}]
        
        logger.info("=== DETERMINING THINKING ROUNDS ===")
        response = self._call_api(messages, temperature=0.3, stream=False)
        logger.info("=" * 50)

        try:
            rounds = int(''.join(filter(str.isdigit, response)))
            logger.info(f"\n🤔 Thinking... ({rounds} rounds needed)")
            return min(max(rounds, 1), 5)  # Between 1 and 5
        except Exception as e:
            logger.warning(f"Could not determine rounds, using default: {e}")
            logger.info(f"\n🤔 Thinking... (3 rounds needed)")
            return 3  # Default to 3 rounds
        
        try:
            rounds = int(''.join(filter(str.isdigit, response)))
            return min(max(rounds, 1), 5)  # Between 1 and 5
        except Exception as e:
            logger.warning(f"Could not determine rounds, using default: {e}")
            return 3  # Default to 3 rounds
            
    def _build_eval_prompt(self, prompt, current_best, alternatives, neweval=False):
        if neweval:
            logger.info("[EVAL PROMPT] neweval=True: new eval prompt")
            return f"""Original message: {prompt}\n\nYou are an expert evaluator tasked with selecting the response that best fulfills the user's true needs, considering multiple perspectives.\n\nCurrent best: {current_best}\n\nAlternatives:\n{chr(10).join([f"{i+1}. {alt}" for i, alt in enumerate(alternatives)])}\n\nPlease follow this evaluation process:\n\n1. Intent Analysis: What is the user REALLY seeking? What underlying needs might be present beyond the surface question?\n2. Context Consideration: What possible situations or backgrounds could this question arise from?\n3. Diversity Assessment: Does the response consider different viewpoints or possible interpretations?\n4. Practicality Evaluation: How useful would the response be in the user's real-world context?\n5. Consistency Check: Is the response internally consistent and logically coherent?\n\nFor each response (including the current best):\n- Does it solve the user's TRUE problem?\n- Does it balance accuracy and usefulness?\n- Does it avoid unnecessary assumptions or biases?\n- Is it flexible enough to apply in various contexts or situations?\n- Does it account for exceptions or special cases?\n\nAfter completing your evaluation:\n1. Indicate your choice with ONLY 'current' or a number (1-{len(alternatives)}).\n2. On the next line, explain specifically why this response best meets the user's true needs.\n"""
        else:
            logger.info("[EVAL PROMPT] neweval=False: original eval prompt")
            return f"""Original message: {prompt}\n\nEvaluate these responses and choose the best one:\n\nCurrent best: {current_best}\n\nAlternatives:\n{chr(10).join([f"{i+1}. {alt}" for i, alt in enumerate(alternatives)])}\n\nWhich response best addresses the original message? Consider accuracy, clarity, and completeness.\nFirst, respond with ONLY 'current' or a number (1-{len(alternatives)}).\nThen on a new line, explain your choice in one sentence."""

    def think(self, prompt: str, rounds: Optional[int] = None, num_alternatives: int = 3, details: bool = False, neweval: bool = False) -> Dict[str, Any]:
        """Process user input with recursive thinking.
        
        Args:
            prompt: The user's prompt
            rounds: The number of thinking rounds (if None, will be determined automatically)
            num_alternatives: The number of alternative responses to generate
            details: Whether to include thinking details in the result
            
        Returns:
            A dictionary with the response and optionally thinking details
        """
        # Determine thinking rounds if not specified
        thinking_rounds = rounds if rounds is not None else self._determine_thinking_rounds(prompt)
        logger.info(f"\n\n🤔 Thinking... ({thinking_rounds} rounds needed)")
        
        thinking_history = []
        self.conversation_history.append({"role": "user", "content": prompt})
        messages = self.conversation_history.copy()
        
        # Generate initial response
        logger.info("\n=== GENERATING INITIAL RESPONSE ===")
        base_llm_prompt = messages[-1]["content"] if messages else prompt
        base_response = self._call_api(messages, temperature=0.7, stream=False)
        current_best = base_response
        logger.info("=" * 50)
        # Record the base response in the history as well (set round=0)
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
            logger.info(f"\n=== ROUND {r+1}/{thinking_rounds} ===")
            
            alternatives = []
            alt_prompts = []
            alt_llm_prompts = []
            alt_llm_responses = []
            
            # Generate alternatives
            for i in range(num_alternatives):
                logger.info(f"\n✨ ALTERNATIVE {i+1} ✨")
                alt_prompt = f"""Original message: {prompt}\n\nCurrent response: {current_best}\n\nGenerate an alternative response that might be better. Be creative and consider different approaches.\nAlternative response:"""
                alt_messages = self.conversation_history + [{"role": "user", "content": alt_prompt}]
                alternative = self._call_api(alt_messages, temperature=0.7 + i * 0.1, stream=False)
                alternatives.append(alternative)
                alt_prompts.append(alt_prompt)
                alt_llm_prompts.append(alt_prompt)
                alt_llm_responses.append(alternative)
            # Evaluate responses
            logger.info("\n=== EVALUATING RESPONSES ===")
            eval_prompt = self._build_eval_prompt(prompt, current_best, alternatives, neweval=neweval)
            eval_messages = [{"role": "user", "content": eval_prompt}]
            evaluation = self._call_api(eval_messages, temperature=0.2, stream=False)
            logger.info("=" * 50)
            # Better parsing of evaluation result
            lines = [line.strip() for line in evaluation.split('\n') if line.strip()]
            
            choice = 'current'
            explanation_text = "No explanation provided"
            
            if lines:
                first_line = lines[0].lower()
                if 'current' in first_line:
                    choice = 'current'
                else:
                    for char in first_line:
                        if char.isdigit():
                            choice = char
                            break
                
                if len(lines) > 1:
                    explanation_text = ' '.join(lines[1:])
            
            if choice == 'current':
                selected_response = current_best
                selected_idx = -1
                logger.info(f"\n    ✓ Kept current response: {explanation_text}")
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(alternatives):
                        selected_response = alternatives[idx]
                        selected_idx = idx
                        logger.info(f"\n    ✓ Selected alternative {idx+1}: {explanation_text}")
                    else:
                        selected_response = current_best
                        selected_idx = -1
                        logger.info(f"\n    ✓ Invalid selection, keeping current response")
                except Exception:
                    selected_response = current_best
                    selected_idx = -1
                    logger.info(f"\n    ✓ Could not parse selection, keeping current response")
            thinking_history.append({
                "round": r + 1,
                "llm_prompt": alt_llm_prompts,
                "llm_response": alt_llm_responses,
                "response": selected_response,
                "alternatives": alternatives,
                "selected": selected_idx,
                "explanation": explanation_text
            })
            current_best = selected_response
        # Add to conversation history
        self.conversation_history.append({"role": "assistant", "content": current_best})
        
        # Keep conversation history manageable
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
        
        logger.info("\n" + "=" * 50)
        logger.info("🎯 FINAL RESPONSE SELECTED")
        logger.info("=" * 50)
        
        result = {
            "response": current_best,
            "model": self.model,
            "provider": self.provider
        }
        if details:
            result["thinking_rounds"] = thinking_rounds
            result["thinking_history"] = thinking_history
        return result
