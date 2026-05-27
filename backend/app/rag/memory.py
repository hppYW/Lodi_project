# memory.py — 세션별 대화 히스토리 관리 모듈
# 역할: 세션 ID 기반으로 대화 메모리를 저장, 조회, 삭제 (서버 재시작 시 초기화)

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory

_session_store: dict[str, ChatMessageHistory] = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """세션 ID에 해당하는 대화 히스토리를 반환. 없으면 새로 생성."""
    if session_id not in _session_store:
        _session_store[session_id] = ChatMessageHistory()
    return _session_store[session_id]


def clear_session(session_id: str) -> None:
    """세션 삭제 (새 대화 시작 시 호출)."""
    if session_id in _session_store:
        del _session_store[session_id]
