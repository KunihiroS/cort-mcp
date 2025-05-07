# cort-mcp

Chain-of-Recursive-Thoughts (CORT) MCPサーバー/CLIツール

---

## 特徴
- 再帰的思考AIロジックをパッケージ本体に集約
- CLIバッチ・MCPサーバー両対応
- OpenAI/OpenRouter API両対応
- pipx/uvxインストール・即コマンド利用可能

---

## ディレクトリ構成

```
cort-mcp/
├── cort_mcp/
│   ├── __init__.py
│   ├── recursive_thinking_ai.py
│   └── server.py
├── pyproject.toml
├── README.md
├── CHANGELOG.md
└── tests/
    └── test_server.py
```

---

## インストール

```
pipx install .
# または
uvx install .
```

---

## 使い方

### MCPサーバーモード（標準入出力でMCPプロトコルを受け付け）
```
cort-server
```

### CLIバッチモード（1回だけAI応答を返す）
```
cort-server --cli --prompt "質問内容"
```

### モデル指定・JSON出力例
```
cort-server --cli --prompt "質問" --model "openrouter/mistral-7b" --json
```

---

## ツールインターフェイス定義（MCPツール仕様）

### cort.think.simple
- **説明:** シンプルな再帰的思考AI応答を返す
- **パラメータ:**
    - `prompt` (string, 必須): AIへの入力プロンプト
    - `model` (string, 任意): モデル名（例: "gpt-4.1-mini", "qwen/qwen3-235b-a22b:free" など）
    - `provider` (string, 任意): "openai" または "openrouter"（省略時はデフォルト値）
- **戻り値:**
    - `response` (string): AIの応答
    - `model` (string): 使用モデル名
    - `provider` (string): 使用プロバイダー

### cort.think.details
- **説明:** 思考過程の詳細も含めて返す再帰的思考AIツール
- **パラメータ:**
    - `prompt` (string, 必須): AIへの入力プロンプト
    - `model` (string, 任意): モデル名
    - `provider` (string, 任意): "openai" または "openrouter"
- **戻り値:**
    - `response` (string): AIの応答
    - `model` (string): 使用モデル名
    - `provider` (string): 使用プロバイダー
    - `details` (string): 思考履歴や過程のYAML

---

## モデル・APIプロバイダーの切り替え・エラーハンドリング
- モデル名は「リクエストのparams['model']」またはCLIの`--model`で指定
- providerはparams['provider']で明示指定可能（省略時はデフォルト）
- 指定がなければ `server.py` 内の `DEFAULT_MODEL`/`DEFAULT_PROVIDER`（OpenAI/4.1-mini）が使われる
- **指定されたproviderに該当モデルが無い場合や、その他エラー時も自動的にOpenAIの4.1-mini（デフォルト）でフォールバック動作します**
- 外部設定ファイル（settings.json等）は一切不要

---

## APIキー設定
- OpenAI: `OPENAI_API_KEY` 環境変数で指定
- OpenRouter: `OPENROUTER_API_KEY` 環境変数で指定

---

## 進捗・現状レポート（2025-05-03 更新）

### ✅ MCPサーバー起動・MCP Hostからの呼び出し成功
- それほど長くない入力の応答に約1~2分程度かかる


#### 📝 ユーザー追加分TODO
- CLI による呼び出し機能の削除（MCP Server専用化）
- 軽量モデルへの変更（現状の4.1 miniだと時間がかかりすぎるため、より軽いモデルを試す）
- 思考過程における実際のLLMの出力を details tool の response に含むようにする
- Toolの説明の充実（AI呼び出し時にオプションパラメータへ null を設定し失敗していた問題の明確化）
- Log出力設定を引数指定にする (現状絶対PATHがハードコーディングされている)

---

### 起動例
```sh
$ cort-mcp
```

### ログ出力例
```
cort-mcp main() started
Server mode: waiting for MCP stdio requests...
Using selector: EpollSelector
Starting stdio_server session...
stdio_server session established. Running server.run...
```

---

## 開発・保守
- AIロジックは `cort_mcp/recursive_thinking_ai.py` に一元化
- CLI/サーバー切替・ツール登録は `cort_mcp/server.py` で管理
- テストは `tests/` 配下

---

## ライセンス
MIT

何か問題や要望があれば、READMEまたはissue等でお知らせください。
