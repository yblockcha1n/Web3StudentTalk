from typing import Dict, List

class ConversationManager:
    """会話履歴とユーザー設定の管理クラス"""
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
    
    def clear_all_conversations(self) -> None:
        """全ユーザーの会話履歴をリセット"""
        self.conversations.clear()
    
    def get_ephemeral_setting(self, user_id: int) -> bool:
        """メッセージ表示設定を取得"""
        return self.ephemeral_settings.get(user_id, True)
    
    def set_ephemeral_setting(self, user_id: int, setting: bool) -> None:
        """メッセージ表示設定を更新"""
        self.ephemeral_settings[user_id] = setting