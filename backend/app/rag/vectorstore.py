# backend/app/rag/vectorstore.py
import os
# 경고 메시지 숨기기 (선택 사항)
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from langchain_community.vectorstores import Chroma
# 방금 만든 embeddings.py에서 함수들을 가져옵니다.
from .embeddings import get_embedding_model, load_and_chunk_pdf

def create_vector_db():
    # 1. 경로 설정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    doc_dir = os.path.normpath(os.path.join(current_dir, "../../data/documents"))
    db_dir = os.path.normpath(os.path.join(current_dir, "../../chroma_db")) # DB가 저장될 폴더

    all_chunks = []

    # 2. documents 폴더 안의 '모든' PDF 파일 읽어오기
    print("📚 문서 폴더를 탐색합니다...")
    for filename in os.listdir(doc_dir):
        if filename.endswith(".pdf"):
            file_path = os.path.join(doc_dir, filename)
            # embeddings.py의 함수 재사용
            chunks = load_and_chunk_pdf(file_path)
            all_chunks.extend(chunks)

    print(f"\n총 {len(all_chunks)}개의 텍스트 조각을 벡터 DB로 변환합니다. (시간이 조금 걸릴 수 있습니다...)")

    # 3. 벡터 DB (Chroma) 생성 및 로컬 저장
    embedding_model = get_embedding_model()

    # ChromaDB에 데이터 삽입 (자동으로 db_dir에 파일로 저장됨)
    vectorstore = Chroma.from_documents(
        documents=all_chunks,
        embedding=embedding_model,
        persist_directory=db_dir
    )

    print(f"✅ 벡터 DB 구축이 완료되었습니다! (저장 위치: {db_dir})")
    return vectorstore

def get_vectorstore():
    """나중에 챗봇이 검색을 위해 DB를 불러올 때 사용할 함수"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.normpath(os.path.join(current_dir, "../../chroma_db"))
    embedding_model = get_embedding_model()

    # 저장된 로컬 DB 불러오기
    return Chroma(persist_directory=db_dir, embedding_function=embedding_model)


def search_with_reranking(
    query: str,
    k: int = 5,
    score_threshold: float = 0.3,
    top_n: int = 3,
):
    """
    벡터 검색 후 유사도 점수 기반으로 관련성 낮은 문서를 필터링합니다.

    [동작 방식]
      1. Chroma에서 k개 후보 문서를 유사도 점수와 함께 검색
      2. score_threshold 이상인 문서만 남김 (낮을수록 유사 — Chroma L2 거리 기준)
      3. 상위 top_n개만 최종 반환

    Args:
        query: 검색 질문 (Query Rewriting 된 법률 키워드 중심 문장)
        k: 초기 후보 문서 개수
        score_threshold: 이 거리 이하인 문서만 통과 (작을수록 엄격)
        top_n: 최종 반환할 문서 수
    Returns:
        관련성 높은 Document 리스트
    """
    vs = get_vectorstore()
    # similarity_search_with_score: (Document, distance) 쌍 반환
    # Chroma 기본 L2 거리 — 값이 작을수록 유사
    results = vs.similarity_search_with_score(query, k=k)

    # 거리 기준 필터링: threshold 이하만 통과
    filtered = [(doc, score) for doc, score in results if score <= score_threshold]

    # 거리 오름차순 정렬 후 상위 top_n개 반환
    filtered.sort(key=lambda x: x[1])
    return [doc for doc, _score in filtered[:top_n]]


if __name__ == "__main__":
    # 로컬 테스트용 실행
    create_vector_db()