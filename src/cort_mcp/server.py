import sys
import os
import argparse
import yaml
import json
import logging as py_logging

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
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_PROVIDER = "openai"

# ロギング設定
def setup_logging(log: str, logfile: str):
    # 絶対パスでログファイルを指定
    abs_logfile = "/home/kunipiro/DEV/cort-mcp/cort-mcp.log"
    
    # 起動元の情報をログに出力
    with open("/home/kunipiro/DEV/cort-mcp/startup-debug.log", "a") as f:
        import os
        import sys
        import datetime
        f.write(f"\n--- Startup at {datetime.datetime.now()} ---\n")
        f.write(f"Current directory: {os.getcwd()}\n")
        f.write(f"Python executable: {sys.executable}\n")
        f.write(f"Arguments: {sys.argv}\n")
        f.write(f"Environment: OPENAI_API_KEY={'*' * 5 if os.getenv('OPENAI_API_KEY') else 'Not set'}\n")
        f.write(f"Environment: OPENROUTER_API_KEY={'*' * 5 if os.getenv('OPENROUTER_API_KEY') else 'Not set'}\n")
    
    # ログディレクトリが存在しない場合は作成
    log_dir = os.path.dirname(abs_logfile)
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            import logging as py_logging
            py_logging.basicConfig(level=py_logging.DEBUG)
            py_logging.exception(f"[FATAL] Failed to create log directory: {log_dir} error={e}")
            print(f"[FATAL] Failed to create log directory: {log_dir} error={e}", file=sys.stderr)
            sys.exit(1)
    try:
        import logging as py_logging
        # ログレベルをDEBUGに設定し、フォーマットを詳細にする
        py_logging.basicConfig(
            level=py_logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler = py_logging.FileHandler(abs_logfile, mode="a", encoding="utf-8")
        file_handler.setLevel(py_logging.DEBUG)
        formatter = py_logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        py_logging.getLogger().addHandler(file_handler)
        
        # MCPライブラリのロガーもDEBUGレベルに設定
        py_logging.getLogger('mcp').setLevel(py_logging.DEBUG)
    except Exception as e:
        import logging as py_logging
        py_logging.basicConfig(level=py_logging.DEBUG)
        py_logging.exception(f"[FATAL] Failed to open logfile: {abs_logfile} error={e}")
        print(f"[FATAL] Failed to open logfile: {abs_logfile} error={e}", file=sys.stderr)
        sys.exit(1)
    # --- 以前の絶対パスチェック・ディレクトリ生成・FileHandler部分はコメントアウトで残す ---
    # if log == "on":
    #     if not logfile or not logfile.startswith("/"):
    #         print("[FATAL] --logfile must be an absolute path when --log=on", file=sys.stderr)
    #         sys.exit(1)
    #     log_dir = os.path.dirname(logfile)
    #     if not os.path.exists(log_dir):
    #         try:
    #             os.makedirs(log_dir, exist_ok=True)
    #         except Exception as e:
    #             print(f"[FATAL] Failed to create log directory: {log_dir} error={e}", file=sys.stderr)
    #             sys.exit(1)
    #     try:
    #         file_handler = logging.FileHandler(logfile, mode="a", encoding="utf-8")
    #         file_handler.setLevel(logging.DEBUG)
    #         import logging as py_logging
    #         py_logging.getLogger().addHandler(file_handler)
    #     except Exception as e:
    #         print(f"[FATAL] Failed to open logfile: {logfile} error={e}", file=sys.stderr)
    #         sys.exit(1)

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
    'Chain-of-Recursive-Thoughts MCP Server',
    description="再帰的思考AIロジックを提供するCORT MCPサーバー"
)

# ツール定義はデコレータで行う
@server.tool(
    name="cort.think.simple",
    description="シンプルな再帰的思考AI応答を返す"
)
async def cort_think_simple(prompt: str, model: str = None, provider: str = None):
    """シンプルな再帰的思考AI応答を返す
    
    Args:
        prompt: AIへの入力プロンプト
        model: モデル名（例: "gpt-4.1-mini", "qwen/qwen3-235b-a22b:free" など）
        provider: "openai" または "openrouter"
    """
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
    description="思考過程の詳細も含めて返す再帰的思考AIツール"
)
async def cort_think_details(prompt: str, model: str = None, provider: str = None):
    """思考過程の詳細も含めて返す再帰的思考AIツール
    
    Args:
        prompt: AIへの入力プロンプト
        model: モデル名
        provider: "openai" または "openrouter"
    """
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
    setup_logging(log="on", logfile="")
    import logging as py_logging
    py_logging.info("cort-mcp server starting...")
    # MCPサーバーを実行
    server.run()

def main():
    # 必ず最初にログをセットアップ（絶対パスで固定出力）
    setup_logging(log="on", logfile="")
    import argparse
    import logging as py_logging
    py_logging.info("cort-mcp main() started")
    try:
        parser = argparse.ArgumentParser(description="Chain-of-Recursive-Thoughts MCP Server/CLI")
        parser.add_argument("--log", default="off", choices=["on", "off"])
        parser.add_argument("--logfile", default="/tmp/cort-mcp.log")
        parser.add_argument("--prompt", default=None)
        parser.add_argument("--details", action="store_true")
        parser.add_argument("--model", default=None)
        parser.add_argument("--provider", default=None)
        args = parser.parse_args()

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
