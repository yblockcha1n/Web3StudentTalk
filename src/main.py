import discord
from discord import app_commands, Embed
import cohere
import configparser
import json
import asyncio
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self):
        self.conversations: Dict[int, List[dict]] = {}
        self.ephemeral_settings: Dict[int, bool] = {}
        
    def add_message(self, user_id: int, message: dict):
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        self.conversations[user_id].append(message)
        
    def get_conversation(self, user_id: int) -> List[dict]:
        return self.conversations.get(user_id, [])
        
    def reset_conversation(self, user_id: int):
        self.conversations[user_id] = []
        
    def get_ephemeral_setting(self, user_id: int) -> bool:
        return self.ephemeral_settings.get(user_id, True)
        
    def set_ephemeral_setting(self, user_id: int, setting: bool):
        self.ephemeral_settings[user_id] = setting

class ChatBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.all()
        #intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.load_config()
        self.cohere_client = cohere.ClientV2(api_key=self.cohere_api_key)
        self.conversation_manager = ConversationManager()
        
        try:
            with open('assistant/prompt.json', 'r', encoding='utf-8') as f:
                self.system_prompt = json.load(f)['system_prompt']
        except Exception as e:
            logger.error(f"プロンプトファイルの読み込みに失敗: {e}")

    def load_config(self):
        config = configparser.ConfigParser()
        config.read('config/config.ini', encoding='utf-8')
        self.cohere_api_key = config['DEFAULT']['COHERE_API_KEY']
        self.discord_token = config['DEFAULT']['DISCORD_TOKEN']

    async def setup_hook(self):
        await self.tree.sync()

class ChatCommands(app_commands.Group):
    def __init__(self, bot: ChatBot):
        super().__init__(name="chat", description="チャットコマンド")
        self.bot = bot

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
            
            response = self.bot.cohere_client.chat(
                model="command-r-plus-08-2024",
                messages=messages
            )
            
            if hasattr(response.message.content[0], 'text'):
                content = response.message.content[0].text
            else:
                content = response.message.content

            self.bot.conversation_manager.add_message(
                interaction.user.id,
                {"role": "assistant", "content": content}
            )

            embed = Embed(description=content, color=int('56F0FA', 16))
            embed.set_footer(text=f"Token使用量: 入力 {response.usage.tokens.input_tokens}, 出力 {response.usage.tokens.output_tokens}")
            
            await interaction.followup.send(embed=embed, ephemeral=is_ephemeral)
            
        except Exception as e:
            logger.error(f"チャットコマンドでエラー発生: {e}")
            await interaction.followup.send("エラーが発生しました。後でもう一度お試しください。", ephemeral=is_ephemeral)

    @app_commands.command(name="reset", description="会話履歴をリセット")
    async def reset(self, interaction: discord.Interaction):
        is_ephemeral = self.bot.conversation_manager.get_ephemeral_setting(interaction.user.id)
        self.bot.conversation_manager.reset_conversation(interaction.user.id)
        
        embed = Embed(description="会話履歴をリセットしました。", color=int('56F0FA', 16))
        await interaction.response.send_message(embed=embed, ephemeral=is_ephemeral)

    @app_commands.command(name="settings", description="メッセージの表示設定を変更")
    async def settings(self, interaction: discord.Interaction, ephemeral: bool):
        self.bot.conversation_manager.set_ephemeral_setting(interaction.user.id, ephemeral)
        status = "非公開" if ephemeral else "公開"
        
        embed = Embed(
            description=f"メッセージ表示設定を{status}に変更しました。",
            color=int('56F0FA', 16)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

def main():
    try:
        bot = ChatBot()
        bot.tree.add_command(ChatCommands(bot))
        bot.run(bot.discord_token)
    except Exception as e:
        logger.error(f"起動に失敗: {e}")

if __name__ == "__main__":
    main()