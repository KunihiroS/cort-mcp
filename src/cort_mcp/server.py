import sys
import os
import argparse
import yaml
import json
import logging as py_logging
from typing import Annotated
from pydantic import Field

# ロギング初期化
py_logging.basicConfig(level=py_logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 相対インポートをサポート
try:
    from .recursive_thinking_ai import EnhancedRecursiveThinkingChat
    py_logging.debug("Imported EnhancedRecursiveThinkingChat via relative import")
except ImportError as e:
    py_logging.debug(f"Relative import failed: {e}, trying absolute import")
    try:
        # 直接実行された場合
        from cort_mcp.recursive_thinking_ai import EnhancedRecursiveThinkingChat
        py_logging.debug("Imported EnhancedRecursiveThinkingChat via absolute import")
    except ImportError as e2:
        py_logging.debug(f"Absolute import failed: {e2}, trying sys.path modification")
        # 開発モードで実行された場合
        src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        py_logging.debug(f"Adding path to sys.path: {src_path}")
        sys.path.append(src_path)
        try:
            from recursive_thinking_ai import EnhancedRecursiveThinkingChat
            py_logging.debug("Imported EnhancedRecursiveThinkingChat via sys.path modification")
        except ImportError as e3:
            py_logging.error(f"All import attempts failed: {e3}")
            raise

# MCPサーバーライブラリのインポート
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

# デフォルト値を定数として定義
DEFAULT_MODEL = "gpt-4.1-nano"
DEFAULT_PROVIDER = "openai"

# --- Logging Setup ---
def setup_logging(log: str, logfile: str):
    import logging
    import sys
    import os
    if log == "on":
        if not logfile or not logfile.startswith("/"):
            print("[FATAL] --logfile must be an absolute path when --log=on", file=sys.stderr)
            sys.exit(1)
        log_dir = os.path.dirname(logfile)
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception as e:
                print(f"[FATAL] Failed to create log directory: {log_dir} error={e}", file=sys.stderr)
                sys.exit(1)
        try:
            # --- Full handler initialization ---
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            root_logger.handlers.clear()
            root_logger.setLevel(logging.DEBUG)

            # Add only FileHandler to root logger
            file_handler = logging.FileHandler(logfile, mode="a", encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            # Also add StreamHandler (stdout)
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setLevel(logging.DEBUG)
            stream_handler.setFormatter(formatter)
            root_logger.addHandler(stream_handler)

            # Explicitly call flush
            file_handler.flush()

            # Set global logger as well
            specific_logger = logging.getLogger("cort-mcp-server")
            specific_logger.handlers.clear()  # Clear existing handlers
            specific_logger.setLevel(logging.DEBUG)
            specific_logger.addHandler(file_handler)
            specific_logger.addHandler(stream_handler)
            specific_logger.propagate = False

            specific_logger.debug(f"=== MCP Server log initialized: {logfile} ===")
            print(f"[INFO] MCP Server log initialized: {logfile}")
            if os.path.exists(logfile):
                print(f"[INFO] Log file created: {logfile}")
            else:
                print(f"[WARN] Log file NOT created: {logfile}")

            return specific_logger
        except Exception as e:
            print(f"[FATAL] Failed to create log file: {logfile} error={e}", file=sys.stderr)
            sys.exit(1)
    elif log == "off":
        # Completely disable logging functionality
        logging.disable(logging.CRITICAL)
        print("[INFO] Logging disabled (--log=off)")
        return None
    else:
        print("[FATAL] --log must be 'on' or 'off'", file=sys.stderr)
        sys.exit(1)

def resolve_model_and_provider(params):
    # params: dict
    model = params.get("model")
    provider = params.get("provider")
    if not model:
        model = DEFAULT_MODEL
    if not provider:
        provider = DEFAULT_PROVIDER
    # ここでAPIキー存在チェック（providerが不正/未設定含む）
    api_key = get_api_key(provider)
    if not api_key:
        # providerが不正、APIキー無し→デフォルトにフォールバック
        provider = DEFAULT_PROVIDER
        model = DEFAULT_MODEL
        api_key = get_api_key(provider)
    # さらに「モデル名がproviderに存在しない」等のチェックはAI側APIで例外発生時に検知
    return model, provider, api_key

def get_api_key(provider):
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
    elif provider == "openrouter":
        key = os.getenv("OPENROUTER_API_KEY")
    else:
        key = None
    return key

# FastMCPのインスタンスを作成
server = FastMCP(
    name="Chain-of-Recursive-Thoughts MCP Server",
    instructions="Provide deeper recursive thinking and reasoning for the given prompt. Use the MCP Server when you encounter complex problems.",
)

# ツール定義はデコレータで行う
@server.tool(
    name="cort.think.simple",
    description="""
    シンプルな再帰的思考AI応答を返すMCPツール。

    機能:
        指定されたプロンプトに対して、再帰的思考AIの応答（最終回答のみ）を返します。

    パラメータ:
        prompt (str, 必須): AIへの入力プロンプト。
        model (str, 任意): 利用するモデル名（例: "gpt-4.1-nano", "qwen/qwen3-235b-a22b:free" など）。未指定の場合はデフォルトモデルを利用。
        provider (str, 任意): "openai" または "openrouter"。未指定の場合はデフォルトプロバイダーを利用。

    戻り値:
        dict: {
            "response": AIの応答（string）,
            "model": 実際に使用されたモデル名（string）,
            "provider": 実際に使用されたプロバイダー名（string）
        }

    注意:
        - オプションパラメータ（model, provider）は未指定時はパラメータごと省略してください。
        - 明示的にnullや空文字を渡すとAPI側でエラーとなる場合があります。
        - エラー時はOpenAIのデフォルトモデルで自動フォールバックします。
    """
)
async def cort_think_simple(
    prompt: Annotated[str, Field(description="AIへの入力プロンプト（必須）")],
    model: Annotated[str | None, Field(description="利用するモデル名（例: 'gpt-4.1-nano', 'qwen/qwen3-235b-a22b:free' など）。省略時はデフォルトモデルを利用")]=None,
    provider: Annotated[str | None, Field(description="APIプロバイダー（'openai' または 'openrouter'）。省略時はデフォルトプロバイダーを利用")]=None
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
            "response": result["response"],
            "model": resolved_model,
            "provider": resolved_provider
        }
    except Exception as e:
        py_logging.exception(f"[ERROR] cort_think_simple failed: {e}")
        fallback_api_key = get_api_key("openai")
        if fallback_api_key:
            try:
                chat = EnhancedRecursiveThinkingChat(api_key=fallback_api_key, model=DEFAULT_MODEL, provider="openai")
                result = chat.think(prompt, details=False)
                py_logging.info("cort_think_simple: fallback result generated successfully")
                return {
                    "response": result["response"],
                    "model": DEFAULT_MODEL,
                    "provider": "openai (fallback)"
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
    name="cort.think.details",
    description="""
    思考過程の詳細も含めて返す再帰的思考AIツール。

    機能:
        指定されたプロンプトに対し、再帰的思考AIの応答と、思考履歴や過程（YAML形式）を返します。

    パラメータ:
        prompt (str, 必須): AIへの入力プロンプト。
        model (str, 任意): 利用するモデル名。未指定時はデフォルトモデル。
        provider (str, 任意): "openai" または "openrouter"。未指定時はデフォルトプロバイダー。

    戻り値:
        dict: {
            "response": AIの応答（string）,
            "details": 思考履歴や過程（YAML形式のstring）,
            "model": 実際に使用されたモデル名（string）,
            "provider": 実際に使用されたプロバイダー名（string）
        }

    注意:
        - オプションパラメータ（model, provider）は未指定時はパラメータごと省略してください。
        - 明示的にnullや空文字を渡すとAPI側でエラーとなる場合があります。
        - エラー時はOpenAIのデフォルトモデルで自動フォールバックします。
    """
)
async def cort_think_details(
    prompt: Annotated[str, Field(description="AIへの入力プロンプト（必須）")],
    model: Annotated[str | None, Field(description="利用するモデル名。省略時はデフォルトモデル")]=None,
    provider: Annotated[str | None, Field(description="APIプロバイダー（'openai' または 'openrouter'）。省略時はデフォルトプロバイダー")]=None
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
        fallback_api_key = get_api_key("openai")
        if fallback_api_key:
            try:
                chat = EnhancedRecursiveThinkingChat(api_key=fallback_api_key, model=DEFAULT_MODEL, provider="openai")
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
                    "provider": "openai (fallback)"
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

# ツールはデコレータで登録済み

def initialize_and_run_server():
    """MCPサーバーを初期化して実行する関数"""
    import logging as py_logging
    py_logging.info("cort-mcp server starting...")
    # MCPサーバーを実行
    server.run()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Chain-of-Recursive-Thoughts MCP Server/CLI")
    parser.add_argument("--log", choices=["on", "off"], required=True, help="Enable or disable logging (on/off)")
    parser.add_argument("--logfile", type=str, required=False, help="Absolute path to log file (required if --log=on)")
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--details", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--provider", default=None)
    args = parser.parse_args()
    if args.log == "on" and not args.logfile:
        print("[FATAL] --logfile is required when --log=on", file=sys.stderr)
        sys.exit(1)
    if args.log == "on" and not args.logfile.startswith("/"):
        print("[FATAL] --logfile must be an absolute path when --log=on", file=sys.stderr)
        sys.exit(1)
    logger = setup_logging(args.log, args.logfile)
    import logging as py_logging
    py_logging.info("cort-mcp main() started")
    try:
        if args.prompt:
            py_logging.info(f"CLI batch mode: prompt={args.prompt} details={args.details} model={args.model} provider={args.provider}")
            params = {}
            if args.model:
                params["model"] = args.model
            if args.provider:
                params["provider"] = args.provider
            if args.details:
                import asyncio
                result = asyncio.run(cort_think_details(args.prompt, **params))
            else:
                import asyncio
                result = asyncio.run(cort_think_simple(args.prompt, **params))
            for key, value in result.items():
                print(f"{key}: {value}")
        else:
            py_logging.info("Server mode: waiting for MCP stdio requests...")
            # FastMCPを使用してサーバーを起動
            initialize_and_run_server()
    except Exception as e:
        py_logging.exception(f"[ERROR] main() failed: {e}")
        return 1

if __name__ == "__main__":
    main()
