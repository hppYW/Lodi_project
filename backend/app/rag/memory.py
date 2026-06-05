# ============================================================
# memory.py — 세션별 대화 히스토리 관리 모듈 (Sliding Window)
# ============================================================
# [역할]
#   세션 ID 기반으로 대화 메모리를 저장, 조회, 삭제합니다.
#   서버 재시작 시 초기화됩니다 (In-Memory 방식).
#
# [고도화 포인트: Sliding Window 메모리]
#   기본 ChatMessageHistory는 모든 메시지를 무한히 저장합니다.
#   대화가 길어지면 LLM의 토큰 제한(context window)을 초과하여
#   오류가 발생하거나 답변 품질이 떨어집니다.
#
#   Sliding Window 방식은 최근 N턴의 대화만 유지하여:
#     ✓ 토큰 제한 내에서 안정적 동작
#     ✓ 최근 맥락에 집중한 정확한 답변
#     ✗ 오래된 대화 내용은 잊어버림 (트레이드오프)
#
#   [예시: MAX_TURNS=5일 때]
#     턴 1: "주휴수당이 뭐야?" / "주휴수당은..."   ← 삭제됨
#     턴 2: "계산법은?" / "계산법은..."              ← 삭제됨
#     턴 3: "15시간 미만이면?" / "15시간 미만..."   ← 유지 (윈도우 시작)
#     턴 4: "그럼 주 3일은?" / "주 3일이면..."       ← 유지
#     턴 5: "퇴직금도 궁금해" / "퇴직금은..."        ← 유지
#     턴 6: "1년 미만이면?" / "1년 미만..."           ← 유지
#     턴 7: "감사합니다" / "도움이 되셨다면..."       ← 유지 (가장 최근)
# ============================================================

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage

# ── 설정 상수 ──
# 최대 유지할 대화 턴 수 (1턴 = 사용자 질문 1개 + AI 응답 1개 = 메시지 2개)
# 5턴이면 최대 10개 메시지가 유지됨
# → Upstage Solar 모델의 컨텍스트 윈도우를 고려한 설정
MAX_TURNS = 5

# ── 세션 저장소 ──
# 서버 메모리에 유지되며, 서버 재시작 시 모든 세션이 초기화됩니다.
# 프로덕션 환경에서는 Redis 등 외부 저장소로 교체를 권장합니다.
_session_store: dict[str, "SlidingWindowHistory"] = {}


class SlidingWindowHistory(BaseChatMessageHistory):
    """
    Sliding Window 방식의 대화 히스토리 관리 클래스.

    최근 MAX_TURNS턴의 대화만 유지하여 토큰 사용량을 제어합니다.
    LangChain의 BaseChatMessageHistory를 상속하여
    RunnableWithMessageHistory와 완벽히 호환됩니다.

    [왜 직접 구현하는가?]
      LangChain 기본 ChatMessageHistory는 윈도우 제한이 없습니다.
      ConversationBufferWindowMemory가 있지만 RunnableWithMessageHistory와
      조합이 번거로워, 깔끔한 커스텀 구현이 더 유지보수하기 좋습니다.
    """

    def __init__(self, max_turns: int = MAX_TURNS):
        """
        Args:
            max_turns: 유지할 최대 대화 턴 수.
                       1턴 = HumanMessage + AIMessage = 2개 메시지
        """
        self._messages: list[BaseMessage] = []
        self._max_messages = max_turns * 2  # 턴 수 → 메시지 수 변환

    @property
    def messages(self) -> list[BaseMessage]:
        """현재 저장된 메시지 목록을 반환합니다 (읽기 전용)."""
        return self._messages

    def add_message(self, message: BaseMessage) -> None:
        """
        새 메시지를 추가하고, 윈도우 크기 초과 시 오래된 메시지를 제거합니다.

        [동작 원리]
          메시지 추가 후 전체 개수가 _max_messages를 초과하면
          가장 오래된 메시지부터 2개씩 제거합니다.
          2개씩 제거하는 이유: 질문-응답 쌍이 깨지지 않도록 하기 위함.

        [예시]
          max_messages=10 (5턴), 현재 10개 → 새 메시지 추가 → 11개
          → 앞에서 2개(가장 오래된 질문+응답) 제거 → 9개
          → 이후 AI 응답 추가 → 10개 (다시 5턴 완성)

        Args:
            message: 추가할 메시지 (HumanMessage 또는 AIMessage)
        """
        self._messages.append(message)

        # 윈도우 크기 초과 시 오래된 메시지 쌍(질문+응답) 단위로 제거
        while len(self._messages) > self._max_messages:
            self._messages.pop(0)  # 가장 오래된 메시지 제거
            if self._messages:
                self._messages.pop(0)  # 쌍을 맞추기 위해 하나 더 제거

    def clear(self) -> None:
        """모든 메시지를 삭제합니다 (새 대화 시작 시 호출)."""
        self._messages = []


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """
    세션 ID에 해당하는 대화 히스토리를 반환합니다.
    존재하지 않으면 새로운 SlidingWindowHistory를 생성합니다.

    [호출 흐름]
      RunnableWithMessageHistory가 체인 실행 시 자동으로 이 함수를 호출하여
      세션별 대화 이력을 로드하고, 체인 실행 후 새 메시지를 저장합니다.

    Args:
        session_id: 클라이언트에서 전달하는 고유 세션 식별자
                    (예: 프론트엔드의 chat.id 값)

    Returns:
        해당 세션의 SlidingWindowHistory 인스턴스
    """
    if session_id not in _session_store:
        _session_store[session_id] = SlidingWindowHistory(max_turns=MAX_TURNS)
    return _session_store[session_id]


def clear_session(session_id: str) -> None:
    """
    특정 세션의 대화 이력을 완전히 삭제합니다.
    사용자가 '새 대화'를 시작할 때 호출됩니다.

    Args:
        session_id: 삭제할 세션의 식별자
    """
    if session_id in _session_store:
        del _session_store[session_id]


def get_active_sessions() -> list[str]:
    """
    현재 활성 중인 세션 ID 목록을 반환합니다.
    관리자 모니터링이나 디버깅 용도로 사용할 수 있습니다.

    Returns:
        활성 세션 ID 리스트
    """
    return list(_session_store.keys())
