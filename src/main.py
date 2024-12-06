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

# ログの基本設定
# フォーマット：[時刻] [モジュール名] [ログレベル] [メッセージ]
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class Config:
    """設定管理クラス
    
    設定ファイルの読み込みと権限管理を担当
    
    Attributes:
        cohere_api_key (str): Cohere APIキー
        discord_token (str): Discord Token
        master_admin_id (int): マスター管理者のUSER ID
        admin_user_ids (List[int]): 管理者USER IDのリスト
    """
    cohere_api_key: str
    discord_token: str
    master_admin_id: int
    admin_user_ids: List[int]
    
    def is_admin(self, user_id: int) -> bool:
        """ユーザーが管理者権限を持っているか確認
        
        Args:
            user_id: 確認するUSER ID
            
        Returns:
            bool: 管理者権限を持っている場合True
        """
        return user_id == self.master_admin_id or user_id in self.admin_user_ids
    
    @classmethod
    def load(cls, path: str = 'config/config.ini') -> 'Config':
        """設定ファイルを読み込み、Configインスタンスを生成
        
        Args:
            path: 設定ファイルのパス
            
        Returns:
            Config: 設定情報を含むインスタンス
            
        Raises:
            FileNotFoundError: 設定ファイルが存在しない場合
            ValueError: 設定内容が不正な場合
        """
        config = configparser.ConfigParser()
        if not config.read(path, encoding='utf-8'):
            raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")
        
        try:
            admin_ids_str = config['DEFAULT'].get('ADMIN_USER_IDS', '[]')
            admin_ids = json.loads(admin_ids_str)
            return cls(
                cohere_api_key=config['DEFAULT']['COHERE_API_KEY'],
                discord_token=config['DEFAULT']['DISCORD_TOKEN'],
                master_admin_id=int(config['DEFAULT']['MASTER_ADMIN_ID']),
                admin_user_ids=admin_ids
            )
        except KeyError as e:
            raise ValueError(f"必要な設定項目がありません: {e}")
        except ValueError as e:
            raise ValueError(f"設定値が不正です: {e}")

class ConversationManager:
    """会話履歴とユーザー設定の管理クラス
    
    ユーザーごとの会話履歴と表示設定を管理
    """
    def __init__(self):
        self.conversations: Dict[int, List[dict]] = {}
        self.ephemeral_settings: Dict[int, bool] = {}
    
    def add_message(self, user_id: int, message: dict) -> None:
        """会話履歴にメッセージを追加"""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        self.conversations[user_id].append(message)
    
    def get_conversation(self, user_id: int) -> List[dict]:
        """ユーザーの会話履歴を取得"""
        return self.conversations.get(user_id, [])
    
    def reset_conversation(self, user_id: int) -> None:
        """会話履歴をリセット"""
        self.conversations[user_id] = []
    
    def get_ephemeral_setting(self, user_id: int) -> bool:
        """メッセージ表示設定を取得"""
        return self.ephemeral_settings.get(user_id, True)
    
    def set_ephemeral_setting(self, user_id: int, setting: bool) -> None:
        """メッセージ表示設定を更新"""
        self.ephemeral_settings[user_id] = setting

class ChatBot(discord.Client):
    """WestAIのクラス"""
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(intents=intents)
        
        self.config = Config.load()
        self.tree = app_commands.CommandTree(self)
        self.cohere_client = cohere.ClientV2(api_key=self.config.cohere_api_key)
        self.conversation_manager = ConversationManager()
        
        self.system_prompt = self._load_system_prompt()
    
    def _load_system_prompt(self) -> str:
        """システムプロンプトをファイルから読み込み"""
        try:
            with open('assistant/prompt.json', 'r', encoding='utf-8') as f:
                return json.load(f)['system_prompt']
        except Exception as e:
            logger.error(f"プロンプトファイルの読み込みに失敗: {e}")
            #　読み取れなかった場合の考慮            
            return "親切なAIアシスタントとして振る舞ってください。"

    async def update_config(self, key: str, value: str) -> None:
        """設定を更新してファイルに保存"""
        try:
            config = configparser.ConfigParser()
            config.read('config/config.ini', encoding='utf-8')
            config['DEFAULT'][key] = value
            
            with open('config/config.ini', 'w', encoding='utf-8') as f:
                config.write(f)
                
            # 設定値をメモリ上でも更新
            if key == 'COHERE_API_KEY':
                self.cohere_client = cohere.ClientV2(api_key=value)
                self.config.cohere_api_key = value
            elif key == 'ADMIN_USER_IDS':
                self.config.admin_user_ids = json.loads(value)
                
        except Exception as e:
            raise RuntimeError(f"設定の更新に失敗: {e}")

    async def update_system_prompt(self, new_prompt: str) -> None:
        """システムプロンプトを更新"""
        try:
            with open('assistant/prompt.json', 'w', encoding='utf-8') as f:
                json.dump({'system_prompt': new_prompt}, f, ensure_ascii=False, indent=2)
            self.system_prompt = new_prompt
        except Exception as e:
            raise RuntimeError(f"システムプロンプトの更新に失敗: {e}")

    async def setup_hook(self) -> None:
        await self.tree.sync()

class ChatCommands(app_commands.Group):
    """Discordスラッシュコマンドの管理クラス"""
    def __init__(self, bot: ChatBot):
        super().__init__(name="chat", description="チャットコマンド")
        self.bot = bot
    
    async def _create_response_embed(self, content: str, token_info: Optional[dict] = None) -> Embed:
        """埋め込みメッセージの作成"""
        embed = Embed(description=content, color=int('56F0FA', 16))
        if token_info:
            embed.set_footer(text=f"Token使用量: 入力 {token_info['input']}, 出力 {token_info['output']}")
        return embed

    @app_commands.command(name="list_admins", description="現在の管理者リストを表示 (マスター管理者のみ)")
    async def list_admins(self, interaction: discord.Interaction):
        """管理者リスト表示コマンド"""
        if interaction.user.id != self.bot.config.master_admin_id:
            embed = await self._create_response_embed("このコマンドはマスター管理者のみ実行できます。")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            # マスター管理者とその他の管理者を分けて表示
            admin_list = ["管理者リスト:"]
            
            # マスター管理者のユーザー情報を取得
            master_user = await self.bot.fetch_user(self.bot.config.master_admin_id)
            master_name = master_user.name if master_user else "Unknown"
            admin_list.append(f"\nマスター管理者:\n• {self.bot.config.master_admin_id} ({master_name})")
            
            if self.bot.config.admin_user_ids:
                admin_list.append("\nその他の管理者:")
                for admin_id in self.bot.config.admin_user_ids:
                    user = await self.bot.fetch_user(admin_id)
                    user_name = user.name if user else "Unknown"
                    admin_list.append(f"• {admin_id} ({user_name})")
            else:
                admin_list.append("\nその他の管理者: なし")

            embed = await self._create_response_embed("\n".join(admin_list))
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"管理者リスト表示でエラー発生: {e}")
            embed = await self._create_response_embed("管理者リストの表示に失敗しました。")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="send", description="WestAIにメッセージを送信")
    async def send(self, interaction: discord.Interaction, message: str):
        """メッセージ送信コマンド"""
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

    @app_commands.command(name="reset", description="会話履歴をリセット")
    async def reset(self, interaction: discord.Interaction):
        """コンテキスト（会話履歴）リセットコマンド"""
        is_ephemeral = self.bot.conversation_manager.get_ephemeral_setting(interaction.user.id)
        self.bot.conversation_manager.reset_conversation(interaction.user.id)
        
        embed = await self._create_response_embed("会話履歴をリセットしました。")
        await interaction.response.send_message(embed=embed, ephemeral=is_ephemeral)

    @app_commands.command(name="settings", description="メッセージの表示設定を変更")
    async def settings(self, interaction: discord.Interaction, ephemeral: bool):
        """表示設定変更コマンド"""
        self.bot.conversation_manager.set_ephemeral_setting(interaction.user.id, ephemeral)
        status = "非公開" if ephemeral else "公開"
        
        embed = await self._create_response_embed(f"メッセージ表示設定を{status}に変更しました。")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="update_key", description="Cohere APIキーを更新 (マスター管理者のみ)")
    async def update_key(self, interaction: discord.Interaction, api_key: str):
        """こーひーAPIキーの更新 (ワイのみ)"""
        if interaction.user.id != self.bot.config.master_admin_id:
            embed = await self._create_response_embed("このコマンドはマスター管理者のみ実行できます。")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.update_config('COHERE_API_KEY', api_key)
            embed = await self._create_response_embed("APIキーを更新しました。")
        except Exception as e:
            logger.error(f"APIキー更新でエラー発生: {e}")
            embed = await self._create_response_embed("APIキーの更新に失敗しました。")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="add_admin", description="管理者ユーザーを追加/削除 (マスター管理者のみ)")
    async def add_admin(self, interaction: discord.Interaction, user_id: str, add: bool):
        """管理者追加・削除コマンド"""
        if interaction.user.id != self.bot.config.master_admin_id:
            embed = await self._create_response_embed("このコマンドはマスター管理者のみ実行できます。")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            admin_id = int(user_id)
            current_admins = set(self.bot.config.admin_user_ids)
            
            if add:
                current_admins.add(admin_id)
            else:
                current_admins.discard(admin_id)
            
            await self.bot.update_config('ADMIN_USER_IDS', json.dumps(list(current_admins)))
            action = "追加" if add else "削除"
            embed = await self._create_response_embed(f"管理者を{action}しました。")
            
        except ValueError:
            embed = await self._create_response_embed("無効なユーザーIDです。")
        except Exception as e:
            logger.error(f"管理者更新でエラー発生: {e}")
            embed = await self._create_response_embed("管理者の更新に失敗しました。")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="update_system_prompt", description="システムプロンプトを更新 (管理者のみ)")
    async def update_system_prompt(self, interaction: discord.Interaction, prompt: str, reset_conversations: bool = False):
        """システムプロンプト更新コマンド (デフォルト履歴消去無効)"""
        if not self.bot.config.is_admin(interaction.user.id):
            embed = await self._create_response_embed("このコマンドは管理者のみ実行できます。")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.update_system_prompt(prompt)
            
            if reset_conversations:
                self.bot.conversation_manager.conversations.clear()
                message = "システムプロンプトを更新し、全ユーザーの会話履歴をリセットしました。"
            else:
                message = "システムプロンプトを更新しました。"
                
            embed = await self._create_response_embed(message)
            
        except Exception as e:
            logger.error(f"システムプロンプト更新でエラー発生: {e}")
            embed = await self._create_response_embed("システムプロンプトの更新に失敗しました。")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

async def main():
    """
    主軸エントリーポイント
    - WestAIの初期化と起動を行う
    - エラーハンドリングとログ記録を実施
    """
    try:
        bot = ChatBot()
        bot.tree.add_command(ChatCommands(bot))
        await bot.start(bot.config.discord_token)
    except Exception as e:
        logger.error(f"WestAIの起動に失敗: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())