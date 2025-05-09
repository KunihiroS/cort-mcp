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
DEFAULT_MODEL = "mistralai/mistral-small-3.1-24b-instruct:free"
DEFAULT_PROVIDER = "openrouter"

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
    print("=== resolve_model_and_provider called ===")
    py_logging.info("=== resolve_model_and_provider called ===")
    import os
    # 既存のpy_logging（logging as py_loggingでimport済み）を使う
    # デバッグ: 環境変数の状態を出力
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
    # ここでAPIキー存在チェック（providerが不正/未設定含む）
    api_key = get_api_key(provider)
    py_logging.info(f"[DEBUG] get_api_key(provider={provider}) -> {mask_key(api_key)}")
    if not api_key:
        # providerが不正、APIキー無し→デフォルトにフォールバック
        provider = DEFAULT_PROVIDER
        model = DEFAULT_MODEL
        api_key = get_api_key(provider)
        py_logging.info(f"[DEBUG] fallback: model={model}, provider={provider}, api_key={mask_key(api_key)}")
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
        model (str, 任意): 利用するLLMモデル名を正確に指定してください。
    - 推奨値（OpenAIの場合）: "gpt-4.1-nano"
    - 推奨値（OpenRouterの場合）: "meta-llama/llama-4-maverick:free"
    - デフォルトモデル: gpt-4.1-mini（OpenAIプロバイダ使用時）
    モデル名は各プロバイダの公式リストに従い、正確に入力してください。指定がない場合はプロバイダごとのデフォルトモデルが利用されます。
        provider (str, 任意): 利用するAPIプロバイダ名を正確に指定してください。
    - 指定可能値: "openai" または "openrouter"
    - デフォルトプロバイダ: openai
    プロバイダによって選択可能なモデルが異なるため、モデル名とプロバイダの組み合わせにご注意ください。指定がない場合はデフォルトプロバイダが利用されます。

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
    # Annotatedは型ヒントに追加メタ情報（バリデーションや説明文など）を付与するための標準仕組みです
model: Annotated[str | None, Field(description="利用するLLMモデル名を正確に指定してください。\n- デフォルト: mistralai/mistral-small-3.1-24b-instruct:free（OpenRouterプロバイダ使用時）\n- OpenAI利用時の推奨値: 'gpt-4.1-nano'\n- OpenRouter利用時の推奨値: 'meta-llama/llama-4-maverick:free'\nモデル名は各プロバイダの公式リストに従い、正確に入力してください。指定がない場合はデフォルトモデル（OpenRouter）が利用されます。"\n- 推奨値（OpenAIの場合）: 'gpt-4.1-nano'\n- 推奨値（OpenRouterの場合）: 'meta-llama/llama-4-maverick:free'\n- デフォルトモデル: gpt-4.1-mini（OpenAIプロバイダ使用時）\nモデル名は各プロバイダの公式リストに従い、正確に入力してください。指定がない場合はプロバイダごとのデフォルトモデルが利用されます。")]=None,
    # Annotatedは型ヒントに追加メタ情報（バリデーションや説明文など）を付与するための標準仕組みです
provider: Annotated[str | None, Field(description="利用するAPIプロバイダ名を正確に指定してください。\n- デフォルト: openrouter\n- 指定可能値: 'openai' または 'openrouter'\n- OpenAIはAPIキーが無い場合の自動フォールバック先として利用されます。\nプロバイダによって選択可能なモデルが異なるため、モデル名とプロバイダの組み合わせにご注意ください。指定がない場合はデフォルトプロバイダ（openrouter）が利用されます。"\n- 指定可能値: 'openai' または 'openrouter'\n- デフォルトプロバイダ: openai\nプロバイダによって選択可能なモデルが異なるため、モデル名とプロバイダの組み合わせにご注意ください。指定がない場合はデフォルトプロバイダが利用されます。")]=None
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
        fallback_api_key = get_api_key(DEFAULT_PROVIDER)
        if fallback_api_key:
            try:
                chat = EnhancedRecursiveThinkingChat(api_key=fallback_api_key, model=DEFAULT_MODEL, provider=DEFAULT_PROVIDER)
                result = chat.think(prompt, details=False)
                py_logging.info("cort_think_simple: fallback result generated successfully")
                return {
                    "response": result["response"],
                    "model": DEFAULT_MODEL,
                    "provider": f"{DEFAULT_PROVIDER} (fallback)"
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
        model (str, 任意): 利用するLLMモデル名を正確に指定してください。
    - 推奨値（OpenAIの場合）: "gpt-4.1-nano"
    - 推奨値（OpenRouterの場合）: "meta-llama/llama-4-maverick:free"
    - デフォルトモデル: gpt-4.1-mini（OpenAIプロバイダ使用時）
    モデル名は各プロバイダの公式リストに従い、正確に入力してください。指定がない場合はプロバイダごとのデフォルトモデルが利用されます。
        provider (str, 任意): 利用するAPIプロバイダ名を正確に指定してください。
    - 指定可能値: "openai" または "openrouter"
    - デフォルトプロバイダ: openai
    プロバイダによって選択可能なモデルが異なるため、モデル名とプロバイダの組み合わせにご注意ください。指定がない場合はデフォルトプロバイダが利用されます。

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
    model: Annotated[str | None, Field(description="利用するLLMモデル名を正確に指定してください。\n- デフォルト: mistralai/mistral-small-3.1-24b-instruct:free（OpenRouterプロバイダ使用時）\n- OpenAI利用時の推奨値: 'gpt-4.1-nano'\n- OpenRouter利用時の推奨値: 'meta-llama/llama-4-maverick:free'\nモデル名は各プロバイダの公式リストに従い、正確に入力してください。指定がない場合はデフォルトモデル（OpenRouter）が利用されます。")]=None,
    provider: Annotated[str | None, Field(description="利用するAPIプロバイダ名を正確に指定してください。\n- デフォルト: openrouter\n- 指定可能値: 'openai' または 'openrouter'\n- OpenAIはAPIキーが無い場合の自動フォールバック先として利用されます。\nプロバイダによって選択可能なモデルが異なるため、モデル名とプロバイダの組み合わせにご注意ください。指定がない場合はデフォルトプロバイダ（openrouter）が利用されます。")]=None
):
    print(f"=== cort_think_details called ===")
    print(f"prompt={prompt}")
    print(f"model={model}")
    print(f"provider={provider}")
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

    args = parser.parse_args()
    if args.log == "on" and not args.logfile:
        print("[FATAL] --logfile is required when --log=on", file=sys.stderr)
        sys.exit(1)
    if args.log == "on" and not args.logfile.startswith("/"):
        print("[FATAL] --logfile must be an absolute path when --log=on", file=sys.stderr)
        sys.exit(1)
    global py_logging
    logger = setup_logging(args.log, args.logfile)
    import logging as py_logging
    py_logging = logger
    py_logging.info("cort-mcp main() started")
    try:
        py_logging.info("Server mode: waiting for MCP stdio requests...")
        # FastMCPを使用してサーバーを起動
        initialize_and_run_server()
    except Exception as e:
        py_logging.exception(f"[ERROR] main() failed: {e}")
        return 1

if __name__ == "__main__":
    main()
