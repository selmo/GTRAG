"""로컬 설정 저장 / 로드 유틸리티"""

import os, json
from typing import Dict, Any

SETTINGS_DIR  = os.path.expanduser("~/.gtrag")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings_local.json")


def load_settings() -> Dict[str, Any]:
    """파일이 있으면 읽어서 반환, 없으면 빈 dict"""
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except Exception as e:
        print(f"[로컬 설정 로드 실패] {e}")
        return {}


def save_settings(data: Dict[str, Any]) -> None:
    """dict → JSON 파일 저장"""
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[로컬 설정 저장 실패] {e}")
