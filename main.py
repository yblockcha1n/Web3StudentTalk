import asyncio

from src.config.config import Config
from src.logic.cohere import CohereLogic
from src.logic.discord import DiscordLogic
from src.utils.logger import setup_logger

logger = setup_logger()

async def main():
    """主軸エントリーポイント"""
    try:
        config = Config.load()
        
        cohere_logic = CohereLogic(config.cohere_api_key)
        bot = DiscordLogic(config, cohere_logic)
        
        await bot.start(config.discord_token)
        
    except Exception as e:
        logger.error(f"起動に失敗: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())