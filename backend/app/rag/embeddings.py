# backend/app/rag/embeddings.py
import re
import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

def get_embedding_model():
    return HuggingFaceEmbeddings(
        model_name="jhgan/ko-sroberta-multitask",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )

def clean_text(text: str) -> str:
    """PDF에서 긁어온 텍스트의 불순물(노이즈)을 정교하게 제거합니다."""
    # 1. 페이지 번호 및 머리말 제거 (예: "370/ 근로기준법 질의회시집", "258 / ...")
    text = re.sub(r'\d+\s*/\s*[가-힣\s]+.*?\n', '', text)
    # 2. 불필요하게 끊긴 줄바꿈을 하나로 병합 (단어 중간에 잘리는 현상 방지)
    text = re.sub(r'(?<=[가-힣,])\n(?=[가-힣])', ' ', text)
    # 3. 다중 줄바꿈 정리
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def load_and_chunk_pdf(file_path: str):
    print(f"[{os.path.basename(file_path)}] 텍스트 정제 및 의미론적 분할(Semantic Chunking) 중...")

    loader = PyPDFLoader(file_path)
    pages = loader.load()
    doc_title = os.path.basename(file_path).replace(".pdf", "")

    # 1. 문서 전체를 하나의 거대한 텍스트로 병합
    full_text = ""
    for page in pages:
        full_text += clean_text(page.page_content) + "\n\n"

    # 2. 1차 분할: 법 조항(제O조) 및 Q&A(질의/회시) 등 '의미 단위'로 쪼개기
    # 정규식 Lookahead(?=)를 사용하여 기준점(제O조 등)이 날아가지 않고 조각의 맨 앞에 붙도록 함
    semantic_chunks = re.split(r'(?=\n제\d+조|\n질의\s*:|\n회시\s*:|\nQ\.|\[질의\]|\[회시\])', full_text)

    # 3. 2차 분할: 의미 단위로 잘랐는데도 너무 긴 녀석들을 위한 안전장치
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", " "]
    )

    final_documents = []
    for chunk in semantic_chunks:
        chunk = chunk.strip()
        if len(chunk) < 20:  # 너무 짧은 쓰레기 조각(노이즈)은 버림
            continue

        # 💡 [전문가의 핵심 팁: Context Enrichment]
        # 조각만 덜렁 떼어놓으면 AI가 이게 무슨 법인지 모릅니다.
        # 모든 조각의 맨 앞에 "[근로기준법]" 처럼 출처 꼬리표를 강제로 달아줍니다.
        enriched_text = f"[{doc_title}]\n{chunk}"

        # 만약 조항 하나가 너무 길다면(1000자 초과) 한 번 더 예쁘게 자릅니다.
        sub_chunks = text_splitter.split_text(enriched_text)

        for sub in sub_chunks:
            final_documents.append(Document(
                page_content=sub,
                metadata={"source": doc_title} # 메타데이터에도 출처 기록
            ))

    print(f" └─> 총 {len(final_documents)}개의 고품질 텍스트 조각 생성 완료.")
    return final_documents

if __name__ == "__main__":
    current_file_path = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file_path)
    target_path = os.path.join(current_dir, "../../data/documents/근로기준법.pdf")
    pdf_path = os.path.normpath(target_path)

    if os.path.exists(pdf_path):
        chunks = load_and_chunk_pdf(pdf_path)
        print("\n--- 💎 정제된 첫 번째 조각 샘플 ---")
        print(chunks[0].page_content)
    else:
        print("\n🚨 PDF 파일을 찾을 수 없습니다.")