from discord import app_commands, Embed, Interaction
from typing import Optional
import logging
import json

from ..logic.cohere import CohereLogic

logger = logging.getLogger(__name__)

class ChatCommands(app_commands.Group):
    """コマンドの管理クラス"""
    def __init__(self, bot):
        super().__init__(name="chat", description="チャットコマンド")
        self.bot = bot
    
    async def _create_response_embed(self, content: str, token_info: Optional[dict] = None) -> Embed:
        """埋込メッセージの作成"""
        embed = Embed(description=content, color=int('56F0FA', 16))
        if token_info:
            embed.set_footer(text=f"Token使用量: 入力 {token_info['input']}, 出力 {token_info['output']}")
        return embed

    @app_commands.command(name="send", description="WestAIにメッセージを送信")
    async def send(self, interaction: Interaction, message: str):
        """メッセージ送信コマンド"""
        is_ephemeral = self.bot.conversation_manager.get_ephemeral_setting(interaction.user.id)
        await interaction.response.defer(ephemeral=is_ephemeral)
        
        try:
            self.bot.conversation_manager.add_message(
                interaction.user.id,
                {"role": "user", "content": message}
            )
            
            conversation = self.bot.conversation_manager.get_conversation(interaction.user.id)
            response = await self.bot.cohere_logic.chat(conversation)
            
            self.bot.conversation_manager.add_message(
                interaction.user.id,
                {"role": "assistant", "content": response['content']}
            )
            
            embed = await self._create_response_embed(response['content'], response['token_info'])
            await interaction.followup.send(embed=embed, ephemeral=is_ephemeral)
            
        except Exception as e:
            logger.error(f"チャットコマンドでエラー発生: {e}")
            error_embed = await self._create_response_embed("エラーが発生しました。後でもう一度お試しください。")
            await interaction.followup.send(embed=error_embed, ephemeral=is_ephemeral)

    @app_commands.command(name="reset", description="会話履歴をリセット")
    async def reset(self, interaction: Interaction):
        """会話履歴リセットコマンド"""
        is_ephemeral = self.bot.conversation_manager.get_ephemeral_setting(interaction.user.id)
        self.bot.conversation_manager.reset_conversation(interaction.user.id)
        
        embed = await self._create_response_embed("会話履歴をリセットしました。")
        await interaction.response.send_message(embed=embed, ephemeral=is_ephemeral)

    @app_commands.command(name="settings", description="メッセージの表示設定を変更")
    async def settings(self, interaction: Interaction, ephemeral: bool):
        """表示設定変更コマンド"""
        self.bot.conversation_manager.set_ephemeral_setting(interaction.user.id, ephemeral)
        status = "非公開" if ephemeral else "公開"
        
        embed = await self._create_response_embed(f"メッセージ表示設定を{status}に変更しました。")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="list_admins", description="現在の管理者リストを表示 (マスター管理者のみ)")
    async def list_admins(self, interaction: Interaction):
        """管理者リスト表示コマンド"""
        if interaction.user.id != self.bot.config.master_admin_id:
            embed = await self._create_response_embed("このコマンドはマスター管理者のみ実行できます。")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            admin_list = ["管理者リスト:"]
            
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

    @app_commands.command(name="update_key", description="Cohere APIキーを更新 (マスター管理者のみ)")
    async def update_key(self, interaction: Interaction, api_key: str):
        """Cohere APIキーの更新コマンド"""
        if interaction.user.id != self.bot.config.master_admin_id:
            embed = await self._create_response_embed("このコマンドはマスター管理者のみ実行できます。")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.config.update_config('COHERE_API_KEY', api_key)
            self.bot.cohere_logic = CohereLogic(api_key)
            embed = await self._create_response_embed("APIキーを更新しました。")
        except Exception as e:
            logger.error(f"APIキー更新でエラー発生: {e}")
            embed = await self._create_response_embed("APIキーの更新に失敗しました。")
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="add_admin", description="管理者ユーザーを追加/削除 (マスター管理者のみ)")
    async def add_admin(self, interaction: Interaction, user_id: str, add: bool):
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
            
            await self.bot.config.update_config('ADMIN_USER_IDS', json.dumps(list(current_admins)))
            action = "追加" if add else "削除"
            embed = await self._create_response_embed(f"管理者を{action}しました。")
            
        except ValueError:
            embed = await self._create_response_embed("無効なユーザーIDです。")
        except Exception as e:
            logger.error(f"管理者更新でエラー発生: {e}")
            embed = await self._create_response_embed("管理者の更新に失敗しました。")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="update_system_prompt", description="システムプロンプトを更新 (管理者のみ)")
    async def update_system_prompt(self, interaction: Interaction, prompt: str, reset_conversations: bool = False):
        """システムプロンプト更新コマンド"""
        if not self.bot.config.is_admin(interaction.user.id):
            embed = await self._create_response_embed("このコマンドは管理者のみ実行できます。")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.cohere_logic.update_system_prompt(prompt)
            
            if reset_conversations:
                self.bot.conversation_manager.clear_all_conversations()
                message = "システムプロンプトを更新し、全ユーザーの会話履歴をリセットしました。"
            else:
                message = "システムプロンプトを更新しました。"
                
            embed = await self._create_response_embed(message)
            
        except Exception as e:
            logger.error(f"システムプロンプト更新でエラー発生: {e}")
            embed = await self._create_response_embed("システムプロンプトの更新に失敗しました。")
        
        await interaction.followup.send(embed=embed, ephemeral=True)