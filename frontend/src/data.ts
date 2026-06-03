export const SUGGESTED_QUESTIONS = [
  '주휴수당 계산법',
  '근로계약서 안 쓰면?',
  '퇴직금 조건이 뭐예요?',
  '연차는 언제부터?',
];

export function fmtTime(ts: number): string {
  const d = new Date(ts);
  const h = d.getHours().toString().padStart(2, '0');
  const m = d.getMinutes().toString().padStart(2, '0');
  return `${h}:${m}`;
}
