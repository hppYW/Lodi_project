import type { Source, Chat } from './types';

interface KBEntry {
  keywords: string[];
  reply: string;
  sources: Source[];
  searchingDocs: string[];
}

const KB: KBEntry[] = [
  {
    keywords: ['주휴', '주휴수당', '15시간', '주15'],
    reply: '네, 받으실 수 있습니다. 1주 소정근로시간이 **15시간 이상**인 근로자는 주 1회 이상 **유급휴일**을 받을 권리가 있으며, 주휴수당은 (1일 소정근로시간 × 시급)으로 계산됩니다. 단, 해당 주에 **개근**한 경우에 발생합니다.',
    sources: [
      { doc: '근로기준법', article: '제55조', highlight: true,
        quote: '사용자는 근로자에게 1주일에 평균 1회 이상의 유급휴일을 보장하여야 한다.' },
      { doc: '근로기준법 시행령', article: '제30조' },
    ],
    searchingDocs: ['근로기준법', '근로기준법 시행령', '고용노동부 해설집 2024'],
  },
  {
    keywords: ['근로계약서', '계약서'],
    reply: '근로계약서를 **서면으로 작성·교부**하지 않으면 **500만원 이하의 벌금** 대상입니다. 임금, 소정근로시간, 휴일, 연차 등 필수 기재 사항은 반드시 서면에 명시되어야 합니다.',
    sources: [
      { doc: '근로기준법', article: '제17조', highlight: true,
        quote: '사용자는 근로계약을 체결할 때에 근로자에게 다음 각 호의 사항을 명시하여야 한다.' },
      { doc: '근로기준법', article: '제114조' },
    ],
    searchingDocs: ['근로기준법', '근로기준법 시행령'],
  },
  {
    keywords: ['퇴직금', '퇴직'],
    reply: '퇴직금은 **계속근로기간 1년 이상**, **4주 평균 1주 소정근로시간 15시간 이상**인 근로자에게 지급됩니다. 금액은 **30일분 이상의 평균임금 × 근속연수**로 산정합니다.',
    sources: [
      { doc: '근로자퇴직급여 보장법', article: '제4조', highlight: true,
        quote: '사용자는 퇴직하는 근로자에게 급여를 지급하기 위하여 퇴직급여제도 중 하나 이상의 제도를 설정하여야 한다.' },
      { doc: '동법', article: '제8조' },
    ],
    searchingDocs: ['근로자퇴직급여 보장법', '시행령', '시행규칙'],
  },
  {
    keywords: ['연차', '유급휴가', '연차수당'],
    reply: '**1년간 80% 이상 출근**한 근로자에게 **15일의 유급연차**가 부여됩니다. 1년 미만 근로자는 **1개월 개근 시 1일**씩 부여되며, 3년 이상 근속 시 매 2년마다 **1일이 가산**(최대 25일)됩니다.',
    sources: [
      { doc: '근로기준법', article: '제60조', highlight: true,
        quote: '사용자는 1년간 80퍼센트 이상 출근한 근로자에게 15일의 유급휴가를 주어야 한다.' },
    ],
    searchingDocs: ['근로기준법', '시행령'],
  },
  {
    keywords: ['최저임금', '최임'],
    reply: '**2025년 최저시급은 10,030원**입니다 (월 환산 약 2,096,270원, 주 40시간 기준). 위반 시 **3년 이하 징역 또는 2천만원 이하의 벌금**에 처해질 수 있습니다.',
    sources: [
      { doc: '최저임금법', article: '제6조', highlight: true,
        quote: '사용자는 최저임금의 적용을 받는 근로자에게 최저임금액 이상의 임금을 지급하여야 한다.' },
      { doc: '최저임금 고시', article: '2024-78호' },
    ],
    searchingDocs: ['최저임금법', '최저임금 고시 2024-78호'],
  },
  {
    keywords: ['연장', '야간', '휴일근로', '가산'],
    reply: '**연장·야간·휴일근로**에 대해서는 **통상임금의 50%** 이상을 가산하여 지급해야 합니다. 야간근로(22시~06시)와 연장근로가 중복되는 경우 각각 가산되어 **100%**가 적용됩니다.',
    sources: [
      { doc: '근로기준법', article: '제56조', highlight: true,
        quote: '사용자는 연장근로에 대하여는 통상임금의 100분의 50 이상을 가산하여 지급하여야 한다.' },
    ],
    searchingDocs: ['근로기준법'],
  },
];

export function findKBEntry(q: string): KBEntry {
  const lower = q.toLowerCase().replace(/\s/g, '');
  for (const e of KB) {
    if (e.keywords.some(k => lower.includes(k.toLowerCase()))) return e;
  }
  return {
    keywords: [],
    reply: '죄송합니다. 해당 질문에 대한 **공식 문서 근거를 찾지 못했습니다.** Lori는 추측으로 답변하지 않습니다. 질문을 좀 더 구체적으로 작성해 주시거나, 관련 키워드(예: 주휴수당, 연차, 퇴직금 등)를 포함해 주세요.',
    sources: [],
    searchingDocs: ['근로기준법', '최저임금법', '근로자퇴직급여 보장법'],
  };
}

export const SUGGESTED_QUESTIONS = [
  '주휴수당 계산법',
  '근로계약서 안 쓰면?',
  '퇴직금 조건이 뭐예요?',
  '연차는 언제부터?',
];

export const SEED_CHATS: Chat[] = [
  {
    id: 'seed-1',
    title: '주 15시간 알바 주휴수당',
    createdAt: Date.now() - 1000 * 60 * 60 * 2,
    updatedAt: Date.now() - 1000 * 60 * 60 * 2,
    pinned: true,
    messages: [],
  },
  {
    id: 'seed-2',
    title: '연차 계산 방식 문의',
    createdAt: Date.now() - 1000 * 60 * 60 * 5,
    updatedAt: Date.now() - 1000 * 60 * 60 * 5,
    pinned: false,
    messages: [],
  },
  {
    id: 'seed-3',
    title: '근로계약서 미작성 시 처벌',
    createdAt: Date.now() - 1000 * 60 * 60 * 24 * 2,
    updatedAt: Date.now() - 1000 * 60 * 60 * 24 * 2,
    pinned: false,
    messages: [],
  },
  {
    id: 'seed-4',
    title: '최저임금 2025년 기준',
    createdAt: Date.now() - 1000 * 60 * 60 * 24 * 4,
    updatedAt: Date.now() - 1000 * 60 * 60 * 24 * 4,
    pinned: true,
    messages: [],
  },
  {
    id: 'seed-5',
    title: '퇴직금 지급 요건',
    createdAt: Date.now() - 1000 * 60 * 60 * 24 * 12,
    updatedAt: Date.now() - 1000 * 60 * 60 * 24 * 12,
    pinned: false,
    messages: [],
  },
  {
    id: 'seed-6',
    title: '야간근로 가산수당',
    createdAt: Date.now() - 1000 * 60 * 60 * 24 * 18,
    updatedAt: Date.now() - 1000 * 60 * 60 * 24 * 18,
    pinned: false,
    messages: [],
  },
];

export function fmtTime(ts: number): string {
  const d = new Date(ts);
  const h = d.getHours().toString().padStart(2, '0');
  const m = d.getMinutes().toString().padStart(2, '0');
  return `${h}:${m}`;
}

export function groupChatsByDate(chats: Chat[]): { group: string; items: Chat[] }[] {
  const now = Date.now();
  const day = 1000 * 60 * 60 * 24;
  const groups: Record<string, Chat[]> = { '오늘': [], '지난 7일': [], '이전': [] };
  for (const c of chats) {
    const age = now - c.updatedAt;
    if (age < day) groups['오늘'].push(c);
    else if (age < 7 * day) groups['지난 7일'].push(c);
    else groups['이전'].push(c);
  }
  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([group, items]) => ({ group, items }));
}
