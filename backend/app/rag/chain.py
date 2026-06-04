# ============================================================
# chain.py — RAG 체인 구성 모듈 (고도화 버전)
# ============================================================
# 이 모듈은 사용자의 노동법 질문에 대해 정확한 답변을 생성하는
# RAG(Retrieval-Augmented Generation) 파이프라인의 핵심입니다.
#
# [파이프라인 흐름도]
#
#   사용자 질문 ("알바 짤렸는데 돈 받을 수 있어?")
#       │
#       ▼
#   ① Query Rewriting ─── 구어체를 법률 용어로 변환
#       │                  → "아르바이트 부당해고 해고예고수당 청구 요건"
#       ▼
#   ② Retrieval + Re-ranking ─── 벡터 검색 후 관련성 낮은 문서 필터링
#       │                         → 근로기준법 제26조, 제27조 등 관련 조항만 선별
#       ▼
#   ③ Answer Generation ─── 할루시네이션 차단 프롬프트 + Few-shot으로 답변 생성
#       │                    → 법 조항 인용 + 쉬운 설명 + 출처 명시
#       ▼
#   최종 응답 반환
#
# [주요 설계 결정]
#   - Query Rewriting: 구어체/줄임말을 법률 용어로 변환하여 검색 정확도 향상
#   - Re-ranking: 유사도 점수 기반 필터링으로 무관한 문서 제거 (vectorstore.py)
#   - Few-shot 프롬프트: 답변 형식의 일관성과 품질 보장
#   - Sliding Window 메모리: 토큰 초과 방지를 위한 대화 이력 관리 (memory.py)
# ============================================================

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.documents import Document
from langchain_core.runnables.history import RunnableWithMessageHistory
from .vectorstore import get_vectorstore, search_with_reranking
from .memory import get_session_history

# backend/.env 에서 GOOGLE_API_KEY 로드
load_dotenv()


# ────────────────────────────────────────────────────────────
# 1. Query Rewriting (질문 재작성)
# ────────────────────────────────────────────────────────────
# 사용자의 구어체 질문을 법률 검색에 최적화된 형태로 변환합니다.
#
# [필요한 이유]
#   사용자가 입력하는 질문은 대부분 구어체입니다.
#   예: "알바 짤렸는데 돈 받을 수 있어?"
#
#   하지만 벡터 DB에 저장된 법률 문서는 공식 법률 용어로 작성되어 있습니다.
#   예: "사용자는 근로자를 해고하려면 30일 전에 예고하여야 한다"
#
#   구어체 질문을 그대로 검색하면 관련 조항을 놓칠 수 있으므로,
#   LLM을 활용해 법률 키워드 중심으로 재작성합니다.
#
# [동작 방식]
#   LLM에게 질문을 법률 키워드 중심으로 재작성하도록 지시합니다.
#   원래 질문의 의도는 보존하되, 검색에 유리한 형태로 변환합니다.
#   실패 시(네트워크 오류 등) 원본 질문을 그대로 사용하여 서비스를 유지합니다.

QUERY_REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "당신은 한국 노동법 검색 최적화 전문가입니다.\n"
     "사용자의 질문을 벡터 검색에 최적화된 형태로 재작성하세요.\n\n"
     "규칙:\n"
     "1. 구어체/줄임말을 정확한 법률 용어로 변환\n"
     "2. 핵심 법률 키워드를 포함\n"
     "3. 질문의 원래 의도를 반드시 보존\n"
     "4. 재작성된 질문만 출력 (설명 없이)\n\n"
     "변환 예시:\n"
     "- '알바 짤렸는데 돈 받을 수 있어?' → '아르바이트 부당해고 해고예고수당 청구 요건'\n"
     "- '월급 안 줌' → '임금 체불 미지급 근로기준법 위반'\n"
     "- '야근하면 돈 더 받아?' → '연장근로 야간근로 가산수당 통상임금 계산'\n"
     "- '계약서 안 쓰면 어떻게 됨?' → '근로계약서 미작성 서면 교부 의무 위반 벌칙'"
     ),
    ("human", "{input}")
])


# ────────────────────────────────────────────────────────────
# 2. 시스템 프롬프트 설계 (Few-shot 포함)
# ────────────────────────────────────────────────────────────
# [설계 원칙]
#   ① 할루시네이션 차단: 문서에 없는 내용은 절대 생성 금지
#   ② 출처 명시 강제: 모든 답변에 법 조항 번호 포함
#   ③ 사용자 친화적: 알바생도 이해할 수 있는 쉬운 한국어
#   ④ 질문 유형별 대응: 계산형/요건형/절차형에 맞는 답변 구조
#
# [Few-shot 예시를 넣는 이유]
#   규칙만 나열하면 LLM이 형식을 지키지 않는 경우가 많습니다.
#   실제 "좋은 답변" 예시를 보여줌으로써:
#     - 답변 형식의 일관성 확보
#     - 출처 표기 방법 학습
#     - 질문 유형별 응답 구조 이해
#   또한 "나쁜 답변" 예시를 통해 금지 행동을 명확히 합니다.

SYSTEM_PROMPT = (
    "당신은 한국 노동법 전문 법률 어시스턴트 'Lodi'입니다.\n"
    "\n"
    "━━━ 핵심 규칙 ━━━\n"
    "1. 아래 [문서 내용]에서 관련된 내용을 찾아 답변하세요.\n"
    "   조금이라도 관련된 내용이 있으면 그것을 활용하여 답변하세요.\n"
    "2. 문서에 전혀 관련 없는 주제일 때만 다음 문장으로 답하세요:\n"
    '   "해당 내용은 보유한 문서에서 찾을 수 없습니다. '
    '고용노동부(☎ 1350)에 문의해 주세요."\n'
    "3. 문서에 없는 내용을 지어내지 마세요.\n"
    "4. 답변 마지막에 출처 조항을 명시하세요. 형식: 📄 [법률명] 제○조\n"
    "5. 한국어로, 알바생도 이해할 수 있게 쉽고 친절하게 답변하세요.\n"
    "6. 답변은 300자 이내로 핵심만 간결하게 작성하세요.\n"
    "\n"
    "━━━ 질문 유형별 답변 가이드 ━━━\n"
    "• 계산형 질문 (예: 주휴수당 얼마?):\n"
    "  → 계산 공식을 단계별로 보여주고, 구체적 숫자 예시를 포함하세요.\n"
    "• 요건 확인형 (예: 퇴직금 받을 수 있나?):\n"
    "  → 필요 요건을 번호 리스트로 정리하고, 해당 여부 판단 기준을 제시하세요.\n"
    "• 절차/방법형 (예: 임금체불 신고 어떻게?):\n"
    "  → 단계별 절차를 순서대로 안내하세요.\n"
    "\n"
    "━━━ 좋은 답변 예시 (이 형식을 따르세요) ━━━\n"
    "[질문] 주 15시간 알바인데 주휴수당 받을 수 있나요?\n"
    "[답변]\n"
    "네, 받으실 수 있습니다!\n\n"
    "주휴수당을 받으려면 다음 조건을 충족해야 합니다:\n"
    "1. 1주 소정근로시간이 15시간 이상일 것\n"
    "2. 해당 주에 개근(결근 없이 출근)할 것\n\n"
    "주휴수당 계산법:\n"
    "• 1일 소정근로시간 × 시급 = 주휴수당\n"
    "• 예시: 하루 5시간, 시급 9,860원이면 → 5 × 9,860 = 49,300원\n\n"
    "📄 근로기준법 제55조 (휴일)\n"
    "📄 근로기준법 시행령 제30조 (주휴일)\n"
    "\n"
    "━━━ 나쁜 답변 예시 (이렇게 하지 마세요) ━━━\n"
    "❌ 문서에 없는 내용을 추측하여 답변\n"
    "❌ 출처 없이 법 조항 번호를 지어냄\n"
    "❌ '~일 수도 있습니다', '~인 것 같습니다' 같은 불확실한 표현\n"
    "\n"
    "[문서 내용]\n"
    "{context}"
)


# ────────────────────────────────────────────────────────────
# 3. LLM 인스턴스 생성
# ────────────────────────────────────────────────────────────

def _build_llm() -> ChatGoogleGenerativeAI:
    """
    Google Gemini LLM 인스턴스를 생성합니다.

    [모델: gemini-2.0-flash]
      - 한국어 성능 우수, 빠른 응답 속도
      - 무료 API 티어에서 사용 가능

    [temperature=0.1로 낮춘 이유]
      - 법률 도메인에서는 '창의성'이 곧 '할루시네이션'
      - 0.1로 설정하여 일관성 있고 보수적인 답변 유도

    Returns:
        ChatGoogleGenerativeAI 인스턴스 (대화형 LLM)
    """
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1,
        max_output_tokens=4096,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )


# ────────────────────────────────────────────────────────────
# 4. Query Rewriting 실행 함수
# ────────────────────────────────────────────────────────────

def _rewrite_query(chat_llm: ChatGoogleGenerativeAI, user_input: str) -> str:
    """
    사용자 질문을 검색에 최적화된 형태로 재작성합니다.

    LLM을 사용하여 구어체 질문을 법률 키워드 중심으로 변환합니다.
    네트워크 오류 등으로 실패하면 원본 질문을 그대로 반환하여
    서비스가 중단되지 않도록 합니다 (graceful degradation).

    Args:
        chat_llm: Google Gemini Chat 모델 인스턴스
        user_input: 사용자의 원본 질문

    Returns:
        검색에 최적화된 재작성 질문 문자열

    [변환 예시]
      입력: "주 3일 알바인데 주휴수당 받을 수 있나요?"
      출력: "주 3일 단시간 근로자 주휴수당 지급 요건 주 15시간 이상"
    """
    rewrite_chain = QUERY_REWRITE_PROMPT | chat_llm | StrOutputParser()
    try:
        rewritten = rewrite_chain.invoke({"input": user_input})
        return rewritten.strip()
    except Exception:
        # 재작성 실패 시 원본 질문을 그대로 사용 (서비스 중단 방지)
        return user_input


# ────────────────────────────────────────────────────────────
# 5. 문서 포맷팅 함수
# ────────────────────────────────────────────────────────────

def _format_docs(docs: list[Document]) -> str:
    """
    검색된 문서 리스트를 LLM에 전달할 컨텍스트 문자열로 변환합니다.

    [포맷 설계 의도]
      각 문서에 번호와 출처 메타데이터를 포함하여
      LLM이 답변 시 정확한 출처를 인용할 수 있도록 합니다.

      출력 예시:
        [문서 1] 근로기준법 제55조 (p.42)
        사용자는 근로자에게 1주일에 평균 1회 이상의 유급휴일을...
        ---
        [문서 2] 근로기준법 시행령 제30조 (p.15)
        ...

    Args:
        docs: 검색된 Document 객체 리스트

    Returns:
        포맷팅된 컨텍스트 문자열
    """
    formatted = []
    for i, doc in enumerate(docs, 1):
        # 메타데이터에서 출처 정보 추출
        # (팀원A가 데이터 적재 시 설계한 메타데이터 구조에 맞춤)
        source = doc.metadata.get("source", "출처 미상")
        page = doc.metadata.get("page", "")
        article = doc.metadata.get("article", "")

        # 문서 헤더 구성: [문서 번호] 법률명 조항 (페이지)
        header = f"[문서 {i}] {source}"
        if article:
            header += f" {article}"
        if page:
            header += f" (p.{page})"

        formatted.append(f"{header}\n{doc.page_content}")

    # 문서 간 구분선으로 분리하여 LLM이 각 문서를 명확히 구분하도록 함
    return "\n\n---\n\n".join(formatted)


# ────────────────────────────────────────────────────────────
# 6. RAG 체인 생성 (메인 함수)
# ────────────────────────────────────────────────────────────

def get_rag_chain():
    """
    고도화된 RAG 체인을 생성하여 반환합니다.

    [체인 구조도]
      ┌─────────────────┐
      │  사용자 질문 입력  │
      └───────┬─────────┘
              ▼
      ┌─────────────────┐
      │  Query Rewriting │  구어체 → 법률 용어 변환
      │  + Re-ranking    │  벡터 검색 → 관련성 필터링
      │  (context 생성)  │
      └───────┬─────────┘
              ▼
      ┌─────────────────┐
      │  프롬프트 조립     │  시스템 프롬프트 + 대화 이력 + 질문 + 컨텍스트
      └───────┬─────────┘
              ▼
      ┌─────────────────┐
      │  LLM 답변 생성    │  Google Gemini 2.0 Flash
      └───────┬─────────┘
              ▼
      ┌─────────────────┐
      │  응답 반환        │  {"input": ..., "answer": ..., "context": ...}
      └─────────────────┘

    [대화 히스토리 처리]
      RunnableWithMessageHistory가 세션 ID 기반으로 대화 이력을 자동 관리합니다.
      memory.py의 SlidingWindowHistory를 통해 최근 5턴만 유지하여 토큰 초과를 방지합니다.

    [사용 방법]
      chain = get_rag_chain()
      response = chain.invoke(
          {"input": "주휴수당 받을 수 있나요?"},
          config={"configurable": {"session_id": "user-123"}},
      )
      print(response["answer"])

    Returns:
        RunnableWithMessageHistory — 대화 히스토리가 자동 관리되는 RAG 체인
    """
    chat_llm = _build_llm()

    # ── 검색 함수 정의 ──
    # Query Rewriting → Re-ranking 검색 → 문서 포맷팅을 하나로 묶은 함수
    # RunnableLambda로 감싸서 LCEL 체인에 삽입합니다.
    def retrieve_with_rewriting(input_dict: dict) -> str:
        """
        사용자 질문을 재작성한 후, 관련성 높은 문서만 검색하여 반환합니다.

        [처리 흐름]
          1. 사용자 원본 질문에서 검색용 질문 생성 (Query Rewriting)
          2. 재작성된 질문으로 벡터 검색 수행 (Re-ranking 포함)
          3. 검색된 문서를 LLM이 읽을 수 있는 텍스트로 포맷팅
        """
        user_input = input_dict["input"]

        rewritten_query = _rewrite_query(chat_llm, user_input)
        print(f"[DEBUG] 원본: {user_input}")
        print(f"[DEBUG] 재작성: {rewritten_query}")

        relevant_docs = search_with_reranking(
            query=rewritten_query,
            k=10,
            score_threshold=1.5,
            top_n=5,
        )

        # 재작성 쿼리로 부족하면 원본으로도 검색해서 합침
        if len(relevant_docs) < 3 and rewritten_query != user_input:
            extra = search_with_reranking(
                query=user_input, k=10, score_threshold=1.5, top_n=5,
            )
            seen = {doc.page_content for doc in relevant_docs}
            for doc in extra:
                if doc.page_content not in seen:
                    relevant_docs.append(doc)
                    seen.add(doc.page_content)

        print(f"[DEBUG] 검색 결과: {len(relevant_docs)}개")
        for doc in relevant_docs:
            print(f"[DEBUG]   - {doc.page_content[:60]}")

        if not relevant_docs:
            return "(검색된 관련 문서가 없습니다)"

        context = _format_docs(relevant_docs)
        print(f"[DEBUG] 컨텍스트 길이: {len(context)}자")
        return context

    # ── 답변 생성 프롬프트 구성 ──
    # system: 할루시네이션 차단 규칙 + Few-shot 예시 + 검색된 문서(context)
    # chat_history: 이전 대화 이력 (MessagesPlaceholder로 자동 삽입)
    # human: 사용자의 현재 질문
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    # ── 전체 체인 조립 (LCEL 방식) ──
    #
    # LCEL(LangChain Expression Language)로 파이프라인을 선언적으로 구성합니다.
    #
    # RunnablePassthrough.assign(context=...) 동작 원리:
    #   1. 입력 딕셔너리를 그대로 통과시킴 (passthrough)
    #   2. retrieve_with_rewriting 함수 실행 결과를 "context" 키에 추가
    #   → {"input": "질문", "chat_history": [...]}
    #   → {"input": "질문", "chat_history": [...], "context": "검색 결과"}
    #
    # 두 번째 assign(answer=...)에서:
    #   prompt가 context, chat_history, input을 조합하여 프롬프트 생성
    #   → LLM이 답변 생성 → StrOutputParser가 문자열로 변환
    #   → 결과가 "answer" 키에 저장
    rag_chain = (
        RunnablePassthrough.assign(
            context=RunnableLambda(retrieve_with_rewriting)
        )
        | RunnablePassthrough.assign(
            answer=prompt | chat_llm | StrOutputParser()
        )
    )

    # ── 대화 히스토리 자동 관리 래핑 ──
    # RunnableWithMessageHistory가 하는 일:
    #   1. 체인 실행 전: session_id로 이전 대화 이력을 로드하여 chat_history에 삽입
    #   2. 체인 실행 후: 사용자 질문(input)과 AI 응답(answer)을 자동 저장
    #   → 다음 호출 시 이전 대화 맥락을 자동으로 이어받음
    return RunnableWithMessageHistory(
        rag_chain,
        get_session_history,                  # memory.py에서 세션 히스토리 조회
        input_messages_key="input",           # 사용자 입력이 담긴 키
        history_messages_key="chat_history",  # 대화 이력이 삽입될 키
        output_messages_key="answer",         # AI 응답이 담긴 키
    )
