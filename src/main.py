import discord
from discord import app_commands, Embed
import cohere
import configparser
import json
import asyncio
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
from pathlib import Path

# ログ基本設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# データ管理クラス　(設定ファイルの整合性チェック)
@dataclass
class Config:
    cohere_api_key: str
    discord_token: str
    admin_user_id: int
    
    @classmethod
    def load(cls, path: str = 'config/config.ini') -> 'Config':
        config = configparser.ConfigParser()
        if not config.read(path, encoding='utf-8'):
            raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")
        
        try:
            return cls(
                cohere_api_key=config['DEFAULT']['COHERE_API_KEY'],
                discord_token=config['DEFAULT']['DISCORD_TOKEN'],
                admin_user_id=int(config['DEFAULT']['ADMIN_USER_ID'])
            )
        except KeyError as e:
            raise ValueError(f"必要な設定項目がありません: {e}")
        except ValueError as e:
            raise ValueError(f"設定値が不正です: {e}")

# 会話管理クラス
class ConversationManager:
    def __init__(self):
        self.conversations: Dict[int, List[dict]] = {}
        self.ephemeral_settings: Dict[int, bool] = {}
        
    # メッセージ追加
    def add_message(self, user_id: int, message: dict) -> None:
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        self.conversations[user_id].append(message)
                
    # 会話取得
    def get_conversation(self, user_id: int) -> List[dict]:
        return self.conversations.get(user_id, [])
    
    # 会話消去
    def reset_conversation(self, user_id: int) -> None:
        self.conversations[user_id] = []
        
    # 表示設定の取得
    def get_ephemeral_setting(self, user_id: int) -> bool:
        return self.ephemeral_settings.get(user_id, True)
    
    # 表示設定
    def set_ephemeral_setting(self, user_id: int, setting: bool) -> None:
        self.ephemeral_settings[user_id] = setting

# BOT初期化クラス
class ChatBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(intents=intents)
        
        self.config = Config.load()
        self.tree = app_commands.CommandTree(self)
        self.cohere_client = cohere.ClientV2(api_key=self.config.cohere_api_key)
        self.conversation_manager = ConversationManager()
        
        self.system_prompt = self._load_system_prompt()
    
    # システムプロンプトの読み込み
    def _load_system_prompt(self) -> str:
        try:
            with open('assistant/prompt.json', 'r', encoding='utf-8') as f:
                return json.load(f)['system_prompt']
        except Exception as e:
            logger.error(f"プロンプトファイルの読み込みに失敗: {e}")            
            #　読み取れなかった場合の考慮
            return "親切なAIアシスタントとして振る舞ってください。"

    async def update_api_key(self, new_key: str) -> None:
        try:
            config = configparser.ConfigParser()
            config.read('config/config.ini', encoding='utf-8')
            config['DEFAULT']['COHERE_API_KEY'] = new_key
            
            with open('config/config.ini', 'w', encoding='utf-8') as f:
                config.write(f)
            
            self.cohere_client = cohere.ClientV2(api_key=new_key)
            self.config.cohere_api_key = new_key
        except Exception as e:
            raise RuntimeError(f"APIキーの更新に失敗: {e}")

    async def setup_hook(self) -> None:
        await self.tree.sync()

# Discordコマンド管理クラス
class ChatCommands(app_commands.Group):
    def __init__(self, bot: ChatBot):
        super().__init__(name="chat", description="チャットコマンド")
        self.bot = bot
    
    async def _create_response_embed(self, content: str, token_info: Optional[dict] = None) -> Embed:
        embed = Embed(description=content, color=int('56F0FA', 16))
        if token_info:
            embed.set_footer(text=f"Token使用量: 入力 {token_info['input']}, 出力 {token_info['output']}")
        return embed
    
    # メッセージ送信コマンド
    @app_commands.command(name="send", description="ふがAIにメッセージを送信")
    async def send(self, interaction: discord.Interaction, message: str):
        is_ephemeral = self.bot.conversation_manager.get_ephemeral_setting(interaction.user.id)
        await interaction.response.defer(ephemeral=is_ephemeral, thinking=False)
        
        try:
            self.bot.conversation_manager.add_message(
                interaction.user.id,
                {"role": "user", "content": message}
            )
            
            messages = [{"role": "system", "content": self.bot.system_prompt}]
            messages.extend(self.bot.conversation_manager.get_conversation(interaction.user.id))
            
            # 現行最新モデルのCMDR+ 24-08
            response = self.bot.cohere_client.chat(
                model="command-r-plus-08-2024",
                messages=messages
            )
            
            content = response.message.content[0].text if hasattr(response.message.content[0], 'text') else response.message.content
            
            self.bot.conversation_manager.add_message(
                interaction.user.id,
                {"role": "assistant", "content": content}
            )
            
            # 使用されたToken数の取得
            token_info = {
                'input': response.usage.tokens.input_tokens,
                'output': response.usage.tokens.output_tokens
            }
            
            embed = await self._create_response_embed(content, token_info)
            await interaction.followup.send(embed=embed, ephemeral=is_ephemeral)
            
        except Exception as e:
            logger.error(f"チャットコマンドでエラー発生: {e}")
            error_embed = await self._create_response_embed("エラーが発生しました。後でもう一度お試しください。")
            await interaction.followup.send(embed=error_embed, ephemeral=is_ephemeral)
            
    # コンテキスト（会話履歴）リセットコマンド
    @app_commands.command(name="reset", description="会話履歴をリセット")
    async def reset(self, interaction: discord.Interaction):
        is_ephemeral = self.bot.conversation_manager.get_ephemeral_setting(interaction.user.id)
        self.bot.conversation_manager.reset_conversation(interaction.user.id)
        
        embed = await self._create_response_embed("会話履歴をリセットしました。")
        await interaction.response.send_message(embed=embed, ephemeral=is_ephemeral)
        
    # 表示設定コマンド
    @app_commands.command(name="settings", description="メッセージの表示設定を変更")
    async def settings(self, interaction: discord.Interaction, ephemeral: bool):
        self.bot.conversation_manager.set_ephemeral_setting(interaction.user.id, ephemeral)
        status = "非公開" if ephemeral else "公開"
        
        embed = await self._create_response_embed(f"メッセージ表示設定を{status}に変更しました。")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # こーひーAPIキーの更新（ワイのみ）
    @app_commands.command(name="update_key", description="Cohere APIキーを更新 (管理者のみ)")
    async def update_key(self, interaction: discord.Interaction, api_key: str):
        if interaction.user.id != self.bot.config.admin_user_id:
            embed = await self._create_response_embed("このコマンドは管理者のみ実行できます。")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.update_api_key(api_key)
            embed = await self._create_response_embed("APIキーを更新しました。")
        except Exception as e:
            logger.error(f"APIキー更新でエラー発生: {e}")
            embed = await self._create_response_embed("APIキーの更新に失敗しました。")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

async def main():
    try:
        bot = ChatBot()
        bot.tree.add_command(ChatCommands(bot))
        await bot.start(bot.config.discord_token)
    except Exception as e:
        logger.error(f"BOT起動に失敗: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())