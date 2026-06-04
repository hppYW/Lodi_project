# backend/app/rag/vectorstore.py
import os
import shutil
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from langchain_community.vectorstores import Chroma
from .embeddings import get_embedding_model, load_and_chunk_pdf

def create_vector_db():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    doc_dir = os.path.normpath(os.path.join(current_dir, "../../data/documents"))
    db_dir = os.path.normpath(os.path.join(current_dir, "../../chroma_db"))

    # 🚨 [매우 중요] 기존에 오염된 가짜 데이터베이스 완전 삭제
    if os.path.exists(db_dir):
        print("🗑️ 기존 오염된 ChromaDB를 삭제하고 초기화합니다...")
        shutil.rmtree(db_dir)

    all_chunks = []
    print("📚 문서 폴더 탐색 및 데이터 파이프라인 가동...")
    for filename in os.listdir(doc_dir):
        if filename.endswith(".pdf"):
            file_path = os.path.join(doc_dir, filename)
            chunks = load_and_chunk_pdf(file_path)
            all_chunks.extend(chunks)

    print(f"\n🚀 총 {len(all_chunks)}개의 정제된 텍스트 조각을 벡터 DB에 적재합니다...")
    embedding_model = get_embedding_model()

    vectorstore = Chroma.from_documents(
        documents=all_chunks,
        embedding=embedding_model,
        persist_directory=db_dir
    )

    print(f"✅ 최고 품질의 벡터 DB 구축이 완료되었습니다! (저장 위치: {db_dir})")
    return vectorstore

def get_vectorstore():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.normpath(os.path.join(current_dir, "../../chroma_db"))
    embedding_model = get_embedding_model()
    return Chroma(persist_directory=db_dir, embedding_function=embedding_model)

# backend/app/rag/vectorstore.py (하단 부분 교체)

def _invoke_llm_safely(prompt_text: str) -> str:
    import asyncio
    from langchain_upstage import ChatUpstage  # 👈 변경
    import os

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # 👇 변경
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

def search_with_reranking(query: str, k: int = 15, score_threshold: float = 1.5, top_n: int = 5):
    """
    [Level 1 아키텍처] LLM 동적 쿼리 확장 + 벡터 검색 + 키워드 랭킹
    """
    import re
    vs = get_vectorstore()

    print(f"\n🧠 [Query Expansion] 원본 질문: {query}")

    # 💡 1단계: 안전한 함수를 통해 LLM 호출
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

        # 💡 2단계: 확장된 쿼리로 벡터 검색 진행
    results = vs.similarity_search_with_score(expanded_query, k=k)

    # 💡 3단계: 핵심 명사 강제 필터링 (Re-ranking)
    docs = []
    keywords = re.findall(r"[가-힣]{2,}", query)

    for doc, score in results:
        if score <= score_threshold:
            match_count = sum(1 for kw in keywords if kw in doc.page_content)
            docs.append({"doc": doc, "score": score - (match_count * 0.2)})

    docs.sort(key=lambda x: x["score"])
    final_docs = [item["doc"] for item in docs[:top_n]]

    # 💡 4단계: 벡터 검색이 실패했을 때의 최후의 보루 (단어 매칭)
    if not final_docs:
        seen = set()
        for kw in keywords:
            if kw in ["계산", "방법", "기준", "산정", "어떻게"]: continue
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