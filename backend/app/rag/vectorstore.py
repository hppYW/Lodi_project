# backend/app/rag/vectorstore.py
import os
import shutil
import warnings
# 자잘한 라이브러리 버전 경고창 때문에 터미널 로그가 더러워지는 걸 막기 위해 무시 처리
warnings.filterwarnings("ignore", category=DeprecationWarning)

from langchain_community.vectorstores import Chroma
from .embeddings import get_embedding_model, load_and_chunk_pdf

def create_vector_db():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    doc_dir = os.path.normpath(os.path.join(current_dir, "../../data/documents"))
    db_dir = os.path.normpath(os.path.join(current_dir, "../../chroma_db"))

    # 개발 중 데이터 파이프라인을 수정할 때마다 과거 쓰레기 데이터와 섞이는 문제가 있었음.
    # 안전한 테스트를 위해 DB 생성 시 무조건 폴더를 싹 밀고 새로 만들도록 로직 구성.
    if os.path.exists(db_dir):
        print("🗑️ 기존 오염된 ChromaDB를 삭제하고 초기화합니다...")
        shutil.rmtree(db_dir)

    all_chunks = []
    print("📚 문서 폴더 탐색 및 데이터 파이프라인 가동...")
    for filename in os.listdir(doc_dir):
        if filename.endswith(".pdf"):
            file_path = os.path.join(doc_dir, filename)
            chunks = load_and_chunk_pdf(file_path) # embeddings.py에서 만든 텍스트 정제 함수 호출
            all_chunks.extend(chunks)

    print(f"\n🚀 총 {len(all_chunks)}개의 정제된 텍스트 조각을 벡터 DB에 적재합니다...")
    embedding_model = get_embedding_model()

    # 준비된 조각들을 임베딩 모델로 숫자로 변환한 뒤 Chroma DB 폴더에 영구 저장(persist)
    vectorstore = Chroma.from_documents(
        documents=all_chunks,
        embedding=embedding_model,
        persist_directory=db_dir
    )

    print(f"✅ 최고 품질의 벡터 DB 구축이 완료되었습니다! (저장 위치: {db_dir})")
    return vectorstore

def get_vectorstore():
    # 서버 기동 시 저장된 DB를 불러오는 유틸리티 함수
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.normpath(os.path.join(current_dir, "../../chroma_db"))
    embedding_model = get_embedding_model()
    return Chroma(persist_directory=db_dir, embedding_function=embedding_model)


def _invoke_llm_safely(prompt_text: str) -> str:
    """
    백그라운드에서 동기/비동기 충돌 없이 안전하게 Upstage LLM을 찔러보는 유틸리티.
    주로 사용자의 질문에 살을 붙이는 '쿼리 확장(Query Expansion)'에 쓰임.
    """
    import asyncio
    from langchain_upstage import ChatUpstage
    import os

    # FastAPI의 메인 이벤트 루프와 꼬이지 않도록 독립적인 이벤트 루프를 생성해서 던짐.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # 단어 유의어만 뽑아낼 거라 temperature는 0으로 줘서 딱딱하게 대답하게 세팅.
        llm = ChatUpstage(
            model="solar-1-mini-chat",
            temperature=0,
            max_retries=1,
            api_key=os.getenv("UPSTAGE_API_KEY")
        )
        response = llm.invoke(prompt_text)
        return response.content.replace("'", "").replace('"', '').strip()
    except Exception as e:
        print(f"🚨 LLM API 호출 에러: {e}")
        return ""
    finally:
        loop.close()

# 💡 [데이터 엔지니어 튜닝 포인트] top_n을 5에서 8로 늘려 LLM에게 더 풍부한 단서 제공
def search_with_reranking(query: str, k: int = 15, score_threshold: float = 1.5, top_n: int = 8):
    """
    사용자의 짧고 구어체인 질문을 풍성하게 만들어주고, 정확한 문서를 필터링해주는 고도화된 검색 함수
    [동작 흐름: 쿼리 확장 -> 1차 벡터 검색(Recall) -> 2차 키워드 필터링(Precision)]
    """
    import re
    vs = get_vectorstore()

    print(f"\n🧠 [Query Expansion] 원본 질문: {query}")

    # 1단계: 사용자가 "돈 안줌" 이라고 대충 쳐도 LLM이 "임금체불", "미지급" 같은 법률 용어를 뽑아주도록 지시함
    prompt = (
        "당신은 대한민국 노동법 전문 노무사입니다. "
        f"사용자의 질문 '{query}'과(와) 관련된 근로기준법상 공식 법률 용어(유의어/동의어)를 3개만 쉼표로 구분하여 출력하세요. "
        "설명이나 서론 없이 단어만 출력하세요. (예시: 유급휴일, 연차유급휴가, 평균임금)"
    )

    synonyms = _invoke_llm_safely(prompt)

    if synonyms:
        expanded_query = f"{query} {synonyms}"
        print(f"✨ [Query Expansion] 확장된 질문: {expanded_query}\n")
    else:
        print("⚠️ 쿼리 확장 실패 (원본으로 검색 진행)")
        expanded_query = query

    # 2단계: 유의어가 추가된 풍성한 문장으로 1차 벡터 검색 수행 (일단 넉넉하게 k개 가져옴)
    results = vs.similarity_search_with_score(expanded_query, k=k)

    # 3단계: 가져온 문서들 중 진짜 질문 속 핵심 단어(명사)가 포함된 녀석들만 점수를 깎아주는 방식(Re-ranking) 적용.
    # 점수가 낮을수록 문서가 질문과 가깝다는 의미임(거리 기반).
    docs = []
    keywords = re.findall(r"[가-힣]{2,}", query)

    for doc, score in results:
        if score <= score_threshold: # 터무니없는 문서는 여기서 1차 컷
            match_count = sum(1 for kw in keywords if kw in doc.page_content)
            # 매칭되는 단어가 많을수록 거리를 좁혀줌 (점수를 낮춤)
            docs.append({"doc": doc, "score": score - (match_count * 0.2)})

    docs.sort(key=lambda x: x["score"])
    final_docs = [item["doc"] for item in docs[:top_n]]

    # 4단계: 벡터 검색이 아예 실패해서 문서가 하나도 안 나왔을 때를 대비한 최후의 보루.
    # 단순 무식하게 질문에 들어있는 핵심 단어로 하드코딩 매칭(키워드 검색)을 시도함.
    if not final_docs:
        seen = set()
        for kw in keywords:
            if kw in ["계산", "방법", "기준", "산정", "어떻게"]: continue # 이런 불용어는 검색 안함
            try:
                kw_results = vs.get(where_document={"$contains": kw}, include=["documents"])
                if kw_results and kw_results["documents"]:
                    from langchain_core.documents import Document
                    for content in kw_results["documents"][:3]:
                        if content not in seen:
                            final_docs.append(Document(page_content=content))
                            seen.add(content)
                            if len(final_docs) >= top_n: break
            except Exception:
                continue
            if len(final_docs) >= top_n: break

    return final_docs[:top_n]

if __name__ == "__main__":
    create_vector_db()