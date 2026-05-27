# backend/app/rag/vectorstore.py
import os
# 경고 메시지 숨기기 (선택 사항)
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from langchain_community.vectorstores import Chroma
# 방금 만든 embeddings.py에서 함수들을 가져옵니다.
from embeddings import get_embedding_model, load_and_chunk_pdf

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

if __name__ == "__main__":
    # 로컬 테스트용 실행
    create_vector_db()