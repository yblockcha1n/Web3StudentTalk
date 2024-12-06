import cohere
from typing import Dict, List
import json
import logging

logger = logging.getLogger(__name__)

class CohereLogic:
    """Cohere API連携クラス"""
    def __init__(self, api_key: str):
        self.client = cohere.ClientV2(api_key=api_key)
        self._load_system_prompt()
    
    def _load_system_prompt(self) -> None:
        """システムプロンプトをファイルから読み込み"""
        try:
            with open('assistant/prompt.json', 'r', encoding='utf-8') as f:
                self.system_prompt = json.load(f)['system_prompt']
        except Exception as e:
            logger.error(f"プロンプトファイルの読み込みに失敗: {e}")
            #　読み取れなかった場合の考慮
            self.system_prompt = "親切なAIアシスタントとして振る舞ってください。"

    async def update_system_prompt(self, new_prompt: str) -> None:
        """システムプロンプトを更新"""
        try:
            with open('assistant/prompt.json', 'w', encoding='utf-8') as f:
                json.dump({'system_prompt': new_prompt}, f, ensure_ascii=False, indent=2)
            self.system_prompt = new_prompt
        except Exception as e:
            raise RuntimeError(f"システムプロンプトの更新に失敗: {e}")

    async def chat(self, conversation: List[dict]) -> Dict:
        """Cohereとチャット"""
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(conversation)
        
        try:
            response = self.client.chat(
                model="command-r-plus-08-2024",
                messages=messages
            )
            
            return {
                'content': response.message.content[0].text if hasattr(response.message.content[0], 'text') else response.message.content,
                'token_info': {
                    'input': response.usage.tokens.input_tokens,
                    'output': response.usage.tokens.output_tokens
                }
            }
        except Exception as e:
            logger.error(f"Cohereチャットでエラー発生: {e}")
            raise