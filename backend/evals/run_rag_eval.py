# backend/evals/run_rag_eval.py
"""
RAG 체인 답변 품질 평가 러너

rag_testset.json의 질문들을 RAG 체인에 통과시켜
키워드 포함률 / 법 조항 인용률 / 거부 정확률을 측정한다.

평가 항목:
  keyword_pass  : expected_keywords가 답변에 모두 포함됐는가
  law_pass      : expected_law가 답변에 인용됐는가 (null이면 검사 생략)
  refusal_pass  : should_refuse=true일 때 올바르게 거부했는가
  overall_pass  : 위 항목 모두 통과

실행:
    cd backend
    python -m evals.run_rag_eval                     # 전체 평가
    python -m evals.run_rag_eval --category 주휴수당  # 특정 카테고리만
    python -m evals.run_rag_eval --verbose           # 각 답변 전문 출력
    python -m evals.run_rag_eval --fail-only         # 실패 케이스만 출력
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

TESTSET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_testset.json")
REFUSAL_MARKERS = ["찾을 수 없습니다", "고용노동부(☎ 1350)", "1350"]


# ──────────────────────────────────────────────────────────────
# 체인 로드
# ──────────────────────────────────────────────────────────────
def load_chain():
    print("RAG 체인 로드 중... (임베딩 모델 + ChromaDB + LLM 초기화)")
    from app.rag.chain import get_rag_chain
    chain = get_rag_chain()
    print("체인 로드 완료.\n")
    return chain


# ──────────────────────────────────────────────────────────────
# 단일 케이스 평가
# ──────────────────────────────────────────────────────────────
def evaluate_case(chain, case: dict) -> dict:
    session_id = f"eval_{uuid.uuid4().hex}"
    try:
        response = chain.invoke(
            {"input": case["question"]},
            config={"configurable": {"session_id": session_id}},
        )
        answer = response.get("answer", str(response)) if isinstance(response, dict) else str(response)
    except Exception as exc:
        answer = f"[ERROR] {exc}"

    failures: list[str] = []

    # 1. 키워드 체크
    missing_kw = [kw for kw in case.get("expected_keywords", []) if kw not in answer]
    if missing_kw:
        failures.append(f"키워드 누락: {missing_kw}")

    # 2. 법 조항 인용 체크
    law = case.get("expected_law")
    if law and law not in answer:
        failures.append(f"법 조항 미인용: '{law}'")

    # 3. 거부 여부 체크
    if case.get("should_refuse"):
        if not any(m in answer for m in REFUSAL_MARKERS):
            failures.append("거부 미반환 — 문서 밖 질문에 답변함")

    return {
        "question": case["question"],
        "category": case["category"],
        "description": case.get("description", ""),
        "answer": answer,
        "passed": len(failures) == 0,
        "failures": failures,
        "keyword_pass": not missing_kw,
        "law_pass": (law is None) or (law in answer),
        "refusal_pass": (not case.get("should_refuse")) or any(m in answer for m in REFUSAL_MARKERS),
    }


# ──────────────────────────────────────────────────────────────
# 결과 출력
# ──────────────────────────────────────────────────────────────
def print_results(records: list[dict], verbose: bool, fail_only: bool) -> None:
    total = len(records)
    passed = sum(1 for r in records if r["passed"])
    kw_passed = sum(1 for r in records if r["keyword_pass"])
    law_cases = [r for r in records if r["law_pass"] is not None]
    law_passed = sum(1 for r in law_cases if r["law_pass"])
    refuse_cases = [r for r in records if not r["refusal_pass"] or not records[0]["category"] == "out_of_scope"]
    refusal_total = sum(1 for r in records if any(
        c.get("should_refuse") for c in [{"should_refuse": not r["refusal_pass"] or r["refusal_pass"]}]
    ))

    print("\n" + "=" * 60)
    print("  RAG 체인 답변 품질 평가 결과")
    print("=" * 60)
    print(f"  전체 통과율  : {passed}/{total}  ({passed/total:.1%})")
    print(f"  키워드 포함률: {kw_passed}/{total}  ({kw_passed/total:.1%})")
    law_total = sum(1 for r in records if r.get("law_pass") is not None and
                    any(c.get("expected_law") for c in [{"expected_law": "x"}]))

    # 카테고리별 집계
    cat_stats: dict[str, dict] = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in records:
        cat_stats[r["category"]]["total"] += 1
        if r["passed"]:
            cat_stats[r["category"]]["passed"] += 1

    print("\n  [카테고리별 통과율]")
    for cat, s in sorted(cat_stats.items()):
        bar = "■" * s["passed"] + "□" * (s["total"] - s["passed"])
        print(f"    {cat:<16} {s['passed']:>2}/{s['total']:<2}  {bar}")

    # 실패 케이스
    failed = [r for r in records if not r["passed"]]
    if failed:
        print(f"\n  [실패 케이스 {len(failed)}건]")
        for r in failed:
            print(f"\n  ✗ [{r['category']}] {r['question']}")
            for f in r["failures"]:
                print(f"      → {f}")
            if verbose:
                print(f"      답변: {r['answer'][:200]}...")

    # verbose: 전체 답변 출력
    if verbose:
        print("\n" + "=" * 60)
        print("  전체 답변 상세")
        print("=" * 60)
        for r in records:
            if fail_only and r["passed"]:
                continue
            status = "✓" if r["passed"] else "✗"
            print(f"\n  {status} [{r['category']}] {r['question']}")
            print(f"     {r['answer'][:300]}")
            if r["failures"]:
                for f in r["failures"]:
                    print(f"     → 실패: {f}")
    elif fail_only and failed:
        print("\n" + "=" * 60)
        print("  실패 케이스 답변")
        print("=" * 60)
        for r in failed:
            print(f"\n  ✗ [{r['category']}] {r['question']}")
            print(f"     {r['answer'][:300]}")

    print()


# ──────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 체인 답변 품질 평가 러너")
    parser.add_argument("--category", type=str, default=None,
                        help="특정 카테고리만 평가 (예: 주휴수당, 퇴직금, out_of_scope)")
    parser.add_argument("--verbose", action="store_true",
                        help="각 케이스의 답변 전문 출력")
    parser.add_argument("--fail-only", action="store_true",
                        help="실패 케이스 답변만 상세 출력")
    args = parser.parse_args()

    with open(TESTSET_PATH, encoding="utf-8") as f:
        data = json.load(f)
    cases = data["cases"]

    if args.category:
        cases = [c for c in cases if c["category"] == args.category]
        if not cases:
            print(f"카테고리 '{args.category}'에 해당하는 케이스가 없습니다.")
            print(f"사용 가능한 카테고리: {sorted({c['category'] for c in data['cases']})}")
            return

    print(f"평가 케이스: {len(cases)}건")
    chain = load_chain()

    records = []
    for i, case in enumerate(cases, 1):
        print(f"  [{i:02}/{len(cases):02}] {case['question'][:40]}", end="  ", flush=True)
        result = evaluate_case(chain, case)
        status = "✓" if result["passed"] else "✗"
        print(status)
        records.append(result)

    print_results(records, verbose=args.verbose, fail_only=args.fail_only)


if __name__ == "__main__":
    main()
