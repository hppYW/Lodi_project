# backend/app/rag/embeddings.py
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
import os

def get_embedding_model():
    # 무료이면서 한국어 성능이 뛰어난 로컬 임베딩 모델을 사용합니다.
    return HuggingFaceEmbeddings(
        model_name="jhgan/ko-sroberta-multitask",
        model_kwargs={'device': 'cpu'}, # 컴퓨터에 GPU가 있다면 'cuda'로 변경
        encode_kwargs={'normalize_embeddings': True}
    )

def load_and_chunk_pdf(file_path: str):
    print(f"[{file_path}] 문서를 불러오는 중...")

    # 1. PDF 불러오기
    loader = PyPDFLoader(file_path)
    documents = loader.load()

    # 2. 텍스트 분할하기 (Chunking)
    # 법률 문서는 조항이 잘리지 않도록 chunk_size를 넉넉하게 잡는 것이 좋습니다.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n제", "\n\n", "\n", " ", ""] # '제O조' 단위로 잘리도록 유도
    )

    chunks = text_splitter.split_documents(documents)
    print(f"총 {len(chunks)}개의 텍스트 조각으로 분할되었습니다.")

    return chunks

# --- 로컬 테스트용 실행 코드 ---
if __name__ == "__main__":
    import os

    # 1. 현재 실행 중인 파이썬 파일(embeddings.py)의 절대 경로를 가져옵니다.
    current_file_path = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file_path) # app/rag/ 폴더 위치

    # 2. 현재 파일 위치를 기준으로 문서를 찾아갑니다. (가장 안전한 실무 방식)
    # app/rag -> app -> backend -> data/documents
    target_path = os.path.join(current_dir, "../../data/documents/근로기준법.pdf")
    pdf_path = os.path.normpath(target_path) # 경로를 OS에 맞게 깔끔하게 정리해줍니다.

    print(f"👀 시스템이 찾고 있는 파일 경로: {pdf_path}")

    if os.path.exists(pdf_path):
        chunks = load_and_chunk_pdf(pdf_path)
        print("\n--- 첫 번째 조각 샘플 ---")
        print(chunks[0].page_content)
    else:
        print("\n🚨 경로에 PDF 파일이 없습니다. 파일명이나 폴더 구조를 다시 확인해주세요.")