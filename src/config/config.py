from dataclasses import dataclass
import configparser
import json
import logging
from typing import List
from pathlib import Path

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
    config_path: str = 'config/config.ini'
    
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
        
        if not Path(path).exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")
        
        if not config.read(path, encoding='utf-8'):
            raise FileNotFoundError(f"設定ファイルの読み込みに失敗: {path}")
        
        try:
            admin_ids_str = config['DEFAULT'].get('ADMIN_USER_IDS', '[]')
            admin_ids = json.loads(admin_ids_str)
            
            if not isinstance(admin_ids, list):
                raise ValueError("ADMIN_USER_IDSはリスト形式である必要があります")
                
            return cls(
                cohere_api_key=config['DEFAULT']['COHERE_API_KEY'],
                discord_token=config['DEFAULT']['DISCORD_TOKEN'],
                master_admin_id=int(config['DEFAULT']['MASTER_ADMIN_ID']),
                admin_user_ids=admin_ids,
                config_path=path
            )
            
        except KeyError as e:
            raise ValueError(f"必要な設定項目がありません: {e}")
        except ValueError as e:
            raise ValueError(f"設定値が不正です: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"ADMIN_USER_IDSのJSON形式が不正です: {e}")

    async def update_config(self, key: str, value: str) -> None:
        """設定を更新してファイルに保存"""
        if not Path(self.config_path).exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {self.config_path}")
            
        try:
            config = configparser.ConfigParser()
            config.read(self.config_path, encoding='utf-8')
            
            if key not in config['DEFAULT']:
                raise KeyError(f"未知の設定要素です: {key}")
            
            config['DEFAULT'][key] = value
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                config.write(f)
            
            if key == 'ADMIN_USER_IDS':
                try:
                    new_admin_ids = json.loads(value)
                    if not isinstance(new_admin_ids, list):
                        raise ValueError("ADMIN_USER_IDSはリスト形式である必要があります")
                    self.admin_user_ids = new_admin_ids
                except json.JSONDecodeError as e:
                    raise ValueError(f"ADMIN_USER_IDSのJSON形式が不正です: {e}")
                
            elif key == 'MASTER_ADMIN_ID':
                self.master_admin_id = int(value)
                
            elif key == 'DISCORD_TOKEN':
                self.discord_token = value
                
            elif key == 'COHERE_API_KEY':
                self.cohere_api_key = value
                
        except Exception as e:
            logger.error(f"設定の更新に失敗: {e}")
            raise RuntimeError(f"設定の更新に失敗: {e}")