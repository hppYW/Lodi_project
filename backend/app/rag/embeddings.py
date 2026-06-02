# ============================================================
# embeddings.py — 임베딩 모델 관리 모듈
# ============================================================
# [역할]
#   텍스트를 벡터(숫자 배열)로 변환하는 임베딩 모델을 관리합니다.
#   벡터스토어 검색과 문서 저장 모두에서 동일한 모델이 사용되어야 하므로
#   이 모듈에서 단일 진입점을 제공합니다.
#
# [모델 선택: ko-sroberta-multitask]
#   - 한국어 문장 임베딩에 특화된 SBERT 기반 모델
#   - 다국어 모델(multilingual-e5 등) 대비 한국어 의미 유사도 측정 성능 우수
#   - 768차원 벡터 출력, 빠른 추론 속도
#   - 법률 문서의 조항 간 의미적 유사성을 잘 포착
#
# [주의사항]
#   팀원A(데이터 엔지니어)가 ChromaDB에 문서를 적재할 때와
#   검색 시 반드시 동일한 임베딩 모델을 사용해야 합니다.
#   모델이 다르면 벡터 공간이 달라져 검색 결과가 엉망이 됩니다.
# ============================================================

from langchain_huggingface import HuggingFaceEmbeddings

# ── 임베딩 모델 설정 ──
# jhgan/ko-sroberta-multitask: 한국어 특화 Sentence-BERT 모델
# HuggingFace Hub에서 자동 다운로드 (최초 실행 시 약 500MB)
EMBEDDING_MODEL_NAME = "jhgan/ko-sroberta-multitask"

# 싱글톤 인스턴스 (모델 로드 비용이 크므로 한 번만 초기화)
_embeddings_instance: HuggingFaceEmbeddings | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    한국어 임베딩 모델 인스턴스를 반환합니다.
    싱글톤 패턴으로 중복 초기화를 방지합니다.

    [싱글톤을 사용하는 이유]
      임베딩 모델은 초기 로드 시 약 500MB 모델을 메모리에 올립니다.
      매번 새로 생성하면 메모리 낭비와 응답 지연이 발생하므로,
      한 번 생성한 인스턴스를 재사용합니다.

    Returns:
        HuggingFaceEmbeddings 인스턴스
    """
    global _embeddings_instance

    if _embeddings_instance is None:
        _embeddings_instance = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            # model_kwargs: 모델 로드 시 전달할 추가 설정
            # device="cpu" → GPU가 없는 환경에서도 동작 (필요시 "cuda"로 변경)
            model_kwargs={"device": "cpu"},
            # encode_kwargs: 임베딩 생성 시 전달할 추가 설정
            # normalize_embeddings=True → 벡터를 정규화하여 코사인 유사도 계산 최적화
            encode_kwargs={"normalize_embeddings": True},
        )

    return _embeddings_instance
