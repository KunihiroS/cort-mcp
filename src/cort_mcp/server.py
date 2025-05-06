import sys
import os
import argparse
import yaml
import json
from .recursive_thinking_ai import EnhancedRecursiveThinkingChat
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.server.models import ServerCapabilities

DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_PROVIDER = "openai"

# ロギング設定
def setup_logging(log: str, logfile: str):
    # 必ず /home/kunihiros/project/cort-mcp/cort-mcp.log に絶対パスで出力
    abs_logfile = "/home/kunihiros/project/cort-mcp/cort-mcp.log"
    try:
        import logging as py_logging
        py_logging.basicConfig(level=py_logging.DEBUG)  # 追加: ログレベル明示
        file_handler = py_logging.FileHandler(abs_logfile, mode="a", encoding="utf-8")
        file_handler.setLevel(py_logging.DEBUG)
        py_logging.getLogger().addHandler(file_handler)
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

server = Server(name="cort-mcp", version="0.1.0")

@server.call_tool()
async def cort_think_simple(name, params):
    """簡易思考ツール: params(dict)を受けて要約や短い思考結果を返す"""
    prompt = params.get("prompt")
    model, provider, api_key = resolve_model_and_provider(params)
    import logging as py_logging
    py_logging.info(f"cort_think_simple called: prompt={prompt} model={model} provider={provider}")
    if not prompt:
        py_logging.warning("cort_think_simple: prompt is required")
        return [
            {"type": "text", "text": "prompt is required"}
        ]
    try:
        chat = EnhancedRecursiveThinkingChat(api_key=api_key, model=model, provider=provider)
        result = chat.think(prompt, details=False)
        py_logging.info("cort_think_simple: result generated successfully")
        return [
            {"type": "text", "text": result["response"]},
            {"type": "text", "text": f"model: {model}, provider: {provider}"}
        ]
    except Exception:
        py_logging.exception("[ERROR] cort_think_simple failed")
        fallback_api_key = get_api_key("openai")
        if fallback_api_key:
            chat = EnhancedRecursiveThinkingChat(api_key=fallback_api_key, model=DEFAULT_MODEL, provider="openai")
            result = chat.think(prompt, details=False)
            py_logging.info("cort_think_simple: fallback result generated successfully")
            return [
                {"type": "text", "text": result["response"]},
                {"type": "text", "text": f"model: {DEFAULT_MODEL}, provider: openai (fallback)"}
            ]
        else:
            py_logging.error("cort_think_simple: API key for OpenAI is missing (cannot fallback)")
            return [
                {"type": "text", "text": "API key for OpenAI is missing (cannot fallback)"}
            ]

@server.call_tool()
async def cort_think_details(name, params):
    """詳細思考ツール: params(dict)を受けて詳細な思考経路や根拠を返す"""
    prompt = params.get("prompt")
    model, provider, api_key = resolve_model_and_provider(params)
    import logging as py_logging
    py_logging.info(f"cort_think_details called: prompt={prompt} model={model} provider={provider}")
    if not prompt:
        py_logging.warning("cort_think_details: prompt is required")
        return [
            {"type": "text", "text": "prompt is required"}
        ]
    try:
        chat = EnhancedRecursiveThinkingChat(api_key=api_key, model=model, provider=provider)
        result = chat.think(prompt, details=True)
        yaml_log = yaml.safe_dump({
            "thinking_rounds": result.get("thinking_rounds"),
            "thinking_history": result.get("thinking_history")
        }, allow_unicode=True, sort_keys=False)
        py_logging.info("cort_think_details: result generated successfully")
        return [
            {"type": "text", "text": result["response"]},
            {"type": "text", "text": yaml_log},
            {"type": "text", "text": f"model: {model}, provider: {provider}"}
        ]
    except Exception:
        py_logging.exception("[ERROR] cort_think_details failed")
        fallback_api_key = get_api_key("openai")
        if fallback_api_key:
            chat = EnhancedRecursiveThinkingChat(api_key=fallback_api_key, model=DEFAULT_MODEL, provider="openai")
            result = chat.think(prompt, details=True)
            yaml_log = yaml.safe_dump({
                "thinking_rounds": result.get("thinking_rounds"),
                "thinking_history": result.get("thinking_history")
            }, allow_unicode=True, sort_keys=False)
            py_logging.info("cort_think_details: fallback result generated successfully")
            return [
                {"type": "text", "text": result["response"]},
                {"type": "text", "text": yaml_log},
                {"type": "text", "text": f"model: {DEFAULT_MODEL}, provider: openai (fallback)"}
            ]
        else:
            py_logging.error("cort_think_details: API key for OpenAI is missing (cannot fallback)")
            return [
                {"type": "text", "text": "API key for OpenAI is missing (cannot fallback)"}
            ]

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
            params = {"prompt": args.prompt}
            if args.model:
                params["model"] = args.model
            if args.provider:
                params["provider"] = args.provider
            if args.details:
                import asyncio
                result = asyncio.run(cort_think_details("cort.think.details", params))
            else:
                import asyncio
                result = asyncio.run(cort_think_simple("cort.think.simple", params))
            for r in result:
                print(r["text"])
        else:
            py_logging.info("Server mode: waiting for MCP stdio requests...")
            import asyncio
            async def run_server():
                py_logging.info("Starting stdio_server session...")
                async with stdio_server() as (read_stream, write_stream):
                    py_logging.info("stdio_server session established. Running server.run...")
                    init_opts = InitializationOptions(
                        server_name="cort-mcp",
                        server_version="0.1.0",
                        capabilities=ServerCapabilities(),
                        instructions=None
                    )
                    await server.run(read_stream, write_stream, init_opts)
            import sys
            if sys.version_info >= (3, 7):
                import asyncio
                asyncio.run(run_server())
            else:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(run_server())
    except Exception as e:
        py_logging.exception(f"[FATAL] Unhandled exception in main: {e}")
        print(f"[FATAL] Unhandled exception in main: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
