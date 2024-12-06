# Web3StudentTalk (WestAI)

## 概要
WestAIは、Cohere社が提供する大規模言語モデルを活用したDiscord BOTです。

## 主要機能
- 自然言語での対話機能
- 会話文脈の保持と管理
- メッセージ表示設定の制御
- 会話履歴のリセット機能
- 管理者向けシステム設定機能

## 推奨環境要件
- Python 3.11
- Discord 2.3.2
- Cohere API
- Discord BOT Token

## 導入手順
1. パッケージ類のインストール
```bash
pip install -r requirements.txt
```

2. 設定ファイルの構成
以下の内容で`config/config.ini`を作成してください：
```ini
[DEFAULT]
COHERE_API_KEY = Cohereより発行されたAPIキー
DISCORD_TOKEN = Discordより発行されたToken
ADMIN_USER_ID = 管理者のDiscordユーザーID
```

3. システムプロンプトの設定
`assistant/prompt.json`に以下の内容を設定してください：
```json
{
    "system_prompt": "システムプロンプトをご指定ください"
}
```

4. システムの起動
```bash
python src/main.py
```

## 利用可能なコマンド
| コマンド | 説明 | 権限 |
|---------|------|------|
| /chat send | AIアシスタントとの対話を開始 | 一般ユーザー |
| /chat reset | 会話履歴の初期化 | 一般ユーザー |
| /chat settings | メッセージ表示設定の変更 | 一般ユーザー |
| /chat update_key | APIキーの更新 | 管理者のみ |

## システム構成
- Discord：Discordプラットフォームとの連携
- Cohere API：自然言語処理エンジン（command-r-plus-08-2024モデルを使用）
- データクラスベースの設定管理
- 非同期処理による効率的なリソース管理
- 包括的なエラー処理とログ記録システム
- オブジェクト指向的な構成

## ライセンス
本システムは無断利用可能ですが、CohereAPIの利用規約をご確認ください。

## 開発者情報
本システムに関する技術的なお問い合わせは、[ふが](https://x.com/fuga_135) までにご連絡ください。
