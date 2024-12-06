import discord
from discord import app_commands
import logging

from src.config.config import Config
from src.logic.cohere import CohereLogic
from src.managers.conversation import ConversationManager
from ..commands.chat import ChatCommands

logger = logging.getLogger(__name__)

class DiscordLogic(discord.Client):
    """WestAIの初期化"""
    def __init__(self, config: Config, cohere_logic: CohereLogic):
        intents = discord.Intents.all()
        super().__init__(intents=intents)
        
        self.config = config
        self.cohere_logic = cohere_logic
        self.conversation_manager = ConversationManager()
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        """起動時のコマンド同期"""
        self.tree.add_command(ChatCommands(self))
        await self.tree.sync()

    async def on_ready(self):
        """起動完了時の処理"""
        logger.info(f"{self.user} としてログインしました")