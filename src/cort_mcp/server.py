import sys
import os
import argparse
import yaml
import json
import logging as py_logging
from typing import Annotated
from pydantic import Field

# Initialize logging
py_logging.basicConfig(level=py_logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Support relative imports
try:
    from .recursive_thinking_ai import EnhancedRecursiveThinkingChat
    py_logging.debug("Imported EnhancedRecursiveThinkingChat via relative import")
except ImportError as e:
    py_logging.debug(f"Relative import failed: {e}, trying absolute import")
    try:
        # When executed directly
        from cort_mcp.recursive_thinking_ai import EnhancedRecursiveThinkingChat
        py_logging.debug("Imported EnhancedRecursiveThinkingChat via absolute import")
    except ImportError as e2:
        py_logging.debug(f"Absolute import failed: {e2}, trying sys.path modification")
        # When executed in development mode
        src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        py_logging.debug(f"Adding path to sys.path: {src_path}")
        sys.path.append(src_path)
        try:
            from recursive_thinking_ai import EnhancedRecursiveThinkingChat
            py_logging.debug("Imported EnhancedRecursiveThinkingChat via sys.path modification")
        except ImportError as e3:
            py_logging.error(f"All import attempts failed: {e3}")
            raise

# Import MCP server library
try:
    from fastmcp import FastMCP
    py_logging.debug("Imported FastMCP from fastmcp package")
except ImportError as e:
    py_logging.debug(f"Import from fastmcp failed: {e}, trying mcp.server.fastmcp")
    try:
        from mcp.server.fastmcp import FastMCP
        py_logging.debug("Imported FastMCP from mcp.server.fastmcp")
    except ImportError as e2:
        py_logging.error(f"Failed to import FastMCP: {e2}")
        raise

# Define default values as constants
DEFAULT_MODEL = "mistralai/mistral-small-3.1-24b-instruct:free"
DEFAULT_PROVIDER = "openrouter"

# --- Logging Setup ---
def setup_logging(log: str, logfile: str):
    if log == "on":
        if not logfile or not logfile.startswith("/"):
            print("[FATAL] --logfile must be an absolute path when --log=on", file=sys.stderr)
            sys.exit(1)
        log_dir = os.path.dirname(logfile)
        print(f"[DEBUG] Attempting to use log directory: {log_dir}")
        if not os.path.exists(log_dir):
            print(f"[DEBUG] Log directory {log_dir} does not exist. Attempting to create.")
            try:
                os.makedirs(log_dir, exist_ok=True)
                print(f"[INFO] Successfully created log directory: {log_dir}")
            except Exception as e:
                print(f"[FATAL] Failed to create log directory: {log_dir} error={e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"[DEBUG] Log directory {log_dir} already exists.")

        try:
            print(f"[DEBUG] Attempting to initialize FileHandler with logfile: {logfile}")
            # --- Full handler initialization ---
            # Use the module-level py_logging
            root_logger = py_logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            root_logger.handlers.clear()
            root_logger.setLevel(py_logging.DEBUG)

            # Add only FileHandler to root logger
            file_handler = py_logging.FileHandler(logfile, mode="a", encoding="utf-8")
            print(f"[DEBUG] FileHandler initialized for {logfile}. Attempting to add to root_logger.")
            file_handler.setLevel(py_logging.DEBUG)
            formatter = py_logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            # Also add StreamHandler (stdout)
            stream_handler = py_logging.StreamHandler(sys.stdout)
            print(f"[DEBUG] StreamHandler initialized. Attempting to add to root_logger.")
            stream_handler.setLevel(py_logging.DEBUG)
            stream_handler.setFormatter(formatter)
            root_logger.addHandler(stream_handler)

            # Explicitly call flush
            file_handler.flush()
            print(f"[DEBUG] FileHandler flushed for {logfile}.")

            # Set global logger as well
            specific_logger = py_logging.getLogger("cort-mcp-server")
            specific_logger.handlers.clear()
            specific_logger.setLevel(py_logging.DEBUG)
            specific_logger.addHandler(file_handler)
            specific_logger.addHandler(stream_handler)
            specific_logger.propagate = False
            print(f"[DEBUG] Specific logger 'cort-mcp-server' configured.")

            specific_logger.debug(f"=== MCP Server log initialized: {logfile} ===")
            print(f"[INFO] MCP Server log initialized (print): {logfile}") # 明示的にprint
            if os.path.exists(logfile):
                print(f"[INFO] Log file {logfile} exists and is writable after FileHandler setup (print).")
                specific_logger.info(f"Log file {logfile} exists and is writable after FileHandler setup.") # ロガー経由でも出力
            else:
                print(f"[WARNING] Log file {logfile} was NOT created by FileHandler (check permissions or other issues) (print).")
                specific_logger.warning(f"Log file {logfile} was NOT created by FileHandler (check permissions or other issues).")


            return specific_logger
        except Exception as e:
            print(f"[FATAL] Failed to create log file or setup handler: {logfile} error={e}", file=sys.stderr)
            sys.exit(1)
    elif log == "off":
        # Completely disable logging functionality
        py_logging.disable(py_logging.CRITICAL)
        print("[INFO] Logging disabled (--log=off)")
        return None
    else:
        print("[FATAL] --log must be 'on' or 'off'", file=sys.stderr)
        sys.exit(1)

def resolve_model_and_provider(params):
    print("=== resolve_model_and_provider called ===")
    py_logging.info("=== resolve_model_and_provider called ===")
    import os
    # Use existing py_logging (already imported as py_logging)
    # Debug: Output environment variable status
    def mask_key(key):
        if key:
            return 'SET'
        return 'NOT_SET'
    py_logging.info(f"[DEBUG] ENV OPENROUTER_API_KEY={mask_key(os.getenv('OPENROUTER_API_KEY'))}")
    py_logging.info(f"[DEBUG] ENV OPENAI_API_KEY={mask_key(os.getenv('OPENAI_API_KEY'))}")
    # params: dict
    model = params.get("model")
    provider = params.get("provider")
    py_logging.info(f"[DEBUG] params: model={model}, provider={provider}")
    if not model:
        model = DEFAULT_MODEL
    if not provider:
        provider = DEFAULT_PROVIDER
    py_logging.info(f"[DEBUG] after default: model={model}, provider={provider}")
    # Check API key existence here (including invalid/unset provider)
    api_key = get_api_key(provider)
    py_logging.info(f"[DEBUG] get_api_key(provider={provider}) -> {mask_key(api_key)}")
    if not api_key:
        # Invalid provider or no API key -> fallback to default
        provider = DEFAULT_PROVIDER
        model = DEFAULT_MODEL
        api_key = get_api_key(provider)
        py_logging.info(f"[DEBUG] fallback: model={model}, provider={provider}, api_key={mask_key(api_key)}")
    # Additional checks like "model not existing in provider" are detected by exceptions in AI-side API
    return model, provider, api_key

def get_api_key(provider):
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
    elif provider == "openrouter":
        key = os.getenv("OPENROUTER_API_KEY")
    else:
        key = None
    return key

# Create FastMCP instance
server = FastMCP(
    name="Chain-of-Recursive-Thoughts MCP Server",
    instructions="Provide deeper recursive thinking and reasoning for the given prompt. Use the MCP Server when you encounter complex problems.",
)

# Define tools using decorators
@server.tool(
    name="cort.think.simple",
    description="""
    Return a simple recursive thinking AI response.

    Parameters:
        prompt (str, required): Input prompt for the AI.
        model (str, optional): LLM model name. If not specified, uses default.
        provider (str, optional): API provider name. If not specified, uses default.

    Returns:
        dict: {
            "response": AI response (string),
            "model": model name used (string),
            "provider": provider name used (string)
        }

    Notes:
        - If model/provider is omitted, defaults are used.
        - Do not pass null or empty string for optional params.
        - See README for fallback logic on API errors.
    """
)
async def cort_think_simple(
    prompt: Annotated[str, Field(description="Input prompt for the AI (required)")],
    model: Annotated[str | None, Field(description="LLM model name. If not specified, uses default.")]=None,
    provider: Annotated[str | None, Field(description="API provider name. If not specified, uses default.")]=None
):
    resolved_model, resolved_provider, api_key = resolve_model_and_provider({"model": model, "provider": provider})
    py_logging.info(f"cort_think_simple called: prompt={prompt} model={resolved_model} provider={resolved_provider}")
    if not prompt:
        py_logging.warning("cort_think_simple: prompt is required")
        return {
            "error": "prompt is required"
        }
    try:
        chat = EnhancedRecursiveThinkingChat(api_key=api_key, model=resolved_model, provider=resolved_provider)
        result = chat.think(prompt, details=False)
        py_logging.info("cort_think_simple: result generated successfully")
        return {
            "response": result.get("response"),
            "model": result.get("model"),
            "provider": result.get("provider")
        }
    except Exception as e:
        py_logging.exception(f"[ERROR] cort_think_simple failed: {e}")
        fallback_api_key = get_api_key(DEFAULT_PROVIDER)
        if fallback_api_key:
            try:
                chat = EnhancedRecursiveThinkingChat(api_key=fallback_api_key, model=DEFAULT_MODEL, provider=DEFAULT_PROVIDER)
                result = chat.think(prompt, details=False)
                py_logging.info("cort_think_simple: fallback result generated successfully")
                return {
                    "response": result.get("response"),
                    "model": result.get("model"),
                    "provider": result.get("provider")
                }
            except Exception as e2:
                py_logging.exception(f"[ERROR] cort_think_simple fallback also failed: {e2}")
                return {
                    "error": f"Failed to process request: {str(e)}. Fallback also failed: {str(e2)}"
                }
        else:
            py_logging.error("cort_think_simple: API key for OpenAI is missing (cannot fallback)")
            return {
                "error": f"Failed to process request: {str(e)}. API key for OpenAI is missing (cannot fallback)"
            }

@server.tool(
    name="cort.think.simple.neweval",
    description="""
    Return a simple recursive thinking AI response (new evaluation prompt version).

    Parameters:
        prompt (str, required): Input prompt for the AI.
        model (str, optional): LLM model name. If not specified, uses default.
        provider (str, optional): API provider name. If not specified, uses default.

    Returns:
        dict: {
            "response": AI response (string),
            "model": model name used (string),
            "provider": provider name used (string)
        }

    Notes:
        - If model/provider is omitted, defaults are used.
        - Do not pass null or empty string for optional params.
        - See README for fallback logic on API errors.
    """
)
async def cort_think_simple_neweval(
    prompt: Annotated[str, Field(description="Input prompt for the AI (required)")],
    model: Annotated[str | None, Field(description="LLM model name. If not specified, uses default.")]=None,
    provider: Annotated[str | None, Field(description="API provider name. If not specified, uses default.")]=None
):
    resolved_model, resolved_provider, api_key = resolve_model_and_provider({"model": model, "provider": provider})
    py_logging.info(f"cort_think_simple_neweval called: prompt={prompt} model={resolved_model} provider={resolved_provider}")
    if not prompt:
        py_logging.warning("cort_think_simple_neweval: prompt is required")
        return {
            "error": "prompt is required"
        }
    try:
        chat = EnhancedRecursiveThinkingChat(api_key=api_key, model=resolved_model, provider=resolved_provider)
        result = chat.think(prompt, details=False, neweval=True)
        py_logging.info("cort_think_simple_neweval: result generated successfully")
        return {
            "response": result.get("response"),
            "model": result.get("model"),
            "provider": result.get("provider")
        }
    except Exception as e:
        py_logging.exception(f"[ERROR] cort_think_simple_neweval failed: {e}")
        fallback_api_key = get_api_key(DEFAULT_PROVIDER)
        if fallback_api_key:
            try:
                chat = EnhancedRecursiveThinkingChat(api_key=fallback_api_key, model=DEFAULT_MODEL, provider=DEFAULT_PROVIDER)
                result = chat.think(prompt, details=False, neweval=True)
                py_logging.info("cort_think_simple_neweval: fallback result generated successfully")
                return {
                    "response": result["response"],
                    "model": DEFAULT_MODEL,
                    "provider": f"{DEFAULT_PROVIDER} (fallback)"
                }
            except Exception as e2:
                py_logging.exception(f"[ERROR] cort_think_simple_neweval fallback also failed: {e2}")
                return {
                    "error": f"Failed to process request: {str(e)}. Fallback also failed: {str(e2)}"
                }
        else:
            py_logging.error("cort_think_simple_neweval: API key for OpenAI is missing (cannot fallback)")
            return {
                "error": f"Failed to process request: {str(e)}. API key for OpenAI is missing (cannot fallback)"
            }

@server.tool(
    name="cort.think.details",
    description="""
    Returns a recursive thinking AI response with full reasoning details.

    Parameters:
        prompt (str, required): Input prompt for the AI.
        model (str, optional): LLM model name. If not specified, the default model is used.
        provider (str, optional): API provider name. If not specified, the default provider is used.

    Returns:
        dict: {
            "response": Final AI response (string),
            "details": Reasoning process history (YAML string),
            "model": Model name used (string),
            "provider": Provider name used (string)
        }

    Notes:
        - If model/provider is omitted, defaults are applied automatically.
        - On exceptions, fallback logic is applied.
        - Reasoning history is included in the 'details' key as YAML.
    """
)
async def cort_think_details(
    prompt: Annotated[str, Field(description="Input prompt for the AI (required)")],
    model: Annotated[str | None, Field(description="LLM model name to use.\n- Recommended (OpenAI): 'gpt-4.1-nano'\n- Recommended (OpenRouter): 'meta-llama/llama-4-maverick:free'\n- Default: mistralai/mistral-small-3.1-24b-instruct:free\nRefer to the official provider list for available models. If not specified, the default model will be used automatically.")]=None,
    provider: Annotated[str | None, Field(description="API provider name to use.\n- Allowed: 'openai' or 'openrouter'\n- Default: openrouter\nModel availability depends on the provider. Please ensure the correct combination. If not specified, the default provider will be used automatically.")]=None
):
    resolved_model, resolved_provider, api_key = resolve_model_and_provider({"model": model, "provider": provider})
    py_logging.info(f"cort_think_details called: prompt={prompt} model={resolved_model} provider={resolved_provider}")
    if not prompt:
        py_logging.warning("cort_think_details: prompt is required")
        return {
            "error": "prompt is required"
        }
    try:
        chat = EnhancedRecursiveThinkingChat(api_key=api_key, model=resolved_model, provider=resolved_provider)
        result = chat.think(prompt, details=True)
        yaml_log = yaml.safe_dump({
            "thinking_rounds": result.get("thinking_rounds"),
            "thinking_history": result.get("thinking_history")
        }, allow_unicode=True, sort_keys=False)
        py_logging.info("cort_think_details: result generated successfully")
        return {
            "response": result["response"],
            "details": yaml_log,
            "model": resolved_model,
            "provider": resolved_provider
        }
    except Exception as e:
        py_logging.exception(f"[ERROR] cort_think_details failed: {e}")
        fallback_api_key = get_api_key(DEFAULT_PROVIDER)
        if fallback_api_key:
            try:
                chat = EnhancedRecursiveThinkingChat(api_key=fallback_api_key, model=DEFAULT_MODEL, provider=DEFAULT_PROVIDER)
                result = chat.think(prompt, details=True)
                yaml_log = yaml.safe_dump({
                    "thinking_rounds": result.get("thinking_rounds"),
                    "thinking_history": result.get("thinking_history")
                }, allow_unicode=True, sort_keys=False)
                py_logging.info("cort_think_details: fallback result generated successfully")
                return {
                    "response": result["response"],
                    "details": yaml_log,
                    "model": DEFAULT_MODEL,
                    "provider": f"{DEFAULT_PROVIDER} (fallback)"
                }
            except Exception as e2:
                py_logging.exception(f"[ERROR] cort_think_details fallback also failed: {e2}")
                return {
                    "error": f"Failed to process request: {str(e)}. Fallback also failed: {str(e2)}"
                }
        else:
            py_logging.error("cort_think_details: API key for OpenAI is missing (cannot fallback)")
            return {
                "error": f"Failed to process request: {str(e)}. API key for OpenAI is missing (cannot fallback)"
            }

@server.tool(
    name="cort.think.details.neweval",
    description="""
    Returns a recursive thinking AI response with full reasoning details (new evaluation prompt version).

    Features:
        - Provides a recursive thinking AI response and the reasoning process/history (YAML format) for the given prompt.

    Parameters:
        prompt (str, required): Input prompt for the AI.
        model (str, optional): LLM model name. If not specified, the default model is used.
            - Recommended (OpenAI): "gpt-4.1-nano"
            - Recommended (OpenRouter): "meta-llama/llama-4-maverick:free"
            - Default: mistralai/mistral-small-3.1-24b-instruct:free
            - Please refer to the official provider list for available models.
        provider (str, optional): API provider name. If not specified, the default provider is used.
            - Allowed: "openai" or "openrouter"
            - Default: openrouter
            - Model availability depends on the provider. Please ensure the correct combination.

    Returns:
        dict: {
            "response": AI response (string),
            "details": Reasoning process/history (YAML string),
            "model": Model name used (string),
            "provider": Provider name used (string)
        }

    Notes:
        - If model/provider is omitted, omit the parameter entirely.
        - Passing null or empty string may cause API errors.
        - For fallback behavior on API errors, see the "Parameter Specification and Fallback Handling" section in README.md.
    """
)
async def cort_think_details_neweval(
    prompt: Annotated[str, Field(description="Input prompt for the AI (required)")],
    model: Annotated[str | None, Field(description="LLM model name to use.\n- Recommended (OpenAI): 'gpt-4.1-nano'\n- Recommended (OpenRouter): 'meta-llama/llama-4-maverick:free'\n- Default: mistralai/mistral-small-3.1-24b-instruct:free\nRefer to the official provider list for available models. If not specified, the default model will be used automatically.")]=None,
    provider: Annotated[str | None, Field(description="API provider name to use.\n- Allowed: 'openai' or 'openrouter'\n- Default: openrouter\nModel availability depends on the provider. Please ensure the correct combination. If not specified, the default provider will be used automatically.")]=None
):
    resolved_model, resolved_provider, api_key = resolve_model_and_provider({"model": model, "provider": provider})
    py_logging.info(f"cort_think_details_neweval called: prompt={prompt} model={resolved_model} provider={resolved_provider}")
    if not prompt:
        py_logging.warning("cort_think_details_neweval: prompt is required")
        return {
            "error": "prompt is required"
        }
    try:
        chat = EnhancedRecursiveThinkingChat(api_key=api_key, model=resolved_model, provider=resolved_provider)
        result = chat.think(prompt, details=True, neweval=True)
        yaml_log = yaml.safe_dump({
            "thinking_rounds": result.get("thinking_rounds"),
            "thinking_history": result.get("thinking_history")
        }, allow_unicode=True, sort_keys=False)
        py_logging.info("cort_think_details_neweval: result generated successfully")
        return {
            "response": result["response"],
            "details": yaml_log,
            "model": resolved_model,
            "provider": resolved_provider
        }
    except Exception as e:
        py_logging.exception(f"[ERROR] cort_think_details_neweval failed: {e}")
        fallback_api_key = get_api_key(DEFAULT_PROVIDER)
        if fallback_api_key:
            try:
                chat = EnhancedRecursiveThinkingChat(api_key=fallback_api_key, model=DEFAULT_MODEL, provider=DEFAULT_PROVIDER)
                result = chat.think(prompt, details=True)
                yaml_log = yaml.safe_dump({
                    "thinking_rounds": result.get("thinking_rounds"),
                    "thinking_history": result.get("thinking_history")
                }, allow_unicode=True, sort_keys=False)
                py_logging.info("cort_think_details_neweval: fallback result generated successfully")
                return {
                    "response": result["response"],
                    "details": yaml_log,
                    "model": DEFAULT_MODEL,
                    "provider": f"{DEFAULT_PROVIDER} (fallback)"
                }
            except Exception as e2:
                py_logging.exception(f"[ERROR] cort_think_details_neweval fallback also failed: {e2}")
                return {
                    "error": f"Failed to process request: {str(e)}. Fallback also failed: {str(e2)}"
                }
        else:
            py_logging.error("cort_think_details_neweval: API key for OpenAI is missing (cannot fallback)")
            return {
                "error": f"Failed to process request: {str(e)}. API key for OpenAI is missing (cannot fallback)"
            }

# --- Mixed LLM List Definition ---
MIXED_LLM_LIST = [
    {"provider": "openai", "model": "gpt-4.1-nano"},
    {"provider": "openai", "model": "gpt-4o-mini"},
    {"provider": "openrouter", "model": "meta-llama/llama-4-scout:free"},
    {"provider": "openrouter", "model": "google/gemini-2.0-flash-exp:free"},
    {"provider": "openrouter", "model": "mistralai/mistral-small-3.1-24b-instruct:free"},
    {"provider": "openrouter", "model": "meta-llama/llama-3.2-3b-instruct:free"},
]

def get_available_mixed_llms():
    """Return only LLMs with valid API keys"""
    available = []
    for entry in MIXED_LLM_LIST:
        api_key = get_api_key(entry["provider"])
        if api_key:
            available.append({**entry, "api_key": api_key})
    return available

import random
from typing import Dict, Any

def generate_with_mixed_llm(prompt: str, details: bool = False, neweval: bool = False) -> Dict[str, Any]:
    available_llms = get_available_mixed_llms()
    if not prompt:
        py_logging.warning("mixed_llm: prompt is required")
        return {"error": "prompt is required"}
    if not available_llms:
        py_logging.error("mixed_llm: No available LLMs (API key missing)")
        return {"error": "No available LLMs (API key missing)"}
 
    # --- Number of rounds and alternatives are determined by AI based on existing logic ---
    # First, randomly select a base LLM
    base_llm = random.choice(available_llms)
    chat = EnhancedRecursiveThinkingChat(api_key=base_llm["api_key"], model=base_llm["model"], provider=base_llm["provider"])
    # Generate base response (initial)
    thinking_rounds = chat._determine_thinking_rounds(prompt)
    py_logging.info("\n=== GENERATING INITIAL RESPONSE ===")
    py_logging.info(f"Base LLM: provider={base_llm['provider']}, model={base_llm['model']}, rounds={thinking_rounds}")
    base_response = chat._call_api([{"role": "user", "content": prompt}], temperature=0.7, stream=False)
    # --- base_response contains only AI response (similar to simple mode) ---
    # If API response is a dict or structure, extract only content key; otherwise, use as is
    if isinstance(base_response, dict) and "content" in base_response:
        current_best = base_response["content"]
    else:
        current_best = base_response
    py_logging.info("=" * 50)
    thinking_history = [{
        "round": 0,
        "llm_prompt": prompt,
        "llm_response": base_response,
        "response": base_response,
        "alternatives": [],
        "selected": -1,
        "explanation": "Initial base response",
        "provider": base_llm["provider"],
        "model": base_llm["model"]
    }]
    # Generate alternatives for each round
    # Use the same logic as EnhancedRecursiveThinkingChat.think (num_alternatives)
    num_alternatives = 3
    if hasattr(chat, 'num_alternatives'):
        num_alternatives = chat.num_alternatives
    for r in range(thinking_rounds):
        py_logging.info(f"\n=== ROUND {r+1}/{thinking_rounds} ===")
        alternatives = []
        alt_llm_info = []
        alt_llm_responses = []
        alt_llm_prompts = []
        for i in range(num_alternatives):
            py_logging.info(f"\n✨ ALTERNATIVE {i+1} ✨")
            alt_llm = random.choice(available_llms)
            alt_prompt = f"""Original message: {prompt}\n\nCurrent response: {current_best}\n\nGenerate an alternative response that might be better. Be creative and consider different approaches.\nAlternative response:"""
            alt_messages = [{"role": "user", "content": alt_prompt}]
            alt_chat = EnhancedRecursiveThinkingChat(api_key=alt_llm["api_key"], model=alt_llm["model"], provider=alt_llm["provider"])
            alt_response = alt_chat._call_api(alt_messages, temperature=0.7 + i * 0.1, stream=False)
            # --- alt_response also contains only AI response (similar to simple mode) ---
            if isinstance(alt_response, dict) and "content" in alt_response:
                alt_response_text = alt_response["content"]
            else:
                alt_response_text = alt_response
            py_logging.info(f"Alternative {i+1}: provider={alt_llm['provider']}, model={alt_llm['model']}")
            alternatives.append({
                "response": alt_response_text,
                "provider": alt_llm["provider"],
                "model": alt_llm["model"]
            })
            alt_llm_info.append({"provider": alt_llm["provider"], "model": alt_llm["model"]})
            alt_llm_responses.append(alt_response)
            alt_llm_prompts.append(alt_prompt)
        # Evaluation is performed by base LLM (following current CoRT practice)
        py_logging.info("\n=== EVALUATING RESPONSES ===")
        alts_text = "\n".join([f"{i+1}. {alt['response']}" for i, alt in enumerate(alternatives)])
        # Evaluation prompt is centrally managed on AI core side
        eval_prompt = chat._build_eval_prompt(prompt, current_best, [alt['response'] for alt in alternatives], neweval=neweval)
        eval_messages = [{"role": "user", "content": eval_prompt}]
        evaluation = chat._call_api(eval_messages, temperature=0.2, stream=False)
        py_logging.info("=" * 50)
 
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
            py_logging.info(f"\n    ✓ Kept current response: {explanation_text}")
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(alternatives):
                    selected_response = alternatives[idx]["response"]
                    selected_idx = idx
                    py_logging.info(f"\n    ✓ Selected alternative {idx+1}: {explanation_text}")
                else:
                    selected_response = current_best
                    selected_idx = -1
                    py_logging.info(f"\n    ✓ Invalid selection, keeping current response")
            except Exception:
                selected_response = current_best
                selected_idx = -1
                py_logging.info(f"\n    ✓ Could not parse selection, keeping current response")
        # Record the selected provider/model
        if selected_idx != -1 and 0 <= selected_idx < len(alternatives):
            sel_provider = alternatives[selected_idx]["provider"]
            sel_model = alternatives[selected_idx]["model"]
        else:
            # current_best is either base_llm or previous best
            # Pick from the last thinking_history (if not, use base_llm)
            if thinking_history:
                sel_provider = thinking_history[-1].get("provider", base_llm["provider"])
                sel_model = thinking_history[-1].get("model", base_llm["model"])
            else:
                sel_provider = base_llm["provider"]
                sel_model = base_llm["model"]
        thinking_history.append({
            "round": r + 1,
            "llm_prompt": alt_llm_prompts,
            "llm_response": alt_llm_responses,
            "response": selected_response,
            "alternatives": alternatives,
            "selected": selected_idx,
            "explanation": explanation_text,
            "alternatives_llm": alt_llm_info,
            "provider": sel_provider,
            "model": sel_model
        })
        current_best = selected_response
    py_logging.info("\n" + "=" * 50)
    py_logging.info("🎯 FINAL RESPONSE SELECTED")
    py_logging.info("=" * 50)
    result = {"response": current_best}
    # Regardless of details, always return minimal meta information
    result["thinking_rounds"] = thinking_rounds
    result["thinking_history"] = thinking_history
    # Always store the provider/model that generated the final response in best (for simple mode)
    last_provider = None
    last_model = None
    if thinking_history and isinstance(thinking_history[-1], dict):
        last_provider = thinking_history[-1].get("provider")
        last_model = thinking_history[-1].get("model")
    # Prevent null values just in case
    if not last_provider or not last_model:
        # Get from the last alternatives (if options exist)
        last_alts = thinking_history[-1].get("alternatives", [])
        if last_alts and isinstance(last_alts, list):
            last_alt = last_alts[-1]
            last_provider = last_provider or last_alt.get("provider")
            last_model = last_model or last_alt.get("model")
    # If still not found, use base_llm
    if not last_provider:
        last_provider = base_llm["provider"]
    if not last_model:
        last_model = base_llm["model"]
    result["best"] = {
        "response": current_best,
        "provider": last_provider,
        "model": last_model
    }
    if details:
        # Additional information only in details mode
        result["alternatives"] = thinking_history[-1]["alternatives"] if thinking_history else []
    return result

# --- MCP Tool Definitions ---
from typing import Annotated
from pydantic import Field

@server.tool(
    name="cort.think.simple_mixed_llm",
    description="Generate recursive thinking AI response using a different LLM (provider/model) for each alternative. No history/details output. Parameters: prompt (str, required). model/provider cannot be specified (randomly selected internally). Provider/model info for each alternative is always logged and included in the output.",
)
async def cort_think_simple_mixed_llm(
    prompt: Annotated[str, Field(description="Input prompt for the AI (required)")]
):
    result = generate_with_mixed_llm(prompt, details=False)
    # 必要な情報のみ抽出
    response = result.get("response")
    best = result.get("best")
    return {
        "response": response,
        "model": best.get("model"),
        "provider": best.get("provider")
    }

@server.tool(
    name="cort.think.simple_mixed_llm.neweval",
    description="""
    Generate recursive thinking AI response using a different LLM (provider/model) for each alternative. No history/details output. (new evaluation prompt version)

    Parameters:
        prompt (str, required): Input prompt for the AI (required).
        model/provider cannot be specified (randomly selected internally)。
        Provider/model info for each alternative is always logged and included in the output.

    Returns:
        dict: {
            "response": AI response (string),
            "provider": provider name used (string),
            "model": model name used (string)
        }
    """
)
async def cort_think_simple_mixed_llm_neweval(
    prompt: Annotated[str, Field(description="Input prompt for the AI (required)")]
):
    result = generate_with_mixed_llm(prompt, details=False, neweval=True)
    # neweval専用プロンプトで評価するために、details=False, neweval=Trueでthinkを呼び出す必要がある場合はここで明示
    response = result.get("response")
    best = result.get("best")
    return {
        "response": response,
        "model": best.get("model"),
        "provider": best.get("provider")
    }

@server.tool(
    name="cort.think.details_mixed_llm",
    description="Generate recursive thinking AI response with full history, using a different LLM (provider/model) for each alternative. Parameters: prompt (str, required). model/provider cannot be specified (randomly selected internally). Provider/model info for each alternative is always logged and included in the output and history.",
)
async def cort_think_details_mixed_llm(
    prompt: Annotated[str, Field(description="Input prompt for the AI (required)")]
):
    result = generate_with_mixed_llm(prompt, details=True)
    import yaml
    if "thinking_rounds" in result and "thinking_history" in result:
        result["details"] = yaml.safe_dump({
            "thinking_rounds": result["thinking_rounds"],
            "thinking_history": result["thinking_history"]
        }, allow_unicode=True, sort_keys=False)
    return result

@server.tool(
    name="cort.think.details_mixed_llm.neweval",
    description="""
    Generate recursive thinking AI response with full history, using a different LLM (provider/model) for each alternative. (new evaluation prompt version)

    Parameters:
        prompt (str, required): Input prompt for the AI (required).
        model/provider cannot be specified (randomly selected internally).
        Provider/model info for each alternative is always logged and included in the output and history.

    Returns:
        dict: {
            "response": AI response (string),
            "details": YAML-formatted thinking history (string),
            "thinking_rounds": int,
            "thinking_history": list,
            "best": dict, # Information about the LLM that generated the best/final response
            "alternatives": list (only when details=True) # List of alternative responses considered in the final round
        }
    """
)
async def cort_think_details_mixed_llm_neweval(
    prompt: Annotated[str, Field(description="Input prompt for the AI (required)")]
):
    result = generate_with_mixed_llm(prompt, details=True, neweval=True)
    import yaml
    if "thinking_rounds" in result and "thinking_history" in result:
        result["details"] = yaml.safe_dump({
            "thinking_rounds": result["thinking_rounds"],
            "thinking_history": result["thinking_history"]
        }, allow_unicode=True, sort_keys=False)
    return result

# Tools are registered with decorators

def initialize_and_run_server():
    # Initialize and run the MCP server.
    import logging as py_logging
    py_logging.info("cort-mcp server starting...")
    # Run the MCP server
    server.run()

def main():
    parser = argparse.ArgumentParser(description="Chain-of-Recursive-Thoughts MCP Server/CLI")
    parser.add_argument("--log", choices=["on", "off"], required=True, help="Enable or disable logging (on/off)")
    parser.add_argument("--logfile", type=str, required=False, help="Absolute path to log file (required if --log=on)")
 
    args = parser.parse_args()
    if args.log == "on" and not args.logfile:
        print("[FATAL] --logfile is required when --log=on", file=sys.stderr)
        sys.exit(1)
    if args.log == "on" and not args.logfile.startswith("/"):
        print("[FATAL] --logfile must be an absolute path when --log=on", file=sys.stderr)
        sys.exit(1)
    
    # Call setup_logging to configure logging based on arguments.
    # This function will configure the root logger and a specific logger 'cort-mcp-server'.
    # It returns the specific logger instance, or None if logging is off.
    logger = setup_logging(args.log, args.logfile)
    
    # The module-level 'py_logging' (alias for 'logging') is used by other functions.
    # 'setup_logging' has already configured the necessary handlers on the root logger
    # or the 'cort-mcp-server' logger, so other parts of the code using
    # py_logging.getLogger('cort-mcp-server') or py_logging.getLogger() will get these settings.

    if logger: # If setup_logging returned a logger instance (i.e., log was 'on')
        logger.info("cort-mcp main() started")
    elif args.log == "on": # Should not happen if setup_logging exits on error
        print("[ERROR] Logger was not configured by setup_logging despite --log=on.", file=sys.stderr)


    try:
        if logger:
            logger.info("Server mode: waiting for MCP stdio requests...")
        elif args.log == "on": # Log was on, but logger is None (error in setup_logging)
            print("[INFO] Server mode: waiting for MCP stdio requests... (logger not fully available)", file=sys.stderr)
        # Start the server using FastMCP
        initialize_and_run_server()
    except Exception as e:
        if logger:
            logger.exception(f"[ERROR] main() failed: {e}")
        else:
            # Fallback if logger is not available
            print(f"[FATAL ERROR] main() failed: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    main()
