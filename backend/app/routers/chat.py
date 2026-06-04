# backend/app/routers/chat.py
"""
채팅 API 라우터.

[요청 흐름]
  POST /chat  { question, session_id }
        │
        ▼
    ① 가드레일 (guardrails.check_domain)
        │
        ├─ 차단 → 거부 메시지 즉시 반환
        │
        └─ 통과 ↓
    ② RAG 체인 (chain.get_rag_chain)
        │
        ▼
    ③ 응답 반환 { reply, sources, searchingDocs }
"""
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["chat"])


# ──────────────────────────────────────────────────────────────
# 요청/응답 스키마 (프론트엔드 data.ts의 KBEntry 구조와 동일)
# ──────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    """프론트에서 보내는 채팅 요청."""
    question: str
    session_id: str = "default"


class SourceItem(BaseModel):
    """출처 정보 — 프론트엔드 types.ts의 Source 인터페이스와 대응."""
    doc: str
    article: str
    highlight: bool = False
    quote: str | None = None


class ChatResponse(BaseModel):
    """프론트로 내보내는 채팅 응답."""
    reply: str
    sources: list[SourceItem]
    searchingDocs: list[str]


# ──────────────────────────────────────────────────────────────
# RAG 체인 & 가드레일 유사도 검색 — 지연 초기화 (서버 시작 시 무거운 로딩 방지)
# ──────────────────────────────────────────────────────────────
_rag_chain = None
_similarity_search = None


def _get_rag_chain():
    """RAG 체인을 최초 1회만 생성하고 이후 재사용."""
    global _rag_chain
    if _rag_chain is None:
        from ..rag.chain import get_rag_chain
        _rag_chain = get_rag_chain()
    return _rag_chain


def _get_similarity_search():
    """가드레일 3단계(임베딩 유사도)에 쓸 검색 콜러블을 생성."""
    global _similarity_search
    if _similarity_search is None:
        from ..rag.vectorstore import get_vectorstore
        from ..guardrails import make_chroma_similarity_search
        vs = get_vectorstore()
        _similarity_search = make_chroma_similarity_search(vs)
    return _similarity_search


# ──────────────────────────────────────────────────────────────
# POST /chat
# ──────────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    사용자 질문을 받아 가드레일 → RAG 체인 → 응답을 반환한다.
    """
    from ..guardrails import check_domain, refusal_payload

    # ── ① 가드레일 체크 ──
    # 임베딩 검색이 아직 준비 안 됐으면(DB 미빌드 등) None으로 넘겨서
    # 키워드 단계까지만 판단하고 fallback 허용 (서비스 중단 방지)
    try:
        sim_search = _get_similarity_search()
    except Exception:
        sim_search = None

    result = check_domain(req.question, sim_search)

    if not result.allowed:
        payload = refusal_payload(result)
        return ChatResponse(
            reply=payload["reply"],
            sources=[],
            searchingDocs=[],
        )

    # ── ② RAG 체인 호출 ──
    try:
        chain = _get_rag_chain()
        response = chain.invoke(
            {"input": req.question},
            config={"configurable": {"session_id": req.session_id}},
        )
        answer = response.get("answer", str(response)) if isinstance(response, dict) else str(response)
    except Exception as e:
        import traceback
        traceback.print_exc()
        answer = (
            "죄송합니다, 답변 생성 중 오류가 발생했습니다. "
            "잠시 후 다시 시도해 주세요."
        )

    return ChatResponse(
        reply=answer,
        sources=[],
        searchingDocs=[],
    )


# ──────────────────────────────────────────────────────────────
# DELETE /chat/session — 세션 초기화 (새 대화 시작 시 호출)
# ──────────────────────────────────────────────────────────────
@router.delete("/chat/session/{session_id}")
async def clear_session(session_id: str):
    """특정 세션의 대화 이력을 삭제한다."""
    from ..rag.memory import clear_session as _clear
    _clear(session_id)
    return {"status": "cleared", "session_id": session_id}
