# backend/app/guardrails.py
"""
입력 가드레일 

사용자 질문이 '한국 노동법' 도메인인지 판단해, 무관/악의적 질문을
B의 RAG 체인을 호출하기 *전에* 차단한다.

판단 순서 (앞 단계에서 결정되면 즉시 반환 — 순서가 중요)
  0) 입력 검증   : 빈/초장문/도배/의미없는 입력 등 비정상 입력 방어
  1) 인젝션 탐지 : "이전 지시 무시", 역할극 유도 등 프롬프트 인젝션/탈옥 차단
                   ※ 키워드 통과보다 먼저! ("...무시하고 주휴수당 말고 날씨" 우회 방지)
  2) 키워드      : allowlist / denylist (무료·즉시)
  3) 임베딩 유사도: 1~2단계로 못 가린 '애매한' 질문만 (Chroma 재활용)

설계 메모
  - 임베딩 단계는 vectorstore에 직접 의존하지 않고 외부 주입 콜러블
    (`similarity_search`)로 호출 → 이 모듈은 의존성 없이 import·테스트 가능.
  - 임계값(threshold)은 run_guardrail_eval.py 로 데이터 기반 튜닝.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

# ──────────────────────────────────────────────────────────────
# 거부 응답 메시지 (프론트엔드 계약: reply / sources / searchingDocs)
# ──────────────────────────────────────────────────────────────
MSG_OFF_DOMAIN = (
    "저는 **노동법 관련 질문**에만 답변할 수 있어요. "
    "주휴수당·연차·퇴직금·최저임금 같은 주제로 다시 물어봐 주세요."
)
MSG_INJECTION = (
    "죄송하지만 시스템 지시를 변경하거나 역할을 바꾸는 요청에는 응할 수 없어요. "
    "노동법 관련 질문을 도와드릴게요."
)
MSG_INPUT_INVALID = (
    "질문을 이해하지 못했어요. 노동법에 관해 궁금한 점을 한 문장으로 적어주세요. "
    "(예: 주휴수당은 어떻게 계산하나요?)"
)
MSG_TOO_LONG = (
    "질문이 너무 길어요. 핵심만 간단히 줄여서 다시 물어봐 주세요."
)

# stage → 거부 메시지 매핑 (refusal_payload에서 사용)
_STAGE_MESSAGE = {
    "injection": MSG_INJECTION,
    "input_empty": MSG_INPUT_INVALID,
    "input_gibberish": MSG_INPUT_INVALID,
    "input_too_long": MSG_TOO_LONG,
}

# 기존 호출부 호환용 (이전 이름)
REFUSAL_MESSAGE = MSG_OFF_DOMAIN


# ──────────────────────────────────────────────────────────────
# 0단계: 입력 검증 설정
# ──────────────────────────────────────────────────────────────
MAX_QUESTION_LENGTH = 2000   # 이보다 길면 차단 (컨텍스트 스터핑/도배 방어, 넉넉하게)
MIN_MEANINGFUL_CHARS = 2     # 한글 음절/영문/숫자가 최소 이만큼은 있어야 함

# 완성형 한글 음절 (가-힣), 영문, 숫자 = '의미 있는' 문자로 본다.
_MEANINGFUL_RE = re.compile(r"[가-힣A-Za-z0-9]")
# 한글 자모만(ㄱ-ㅎ, ㅏ-ㅣ) = "ㅁㄴㅇㄹ", "ㅋㅋㅋ" 같은 자모 도배
_JAMO_ONLY_RE = re.compile(r"^[ㄱ-ㅎㅏ-ㅣ\s]+$")


# ──────────────────────────────────────────────────────────────
# 1단계: 프롬프트 인젝션 / 탈옥 패턴
#   _normalize(소문자+공백제거) 후 부분일치로 검사하므로 패턴도 공백 없이 둔다.
#   ※ 오탐(정상 노동법 질문 차단)을 피하려고 '명백한' 공격 문구만 보수적으로 등록.
#     (예: "제한없이"는 "야근을 제한 없이 시켜요" 같은 정상 질문과 충돌하므로 제외)
# ──────────────────────────────────────────────────────────────
INJECTION_PATTERNS: List[str] = [
    # 지시/규칙 무력화 (한국어)
    "이전지시", "위의지시", "앞의지시", "이전대화무시", "이전내용무시",
    "지시무시", "지시를무시", "명령무시", "명령을무시",
    "규칙무시", "규칙을무시", "규칙을잊", "지침무시",
    "프롬프트무시", "프롬프트를무시", "시스템프롬프트", "시스템메시지",
    "지금까지의지시", "위내용은무시",
    # 역할/정체성 변경 (한국어)
    "역할을잊", "역할무시", "역할을바꿔", "너는이제", "넌이제",
    "지금부터너는", "지금부터넌", "개발자모드", "탈옥모드",
    "만능비서", "뭐든답하는", "빙의",
    # 제약/필터 해제 유도 (298개 평가에서 누수된 신규 표현 보강)
    #   ※ 노동법 질문엔 등장하지 않는 고유 토큰만 선별 (오탐 방지)
    "관리자권한", "모든제한", "제한해제", "제한을해제", "제한없이답",
    "필터를꺼", "필터꺼", "필터해제", "신경쓰지말고", "신경쓰지마",
    # 영어 변형
    "ignoreprevious", "ignoretheprevious", "ignoreabove", "ignoreallprevious",
    "disregardprevious", "disregardabove", "disregardthe",
    "youarenow", "youarenolonger", "actas", "pretendtobe",
    "jailbreak", "systemprompt", "developermode",
    "forgetyourinstructions", "forgetallprevious", "forgeteverything",
]


@dataclass
class GuardResult:
    """가드레일 판단 결과."""
    allowed: bool
    stage: str          # input_* | injection | keyword_allow | keyword_deny | embedding | fallback
    reason: str
    score: Optional[float] = None

    @property
    def message(self) -> str:
        """차단 시 사용자에게 보여줄 메시지 (stage별)."""
        return _STAGE_MESSAGE.get(self.stage, MSG_OFF_DOMAIN)


def refusal_payload(result: Optional["GuardResult"] = None) -> dict:
    """가드레일 차단 시 프론트로 그대로 내보낼 응답.

    result를 주면 stage에 맞는 메시지를, 안 주면 기본(off-domain) 메시지를 쓴다.
    """
    msg = result.message if result is not None else MSG_OFF_DOMAIN
    return {"reply": msg, "sources": [], "searchingDocs": []}


def _normalize(text: str) -> str:
    """소문자화 + 공백 제거 (프론트의 키워드 매칭 방식과 동일하게)."""
    return re.sub(r"\s+", "", text.lower())


# ──────────────────────────────────────────────────────────────
# 0단계: 입력 검증
# ──────────────────────────────────────────────────────────────
def _validate_input(question: str) -> Optional[GuardResult]:
    """비정상 입력이면 차단 GuardResult, 정상이면 None."""
    if question is None or not question.strip():
        return GuardResult(False, "input_empty", "빈 질문")

    stripped = question.strip()

    if len(stripped) > MAX_QUESTION_LENGTH:
        return GuardResult(False, "input_too_long",
                           f"입력 길이 {len(stripped)} > 한도 {MAX_QUESTION_LENGTH}")

    # 자모만 도배 ("ㅁㄴㅇㄹ", "ㅋㅋㅋ")
    if _JAMO_ONLY_RE.match(stripped):
        return GuardResult(False, "input_gibberish", "한글 자모만으로 구성")

    # 의미 있는 문자(완성 한글/영문/숫자)가 너무 적음 → 기호 도배/의미없는 입력
    meaningful = len(_MEANINGFUL_RE.findall(stripped))
    if meaningful < MIN_MEANINGFUL_CHARS:
        return GuardResult(False, "input_gibberish",
                           f"의미 있는 문자 {meaningful}개 (기호/공백 위주)")

    # 단일 문자 과다 반복 ("aaaaaaaa", "ㅋㅋㅋㅋㅋㅋ" 등) — 한 종류 문자가 90% 이상
    compact = re.sub(r"\s+", "", stripped)
    if len(compact) >= 6:
        most_common = max(compact.count(ch) for ch in set(compact))
        if most_common / len(compact) >= 0.9:
            return GuardResult(False, "input_gibberish", "동일 문자 과다 반복")

    return None


# ──────────────────────────────────────────────────────────────
# 1단계: 인젝션 탐지
# ──────────────────────────────────────────────────────────────
def _injection_check(question: str) -> Optional[GuardResult]:
    """프롬프트 인젝션/탈옥 패턴이 보이면 차단, 아니면 None."""
    norm = _normalize(question)
    for pat in INJECTION_PATTERNS:
        if pat in norm:
            return GuardResult(False, "injection", f"인젝션 패턴 '{pat}' 매칭")
    return None


# ──────────────────────────────────────────────────────────────
# 2단계: 키워드 사전
#   allowlist를 denylist보다 먼저 검사 → 오차단 최소화.
# ──────────────────────────────────────────────────────────────
ALLOW_KEYWORDS: List[str] = [
    # 임금/수당
    "임금", "급여", "월급", "시급", "일당", "주급", "연봉", "최저임금", "최저시급",
    "주휴", "주휴수당", "가산수당", "통상임금", "평균임금", "체불", "임금체불", "포괄임금",
    # 근로시간/휴식
    "근로시간", "소정근로", "주52시간", "연장근로", "야간근로", "휴일근로", "초과근무",
    "휴게", "휴일", "휴가", "연차", "월차", "결근", "지각", "조퇴",
    # 계약/신분
    "근로계약", "계약서", "수습", "인턴", "알바", "아르바이트", "파트타임",
    "정규직", "계약직", "비정규직", "일용직", "파견", "도급", "촉탁", "정년",
    "근로자", "사용자", "사업주", "노동자",
    # 퇴직/해고
    "퇴직", "퇴직금", "해고", "부당해고", "권고사직", "정리해고", "실업급여",
    "복직", "휴직",
    # 보호/복지
    "산재", "산업재해", "육아휴직", "출산휴가", "출산전후", "모성보호", "임산부",
    "연소근로", "청소년근로", "직장내괴롭힘", "성희롱", "4대보험", "고용보험",
    # 제도/기관
    "근로기준법", "노동법", "취업규칙", "단체협약", "노동조합", "노조",
    "고용노동부", "노동청", "근로감독", "노동위원회",
]

DENY_KEYWORDS: List[str] = [
    # 명백히 도메인 밖인 것만 보수적으로 (오차단 방지)
    "날씨", "기온", "미세먼지", "점심메뉴", "저녁메뉴", "메뉴추천",
    "영화", "드라마", "넷플릭스", "게임추천", "롤전적",
    "연애", "데이트", "썸", "이상형",
    "비트코인", "코인시세", "주식추천", "로또", "복권",
    "레시피", "요리법", "맛집", "여행지추천", "항공권", "호텔예약",
    "축구", "야구중계", "농구", "아이돌", "노래추천", "운세", "별자리", "타로",
    "농담해", "심심해", "사랑해", "넌누구", "너는누구야", "챗지피티",
]


def _keyword_check(question: str) -> Optional[GuardResult]:
    """2단계. 통과/차단이 명백하면 GuardResult, 애매하면 None."""
    norm = _normalize(question)
    for kw in ALLOW_KEYWORDS:
        if kw in norm:
            return GuardResult(True, "keyword_allow", f"allowlist 키워드 '{kw}' 매칭")
    for kw in DENY_KEYWORDS:
        if kw in norm:
            return GuardResult(False, "keyword_deny", f"denylist 키워드 '{kw}' 매칭")
    return None


# 3단계 임계값 — Chroma의 거리(distance) 기준. 값이 작을수록 질문이 법령과 가깝다.
#   best_distance <= threshold  → 통과(관련 있음)
#   best_distance >  threshold  → 차단(무관)
# 1.25는 run_guardrail_eval.py --sweep 으로 튜닝한 값(정확도 97.1%, 오차단 0).
# 오차단(정상 질문을 막는 것)은 회복 불가라 미차단보다 나쁘게 보고,
# 미차단은 RAG 체인이 '근거 없음'으로 한 번 더 거른다는 점을 고려해 오차단 0 지점 채택.
DEFAULT_THRESHOLD = 1.25

# similarity_search 콜러블의 반환 타입: [(문서텍스트, 거리score), ...]
SimilaritySearch = Callable[[str, int], Sequence[Tuple[str, float]]]


def check_domain(
    question: str,
    similarity_search: Optional[SimilaritySearch] = None,
    threshold: float = DEFAULT_THRESHOLD,
    *,
    fallback_allow: bool = True,
) -> GuardResult:
    """
    질문이 노동법 도메인인지(또한 안전한지) 판단한다.

    Args:
        question: 사용자 질문.
        similarity_search: 3단계용. (query, k) -> [(text, distance), ...] 콜러블.
            None이면 임베딩 단계를 건너뛰고 fallback_allow 값을 따른다.
        threshold: 3단계 거리 임계값. best_distance <= threshold 면 통과.
        fallback_allow: 임베딩을 못 쓸 때(애매한데 미연결) 기본 결정.
            정상 질문 오차단을 피하려고 기본 True(통과) — RAG가 근거 없으면 거부함.
    """
    # 0단계: 입력 검증
    invalid = _validate_input(question)
    if invalid is not None:
        return invalid

    # 1단계: 인젝션 탐지 (키워드보다 먼저)
    injection = _injection_check(question)
    if injection is not None:
        return injection

    # 2단계: 키워드
    kw = _keyword_check(question)
    if kw is not None:
        return kw

    # 3단계: 임베딩 유사도
    if similarity_search is None:
        return GuardResult(
            fallback_allow, "fallback", "임베딩 미연결 — fallback 결정 적용"
        )

    results = list(similarity_search(question, 3))
    if not results:
        return GuardResult(False, "embedding", "검색 결과 없음")

    best_distance = min(score for _text, score in results)
    allowed = best_distance <= threshold
    return GuardResult(
        allowed,
        "embedding",
        f"최근접 거리 {best_distance:.4f} {'<=' if allowed else '>'} 임계값 {threshold}",
        score=best_distance,
    )


def make_chroma_similarity_search(vectorstore) -> SimilaritySearch:
    """
    통합 단계용 헬퍼. Chroma vectorstore를 받아
    check_domain이 쓰는 (query, k) -> [(text, distance)] 콜러블로 감싼다.

    예)
        from app.rag.vectorstore import get_vectorstore
        from app.guardrails import check_domain, make_chroma_similarity_search
        search = make_chroma_similarity_search(get_vectorstore())
        result = check_domain(user_q, search)
    """
    def _search(query: str, k: int) -> List[Tuple[str, float]]:
        hits = vectorstore.similarity_search_with_score(query, k=k)
        return [(doc.page_content, float(score)) for doc, score in hits]

    return _search
