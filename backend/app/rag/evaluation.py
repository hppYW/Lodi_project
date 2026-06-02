# ============================================================
# evaluation.py — RAG 파이프라인 성능 평가 모듈
# ============================================================
# [역할]
#   RAG 파이프라인의 답변 품질을 정량적으로 평가합니다.
#   팀원C의 성능 평가 파트에서 이 모듈을 활용할 수 있습니다.
#
# [평가 항목 — 3가지 핵심 지표]
#   ① 출처 정확도 (Source Accuracy):
#      답변에 올바른 법 조항이 인용되었는가?
#      → 잘못된 조항 인용은 법률 서비스에서 치명적
#
#   ② 키워드 적중률 (Keyword Hit Rate):
#      답변에 핵심 법률 개념이 포함되었는가?
#      → 관련 개념 누락 = 불완전한 답변
#
#   ③ 거부 정확도 (Refusal Accuracy):
#      문서에 없는 질문에 대해 "모른다"고 답했는가?
#      → 모른다고 답하지 못하면 할루시네이션 발생
#
# [사용법]
#   python -m backend.app.rag.evaluation
#
# [일반 ChatGPT와의 비교 포인트]
#   - ChatGPT: 학습 데이터 기반 → 최신 법령 미반영 가능, 출처 불명확
#   - Lodi: 공식 문서 기반 RAG → 최신 법령 반영, 출처 명확히 인용
#   - 이 평가 모듈로 "출처 명시율", "거부 정확도" 등에서
#     Lodi의 우위를 수치로 입증할 수 있습니다.
# ============================================================

from dataclasses import dataclass, field


# ────────────────────────────────────────────────────────────
# 1. 테스트 케이스 정의
# ────────────────────────────────────────────────────────────

@dataclass
class TestCase:
    """
    하나의 평가 테스트 케이스를 정의합니다.

    [설계 의도]
      각 테스트 케이스는 "이 질문에 대해 이런 요소가 포함된 답변이 나와야 한다"를
      정의합니다. 이를 통해 RAG 파이프라인의 품질을 자동으로 검증할 수 있습니다.

    Attributes:
        question: 테스트할 질문 (사용자가 실제로 물어볼 법한 질문)
        expected_sources: 답변에 반드시 포함되어야 할 법 조항 키워드
                          예: ["근로기준법 제55조", "시행령 제30조"]
        expected_keywords: 답변에 포함되어야 할 핵심 개념 키워드
                           예: ["15시간", "유급휴일", "개근"]
        should_refuse: True이면 "찾을 수 없습니다" 응답이 기대됨
                       (노동법 범위 밖 질문에 대한 거부 테스트)
        category: 질문 유형 분류 (계산형/요건형/절차형/거부)
                  → 유형별 정확도를 따로 집계할 수 있음
    """
    question: str
    expected_sources: list[str] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)
    should_refuse: bool = False
    category: str = ""


# ── 테스트 데이터셋 ──
# 실제 알바생이 물어볼 법한 질문들을 유형별로 구성했습니다.
# 각 질문에 대해 "올바른 답변이라면 반드시 포함해야 할 요소"를 정의합니다.
# 이 데이터셋은 RAG 파이프라인의 품질 기준선(baseline)으로 사용됩니다.

TEST_CASES: list[TestCase] = [
    # ━━━ 계산형 질문 ━━━
    # 숫자나 공식이 포함된 답변이 필요한 질문
    TestCase(
        question="주휴수당 어떻게 계산하나요?",
        expected_sources=["근로기준법 제55조", "시행령 제30조"],
        expected_keywords=["15시간", "유급휴일", "소정근로시간", "시급"],
        category="계산형",
    ),
    TestCase(
        question="야간근로 수당은 얼마나 더 받나요?",
        expected_sources=["근로기준법 제56조"],
        expected_keywords=["50%", "가산", "22시", "통상임금"],
        category="계산형",
    ),

    # ━━━ 요건 확인형 질문 ━━━
    # "~할 수 있나요?" 형태, 조건/요건을 확인하는 질문
    TestCase(
        question="퇴직금 받을 수 있는 조건이 뭔가요?",
        expected_sources=["근로자퇴직급여 보장법 제4조"],
        expected_keywords=["1년", "15시간", "계속근로"],
        category="요건형",
    ),
    TestCase(
        question="연차휴가는 언제부터 발생하나요?",
        expected_sources=["근로기준법 제60조"],
        expected_keywords=["80%", "출근", "15일"],
        category="요건형",
    ),

    # ━━━ 절차형 질문 ━━━
    # "어떻게 하나요?" 형태, 절차나 방법을 묻는 질문
    TestCase(
        question="근로계약서를 안 써주면 어떻게 하나요?",
        expected_sources=["근로기준법 제17조"],
        expected_keywords=["서면", "500만원", "벌금"],
        category="절차형",
    ),

    # ━━━ 거부해야 할 질문 (노동법 범위 밖) ━━━
    # AI가 "찾을 수 없습니다"라고 답해야 하는 질문
    # → 할루시네이션 방지 능력을 직접 테스트
    TestCase(
        question="오늘 서울 날씨 어때?",
        expected_sources=[],
        expected_keywords=["찾을 수 없습니다", "1350"],
        should_refuse=True,
        category="거부",
    ),
    TestCase(
        question="맛있는 치킨집 추천해줘",
        expected_sources=[],
        expected_keywords=["찾을 수 없습니다", "1350"],
        should_refuse=True,
        category="거부",
    ),
]


# ────────────────────────────────────────────────────────────
# 2. 평가 결과 구조체
# ────────────────────────────────────────────────────────────

@dataclass
class EvalResult:
    """
    단일 테스트 케이스의 평가 결과를 저장합니다.

    Attributes:
        test_case: 원본 테스트 케이스
        answer: RAG 체인이 생성한 실제 답변 텍스트
        source_hit: 기대 출처가 답변에 포함되었는지 여부
        keyword_hit: 기대 키워드가 답변에 포함되었는지 여부
        refuse_correct: 거부해야 할 질문을 올바르게 거부했는지 여부
    """
    test_case: TestCase
    answer: str
    source_hit: bool
    keyword_hit: bool
    refuse_correct: bool

    @property
    def passed(self) -> bool:
        """3가지 지표가 모두 통과하면 True"""
        return self.source_hit and self.keyword_hit and self.refuse_correct


# ────────────────────────────────────────────────────────────
# 3. 평가 로직
# ────────────────────────────────────────────────────────────

def evaluate_single(answer: str, test_case: TestCase) -> EvalResult:
    """
    단일 답변을 테스트 케이스 기준으로 평가합니다.

    [평가 기준]
      ① 출처 정확도: expected_sources의 키워드가 답변에 포함되어 있는지
         예: "근로기준법 제55조"가 기대 출처이면, 답변에 "제55조"가 있는지 확인

      ② 키워드 적중: expected_keywords가 답변에 포함되어 있는지
         예: ["15시간", "유급휴일"]이 기대 키워드이면, 둘 다 답변에 있는지 확인

      ③ 거부 정확도:
         - should_refuse=True → "찾을 수 없습니다" 또는 "문의"가 답변에 있어야 통과
         - should_refuse=False → "찾을 수 없습니다"가 답변에 없어야 통과

    Args:
        answer: RAG 체인이 생성한 답변 텍스트
        test_case: 해당 테스트 케이스

    Returns:
        EvalResult 평가 결과 객체
    """
    answer_lower = answer.lower()

    # ── ① 출처 정확도 평가 ──
    # 기대하는 법 조항이 답변에 언급되었는지 확인
    # 각 출처 문자열의 모든 단어가 답변에 포함되어야 함
    # 예: "근로기준법 제55조" → "근로기준법"과 "제55조"가 모두 답변에 있는지
    if test_case.expected_sources:
        source_hit = all(
            all(part in answer for part in src.split())
            for src in test_case.expected_sources
        )
    else:
        # 기대 출처가 없는 경우 (거부 질문 등) → 무조건 통과
        source_hit = True

    # ── ② 키워드 적중률 평가 ──
    # 핵심 키워드가 답변에 포함되었는지 확인 (대소문자 무시)
    keyword_hit = all(
        kw.lower() in answer_lower
        for kw in test_case.expected_keywords
    )

    # ── ③ 거부 정확도 평가 ──
    if test_case.should_refuse:
        # 거부해야 할 질문: "찾을 수 없습니다" 또는 "문의"가 포함되어야 함
        refuse_correct = "찾을 수 없습니다" in answer or "문의" in answer
    else:
        # 답변해야 할 질문: "찾을 수 없습니다"가 포함되면 안 됨
        refuse_correct = "찾을 수 없습니다" not in answer

    return EvalResult(
        test_case=test_case,
        answer=answer,
        source_hit=source_hit,
        keyword_hit=keyword_hit,
        refuse_correct=refuse_correct,
    )


# ────────────────────────────────────────────────────────────
# 4. 전체 평가 실행
# ────────────────────────────────────────────────────────────

def run_evaluation(rag_chain) -> list[EvalResult]:
    """
    전체 테스트 셋에 대해 RAG 체인을 평가하고 결과를 출력합니다.

    [실행 흐름]
      1. 각 테스트 케이스의 질문을 RAG 체인에 입력
      2. 생성된 답변을 evaluate_single()로 평가
      3. 개별 결과 출력 (통과/실패, 각 지표별 상세)
      4. 전체 요약 출력 (출처 정확도, 키워드 적중률, 거부 정확도, 종합 통과율)

    [사용 예시]
      from backend.app.rag.chain import get_rag_chain
      from backend.app.rag.evaluation import run_evaluation

      chain = get_rag_chain()
      results = run_evaluation(chain)

    Args:
        rag_chain: 평가할 RAG 체인 인스턴스 (get_rag_chain()의 반환값)

    Returns:
        EvalResult 리스트 (각 테스트 케이스의 평가 결과)
    """
    results: list[EvalResult] = []

    print("=" * 60)
    print("  Lodi RAG 파이프라인 성능 평가")
    print("=" * 60)

    for i, tc in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] [{tc.category}] {tc.question}")

        try:
            # RAG 체인 실행
            # 평가용 고정 세션 ID를 사용하여 테스트 간 대화 이력이 섞이지 않도록 함
            response = rag_chain.invoke(
                {"input": tc.question},
                config={"configurable": {"session_id": f"eval-{i}"}},
            )

            # 응답에서 답변 텍스트 추출
            # 체인 반환 형식에 따라 문자열 또는 딕셔너리일 수 있음
            if isinstance(response, str):
                answer = response
            else:
                answer = response.get("answer", str(response))

        except Exception as e:
            answer = f"[오류 발생] {str(e)}"

        # 답변 평가
        result = evaluate_single(answer, tc)
        results.append(result)

        # ── 개별 결과 출력 ──
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] 출처: {'O' if result.source_hit else 'X'} | "
              f"키워드: {'O' if result.keyword_hit else 'X'} | "
              f"거부: {'O' if result.refuse_correct else 'X'}")
        # 답변 미리보기 (너무 길면 100자로 자름)
        preview = answer[:100].replace("\n", " ")
        print(f"  답변: {preview}...")

    # ── 전체 요약 출력 ──
    total = len(results)
    source_acc = sum(1 for r in results if r.source_hit) / total * 100
    keyword_acc = sum(1 for r in results if r.keyword_hit) / total * 100
    refuse_acc = sum(1 for r in results if r.refuse_correct) / total * 100
    overall = sum(1 for r in results if r.passed) / total * 100

    print("\n" + "=" * 60)
    print("  평가 결과 요약")
    print("=" * 60)
    print(f"  테스트 케이스:   {total}개")
    print(f"  출처 정확도:     {source_acc:5.1f}%")
    print(f"  키워드 적중률:   {keyword_acc:5.1f}%")
    print(f"  거부 정확도:     {refuse_acc:5.1f}%")
    print(f"  ─────────────────────────")
    print(f"  종합 통과율:     {overall:5.1f}%  "
          f"({sum(1 for r in results if r.passed)}/{total})")
    print("=" * 60)

    # ── 유형별 정확도 ──
    categories = sorted(set(tc.category for tc in TEST_CASES))
    if len(categories) > 1:
        print("\n  [유형별 통과율]")
        for cat in categories:
            cat_results = [r for r in results if r.test_case.category == cat]
            cat_pass = sum(1 for r in cat_results if r.passed)
            cat_total = len(cat_results)
            print(f"    {cat}: {cat_pass}/{cat_total} "
                  f"({cat_pass / cat_total * 100:.0f}%)")
        print()

    return results


# ── 직접 실행 시 평가 수행 ──
if __name__ == "__main__":
    from .chain import get_rag_chain

    print("RAG 체인 초기화 중...")
    chain = get_rag_chain()
    print("평가 시작!\n")
    run_evaluation(chain)
