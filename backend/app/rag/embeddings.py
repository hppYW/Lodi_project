# embeddings.py — 임베딩 모델 관리 모듈
# 역할: HuggingFace 한국어 임베딩 모델(ko-sroberta-multitask)을 로드하여 반환

from langchain_huggingface import HuggingFaceEmbeddings

EMBEDDING_MODEL_NAME = "jhgan/ko-sroberta-multitask"


def get_embeddings() -> HuggingFaceEmbeddings:
    """한국어 임베딩 모델 인스턴스를 반환."""
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
