# chain.py — RAG 체인 구성 모듈
# 역할: Retriever + LLM 연결, 할루시네이션 차단 프롬프트 설계, 대화 히스토리 포함 RAG 체인 반환

import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_core.runnables.history import RunnableWithMessageHistory
from .vectorstore import load_vectorstore
from .memory import get_session_history

load_dotenv()

SYSTEM_PROMPT = (
    "당신은 한국 노동법 전문 법률 어시스턴트 'Lodi'입니다.\n"
    "\n"
    "아래 규칙을 반드시 지켜주세요:\n"
    "\n"
    "1. 아래 [문서 내용]에서 찾은 내용만을 근거로 답변하세요.\n"
    "2. 문서에 없는 내용은 절대 지어내지 마세요.\n"
    "3. 답변 마지막에 반드시 출처 조항을 명시하세요. (예: 📄 근로기준법 제55조)\n"
    "4. 문서에서 관련 내용을 찾을 수 없는 경우, 반드시 다음 문장만 답하세요:\n"
    '   "해당 내용은 보유한 문서에서 찾을 수 없습니다. 고용노동부(☎ 1350)에 문의해 주세요."\n'
    "5. 한국어로, 알바생도 이해할 수 있게 쉽고 친절하게 답변하세요.\n"
    "6. 법 조항 번호가 애매하면 인용하지 마세요.\n"
    "\n"
    "[문서 내용]\n"
    "{context}"
)


def get_rag_chain():
    """RAG 체인을 생성하여 반환. 대화 히스토리 자동 관리 포함."""
    llm = HuggingFaceEndpoint(
        repo_id="Qwen/Qwen2.5-7B-Instruct",
        task="text-generation",
        max_new_tokens=1024,
        temperature=0.1,
        huggingfacehub_api_token=os.getenv("HUGGINGFACE_API_KEY"),
    )
    chat_llm = ChatHuggingFace(llm=llm)

    vectorstore = load_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    question_answer_chain = create_stuff_documents_chain(chat_llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

    return RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="answer",
    )
