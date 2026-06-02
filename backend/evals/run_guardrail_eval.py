# backend/eval/run_guardrail_eval.py
"""
가드레일 평가 러너 

guardrail_testset.json 의 질문들을 가드레일에 통과시켜
정확도 / 오차단율 / 미차단율을 측정한다.

실행:
    # 1단계 키워드만 (의존성 0 — 지금 바로 실행 가능)
    python backend/eval/run_guardrail_eval.py

    # 2단계 임베딩까지 (venv + Chroma DB 빌드 후)
    python backend/eval/run_guardrail_eval.py --embedding

용어
    오차단(false block) : 노동법 질문(allow)인데 차단한 것 → 사용자가 답을 못 받음 (가장 나쁨)
    미차단(false pass)  : 무관 질문(block)인데 통과시킨 것 → 엉뚱한 답변 위험
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

# Windows 콘솔(cp949)에서도 한글이 깨지지 않도록 UTF-8 출력 강제
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# app 패키지를 import 할 수 있도록 backend/ 를 경로에 추가
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.guardrails import check_domain, make_chroma_similarity_search  # noqa: E402

TESTSET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guardrail_testset.json")


def load_cases() -> list[dict]:
    with open(TESTSET_PATH, encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    # edge 케이스 중 일부는 question을 코드로 생성한다 (JSON에 거대 문자열을 안 박기 위해).
    for c in cases:
        gen = c.get("generate")
        if gen == "empty":
            c["question"] = ""
        elif gen == "whitespace":
            c["question"] = "      "
        elif gen == "too_long":
            # MAX_QUESTION_LENGTH(2000) 초과하도록 생성. 노동법 단어를 일부러 포함시켜
            # '길이 검증이 키워드 통과보다 먼저' 작동하는지도 함께 검증한다.
            c["question"] = "주휴수당 계산법을 자세히 알려주세요. " * 150
    return cases


def build_similarity_search(use_embedding: bool, approx: bool = False):
    """--embedding 옵션이면 Chroma 기반 검색 콜러블을 만든다. 아니면 None.

    기본은 exact(전수 정확검색): DB의 전체 벡터를 한 번 읽어 numpy로 직접 거리를
    계산한다 → 결정적(매번 동일)이고 '참값' 최근접을 보장한다.
    approx=True면 Chroma의 HNSW(근사검색)를 쓰는데, 근사라서 프로세스를 새로 띄울
    때마다 진짜 최근접을 놓쳐 경계 케이스 판정이 ±1 흔들릴 수 있다(평가엔 부적합).
    ※ 거리 척도는 Chroma 기본값 'l2'(제곱 유클리드)와 동일하게 맞춘다.
    """
    if not use_embedding:
        return None
    from app.rag.embeddings import get_embedding_model
    from langchain_community.vectorstores import Chroma

    db_dir = os.path.join(BACKEND_DIR, "chroma_db")
    if not os.path.isdir(db_dir):
        raise SystemExit(
            f"Chroma DB가 없습니다: {db_dir}\n"
            "먼저 DB를 빌드하세요: cd backend/app/rag && python vectorstore.py"
        )
    print(f"Chroma 벡터 DB 로드 중... (검색: {'근사 HNSW' if approx else '정확 exact'})")
    emb = get_embedding_model()
    vs = Chroma(persist_directory=db_dir, embedding_function=emb)

    if approx:
        return make_chroma_similarity_search(vs)

    # exact: 전체 벡터를 한 번 읽어 제곱 유클리드 거리로 정확 최근접 계산
    import numpy as np
    data = vs._collection.get(include=["embeddings"])
    mat = np.asarray(data["embeddings"], dtype=np.float64)  # (N, d)

    def _search(query: str, k: int):
        qv = np.asarray(emb.embed_query(query), dtype=np.float64)
        dist = ((mat - qv) ** 2).sum(axis=1)          # Chroma 기본 'l2' = squared L2
        idx = np.argsort(dist)[:k]
        return [("", float(dist[i])) for i in idx]

    return _search


def collect_records(cases, similarity_search):
    """각 케이스를 한 번만 평가해 임계값과 무관한 '판단 근거'를 모은다.

    반환 레코드: {case, kind, score}
      kind="fixed"     : 키워드/빈질문/fallback 등 threshold와 무관하게 결정됨
                         (이때 score 자리에는 allowed(bool)를 넣음)
      kind="embedding" : 2단계. score = 최근접 거리 (작을수록 도메인에 가까움)
    이렇게 모아두면 sweep 때 임베딩 케이스만 임계값으로 다시 판정하면 되어
    DB를 재조회하지 않아 빠르다.
    """
    records = []
    # 임베딩 단계 case의 '원거리'를 얻기 위해, threshold를 매우 크게 줘서
    # 항상 통과시키되 result.score(거리)만 취한다. (거리는 threshold와 무관)
    for c in cases:
        r = check_domain(c["question"], similarity_search, threshold=float("inf"))
        if r.stage == "embedding":
            records.append({"case": c, "kind": "embedding", "score": r.score})
        else:
            records.append({"case": c, "kind": "fixed", "score": r.allowed})
    return records


def score_at_threshold(records, threshold):
    """주어진 임계값에서 (정확도, 오차단리스트, 미차단리스트)를 계산."""
    correct = 0
    false_block, false_pass = [], []
    for rec in records:
        c = rec["case"]
        if rec["kind"] == "embedding":
            allowed = rec["score"] <= threshold
        else:
            allowed = rec["score"]
        predicted = "allow" if allowed else "block"
        if predicted == c["expected"]:
            correct += 1
        elif c["expected"] == "allow":
            false_block.append((c, rec))
        else:
            false_pass.append((c, rec))
    return correct, false_block, false_pass


def run_sweep(records, lo=0.6, hi=1.5, step=0.05):
    """임계값을 훑어가며 정확도/오차단/미차단을 출력하고 최적값을 추천."""
    total = len(records)
    n_allow = sum(1 for r in records if r["case"]["expected"] == "allow")
    n_block = total - n_allow

    print("\n" + "=" * 60)
    print("  임계값 스윕 (거리 distance 기준 — 작을수록 도메인에 가까움)")
    print("=" * 60)
    print(f"  {'threshold':>9} | {'정확도':>10} | {'오차단':>8} | {'미차단':>8}")
    print("  " + "-" * 46)

    # 추천 정책: 오차단(정상질문 막힘)을 최우선으로 최소화하고, 그 다음 정확도 최대화.
    # 이유: 이 제품에서 오차단은 회복 불가(유저가 답을 못 받음)지만,
    #       미차단은 RAG 체인이 '근거 없음'으로 한 번 더 걸러주기 때문.
    best = None  # key=(-오차단수, 정확도)
    t = lo
    while t <= hi + 1e-9:
        correct, fb, fp = score_at_threshold(records, t)
        acc = correct / total
        print(f"  {t:>9.2f} | {correct:>3}/{total} ({acc:>5.1%}) | "
              f"{len(fb):>2}/{n_allow:<3} | {len(fp):>2}/{n_block:<3}")
        key = (-len(fb), correct)
        if best is None or key > best[0]:
            best = (key, t, correct, len(fb), len(fp))
        t += step

    _, bt, bcorrect, bfb, bfp = best
    print("  " + "-" * 46)
    print(f"  추천 임계값: {bt:.2f}  "
          f"(정확도 {bcorrect}/{total}, 오차단 {bfb}, 미차단 {bfp})")
    print("  ※ 정책: 오차단 최소화 우선 → 그 다음 정확도. (오차단은 회복 불가,")
    print("     미차단은 RAG 체인이 '근거 없음'으로 2차 차단하므로 덜 치명적)")
    print()


def print_distances(records):
    """임베딩 단계 케이스들의 거리 분포를 정렬해 보여준다 (분리 가능성 확인용)."""
    emb = [r for r in records if r["kind"] == "embedding"]
    emb.sort(key=lambda r: r["score"])
    print("\n" + "=" * 60)
    print("  임베딩 단계 케이스 거리 분포 (오름차순 — 위가 도메인에 가까움)")
    print("=" * 60)
    for r in emb:
        c = r["case"]
        tag = "통과대상(allow)" if c["expected"] == "allow" else "차단대상(block)"
        print(f"  {r['score']:>7.4f}  [{tag}]  {c['question']}")
    print()


def run_single(records, threshold):
    total = len(records)
    n_allow = sum(1 for r in records if r["case"]["expected"] == "allow")
    n_block = total - n_allow
    correct, false_block, false_pass = score_at_threshold(records, threshold)

    print("\n" + "=" * 56)
    print(f"  가드레일 평가 결과  (임계값 {threshold})")
    print("=" * 56)
    print(f"  전체 정확도 : {correct}/{total}  ({correct / total:.1%})")
    print(f"  오차단(false block): {len(false_block)}/{n_allow}  "
          f"({len(false_block) / n_allow:.1%} of 노동법 질문)")
    print(f"  미차단(false pass) : {len(false_pass)}/{n_block}  "
          f"({len(false_pass) / n_block:.1%} of 무관 질문)")

    # 카테고리별 정확도 (어느 유형에서 틀리는지 한눈에)
    cats = sorted({rec["case"].get("category", "?") for rec in records})
    print("\n  [카테고리별 정확도]")
    for cat in cats:
        recs = [r for r in records if r["case"].get("category") == cat]
        c_correct = 0
        for rec in recs:
            allowed = (rec["score"] <= threshold) if rec["kind"] == "embedding" else rec["score"]
            pred = "allow" if allowed else "block"
            if pred == rec["case"]["expected"]:
                c_correct += 1
        n = len(recs)
        bar = "■" * c_correct + "□" * (n - c_correct)
        print(f"    {cat:<16} {c_correct:>2}/{n:<2}  {bar}")

    if false_block:
        print("\n  [오차단] 노동법 질문인데 막힘 — 가장 시급히 고쳐야 함:")
        for c, rec in false_block:
            extra = f"거리 {rec['score']:.4f}" if rec["kind"] == "embedding" else rec["kind"]
            print(f"    - {c['question']}  ({c['category']}, {extra})")
    if false_pass:
        print("\n  [미차단] 차단 대상인데 통과:")
        for c, rec in false_pass:
            extra = f"거리 {rec['score']:.4f}" if rec["kind"] == "embedding" else rec["kind"]
            q = c["question"] if len(c["question"]) <= 40 else c["question"][:40] + "…"
            print(f"    - {q}  ({c['category']}, {extra})")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="가드레일 평가 러너. 기본은 3단계(임베딩 의미 필터)까지 모두 사용한다."
    )
    parser.add_argument("--keyword-only", action="store_true",
                        help="3단계 임베딩(의미 필터)을 끄고 0~2단계만 — 빠른 점검용. "
                             "off-domain 질문이 대부분 fallback 통과하므로 정확도가 낮게 나옴")
    parser.add_argument("--embedding", action="store_true",
                        help="(과거 호환용, 무시됨 — 임베딩은 이제 기본 ON)")
    parser.add_argument("--threshold", type=float, default=None,
                        help="3단계 거리 임계값 (기본: guardrails.DEFAULT_THRESHOLD)")
    parser.add_argument("--sweep", action="store_true",
                        help="임계값을 훑어가며 최적값 탐색 (임베딩 필요)")
    parser.add_argument("--distances", action="store_true",
                        help="임베딩 단계 케이스들의 거리 분포 출력 (임베딩 필요)")
    parser.add_argument("--approx", action="store_true",
                        help="정확검색 대신 Chroma HNSW 근사검색 사용 (결과가 실행마다 흔들릴 수 있음)")
    args = parser.parse_args()

    use_embedding = not args.keyword_only
    if (args.sweep or args.distances) and not use_embedding:
        raise SystemExit("--sweep / --distances 는 임베딩이 필요합니다. --keyword-only 와 함께 쓸 수 없습니다.")
    if args.keyword_only:
        print("⚠️  키워드 전용 모드: 3단계 의미 필터가 꺼져 off-domain 질문 대부분이 통과합니다 "
              "(정확도가 실제보다 낮게 나옴). 전체 평가는 플래그 없이 실행하세요.")

    cases = load_cases()
    similarity_search = build_similarity_search(use_embedding, approx=args.approx)
    records = collect_records(cases, similarity_search)

    if args.distances:
        print_distances(records)
    if args.sweep:
        run_sweep(records)
    if not args.sweep and not args.distances:
        from app.guardrails import DEFAULT_THRESHOLD
        threshold = args.threshold if args.threshold is not None else DEFAULT_THRESHOLD
        run_single(records, threshold)


if __name__ == "__main__":
    main()
