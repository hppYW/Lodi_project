# vectorstore.py — 벡터스토어 관리 모듈
# 역할: ChromaDB 벡터스토어를 로드하여 Retriever로 사용할 수 있도록 반환

import os
from dotenv import load_dotenv
from langchain_chroma import Chroma
from .embeddings import get_embeddings

load_dotenv()


def load_vectorstore() -> Chroma:
    """ChromaDB 벡터스토어를 로드하여 반환."""
    chroma_dir = os.getenv("CHROMA_DIR", "./chroma_db")
    return Chroma(
        persist_directory=chroma_dir,
        embedding_function=get_embeddings(),
    )
