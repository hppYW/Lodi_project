# ============================================================
# vectorstore.py — 벡터스토어 관리 모듈 (Re-ranking 포함)
# ============================================================
# [역할]
#   ChromaDB 벡터스토어를 로드하고, 유사도 점수 기반의
#   고도화된 검색(Re-ranking) 기능을 제공합니다.
#
# [Re-ranking이란?]
#   일반적인 벡터 검색은 상위 K개 문서를 그대로 반환합니다.
#   하지만 그 중에는 실제로 관련 없는 문서가 포함될 수 있습니다.
#
#   Re-ranking은 검색된 문서의 유사도 점수를 확인하고,
#   임계값(threshold) 이하인 문서를 제거하여
#   LLM에 전달되는 컨텍스트의 품질을 높입니다.
#
#   [효과]
#     - 관련 없는 문서로 인한 할루시네이션 감소
#     - LLM이 처리할 컨텍스트 양 감소 → 답변 품질 향상
#     - 토큰 사용량 절약
# ============================================================

import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from .embeddings import get_embeddings

load_dotenv()

# ── 벡터스토어 싱글톤 인스턴스 ──
# ChromaDB 로드는 비용이 크므로 한 번만 로드하여 재사용합니다.
_vectorstore_instance: Chroma | None = None


def load_vectorstore() -> Chroma:
    """
    ChromaDB 벡터스토어를 로드하여 반환합니다.
    싱글톤 패턴으로 중복 로드를 방지합니다.

    [싱글톤 패턴을 쓰는 이유]
      - ChromaDB 로드 시 임베딩 모델도 함께 초기화됨
      - 매 요청마다 로드하면 메모리 낭비 + 응답 지연
      - 한 번 로드 후 재사용하여 성능 최적화

    Returns:
        Chroma 벡터스토어 인스턴스
    """
    global _vectorstore_instance

    if _vectorstore_instance is None:
        chroma_dir = os.getenv("CHROMA_DIR", "./chroma_db")
        _vectorstore_instance = Chroma(
            persist_directory=chroma_dir,
            embedding_function=get_embeddings(),
        )

    return _vectorstore_instance


def search_with_reranking(
    query: str,
    k: int = 5,
    score_threshold: float = 0.3,
    top_n: int = 3,
) -> list[Document]:
    """
    유사도 점수 기반 Re-ranking이 적용된 문서 검색을 수행합니다.

    [검색 과정 — 3단계]
      1단계) 벡터 유사도로 상위 k개 문서 후보를 넉넉하게 검색
      2단계) 유사도 점수가 score_threshold 미만인 문서를 필터링하여 제거
      3단계) 점수 순으로 정렬 후 상위 top_n개만 최종 반환

    [파라미터 설계 근거]
      - k=5: 초기 후보를 넉넉하게 확보 (5개 중 관련 없는 문서 걸러내기 위함)
      - score_threshold=0.3: 실험적으로 0.3 미만은 거의 무관한 문서
        → 이 값은 팀원A의 데이터 적재 완료 후 실제 검색 결과를 보며 튜닝 필요
      - top_n=3: LLM 컨텍스트에 3개 문서면 충분한 근거 제공 가능
        → 너무 많으면 오히려 혼란, 너무 적으면 정보 부족

    Args:
        query: 검색 질문 (Query Rewriting 후의 최적화된 질문 권장)
        k: 초기 검색할 후보 문서 수
        score_threshold: 최소 유사도 점수 (0~1, 높을수록 엄격)
        top_n: 최종 반환할 문서 수

    Returns:
        관련성이 검증된 Document 리스트 (최대 top_n개)
    """
    vectorstore = load_vectorstore()

    # ── 1단계: 유사도 점수와 함께 검색 ──
    # similarity_search_with_relevance_scores 반환 형식:
    #   [(Document, score), (Document, score), ...]
    #   score는 0~1 범위이며, 높을수록 관련성이 높음
    results_with_scores = vectorstore.similarity_search_with_relevance_scores(
        query=query,
        k=k,
    )

    # ── 2단계: 점수 기반 필터링 (Re-ranking 핵심) ──
    # 유사도 점수가 임계값 미만인 문서는 노이즈이므로 제거
    # 예: score=0.15인 "부동산 관련법" 문서가 "주휴수당" 검색에 섞이는 것을 방지
    filtered = [
        (doc, score) for doc, score in results_with_scores
        if score >= score_threshold
    ]

    # ── 3단계: 점수 순 정렬 후 상위 N개 선택 ──
    # 가장 관련성 높은 문서가 컨텍스트 앞쪽에 오도록 내림차순 정렬
    # → LLM은 컨텍스트 앞부분에 더 집중하는 경향이 있음 (primacy bias)
    filtered.sort(key=lambda x: x[1], reverse=True)

    # Document 객체만 추출하여 반환 (점수 정보 제거)
    top_docs = [doc for doc, _score in filtered[:top_n]]

    return top_docs
