# backend/app/rag/embeddings.py
import re
import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

def get_embedding_model():
    # 문장 임베딩 모델 로드. 한국어 법률/질의응답 처리에 성능이 좋은 ko-sroberta 모델을 선택함.
    # GPU가 없는 환경에서도 돌아가도록 기본 디바이스를 cpu로 설정.
    return HuggingFaceEmbeddings(
        model_name="jhgan/ko-sroberta-multitask",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )

def clean_text(text: str) -> str:
    """PDF에서 긁어온 텍스트에서 검색 정확도를 떨어뜨리는 불순물(노이즈)을 정교하게 제거하는 함수"""
    # 1. 페이지 상/하단에 반복적으로 찍히는 쪽수와 책 제목 제거 (예: "370/ 근로기준법 질의회시집")
    text = re.sub(r'\d+\s*/\s*[가-힣\s]+.*?\n', '', text)

    # 2. PDF 특성상 문장 중간에서 강제로 줄이 바뀌는(엔터가 쳐지는) 현상이 발생함.
    # 이대로 DB에 넣으면 검색 키워드가 끊기기 때문에, 한글과 한글 사이에 있는 줄바꿈은 띄어쓰기로 합쳐줌.
    text = re.sub(r'(?<=[가-힣,])\n(?=[가-힣])', ' ', text)

    # 3. 쓸데없이 엔터가 여러 번 쳐져 있는 공백 구간 정리 (가독성 향상)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def load_and_chunk_pdf(file_path: str):
    # 문서의 파일명을 나중에 출처(Source) 메타데이터로 쓰기 위해 미리 뽑아둠 (.pdf 확장자 제거)
    doc_title = os.path.basename(file_path).replace(".pdf", "")
    print(f"[{doc_title}] 텍스트 정제 및 의미론적 분할(Semantic Chunking) 중...")

    loader = PyPDFLoader(file_path)
    pages = loader.load()

    # 페이지 단위로 쪼개진 텍스트를 하나로 쭉 이어붙임. (법조문이 페이지를 넘어가면서 잘리는 걸 방지하기 위함)
    full_text = ""
    for page in pages:
        full_text += clean_text(page.page_content) + "\n\n"

    # [가장 핵심적인 데이터 파이프라인] 1차 분할: 단순 글자 수가 아닌 '의미 단위'로 자르기
    # 정규식의 전방탐색(?=)을 써서 "제55조" 같은 기준점이 날아가지 않고 다음 조각의 맨 앞에 딱 붙도록 처리함.
    semantic_chunks = re.split(r'(?=\n제\d+조|\n질의\s*:|\n회시\s*:|\nQ\.|\[질의\]|\[회시\])', full_text)

    # 2차 분할: 의미 단위로 잘랐는데도 특정 법조항이나 답변이 너무 길면 LLM이 읽다가 지침.
    # 이 녀석들을 1000자 단위로 예쁘게 자르되, 문맥이 안 끊기게 앞뒤 200자씩 겹쳐서 자름(overlap).
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", " "]
    )

    final_documents = []
    for chunk in semantic_chunks:
        chunk = chunk.strip()
        # 노이즈 제거 후 남은 찌꺼기 텍스트(예: "1.", "-")들은 DB 용량만 차지하므로 버림
        if len(chunk) < 20:
            continue

        # AI에게 "이 내용은 이 문서에서 온 거야"라고 맥락을 심어주기 위해 조각 맨 앞에 강제로 문서 제목을 박아줌 (Context Enrichment)
        enriched_text = f"[{doc_title}]\n{chunk}"

        # 1000자 넘는 긴 텍스트 분할 실행
        sub_chunks = text_splitter.split_text(enriched_text)

        # 쪼개진 조각들을 Document 객체로 포장하고 메타데이터(출처)를 달아서 리스트에 차곡차곡 담음
        for sub in sub_chunks:
            final_documents.append(Document(
                page_content=sub,
                metadata={"source": doc_title}
            ))

    print(f" └─> 총 {len(final_documents)}개의 고품질 텍스트 조각 생성 완료.")
    return final_documents

if __name__ == "__main__":
    # 이 파일만 단독으로 실행했을 때 잘 돌아가는지 확인하기 위한 테스트 코드
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