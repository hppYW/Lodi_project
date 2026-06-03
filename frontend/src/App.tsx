import React, { useState, useEffect, useRef, useCallback } from 'react';
import type { Theme, Message, Chat } from './types';
import { Wordmark } from './mascot';
import { Mascot } from './mascot';
import { UserBubble, BotBubble, TypingBubble } from './components';
import { SUGGESTED_QUESTIONS, fmtTime } from './data';

// 백엔드 API 주소 — uvicorn app.main:app --reload 로 실행
const API_URL = 'http://localhost:8000';

function loadTheme(): Theme {
  try {
    const t = localStorage.getItem('lw-theme');
    if (t === 'dark') return 'dark';
  } catch { /* ignore */ }
  return 'light';
}

const iconBtnStyle: React.CSSProperties = {
  width: 32, height: 32, borderRadius: 8, border: '1px solid var(--lw-line)',
  background: 'transparent', color: 'var(--lw-ink-2)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
};

// ─────────────────────────────────────────────────────────────
// TopBar
// ─────────────────────────────────────────────────────────────
const TopBar: React.FC<{
  theme: Theme; onToggleTheme: () => void;
  onNewChat: () => void; hasMessages: boolean;
}> = ({ theme, onToggleTheme, onNewChat, hasMessages }) => (
  <header style={{
    height: 52, borderBottom: '1px solid var(--lw-line)',
    background: 'var(--lw-surface)', display: 'flex', alignItems: 'center',
    padding: '0 20px', gap: 12, flexShrink: 0,
  }}>
    <Wordmark />

    <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
      {hasMessages && (
        <button onClick={onNewChat} style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '6px 12px', borderRadius: 8, border: '1px solid var(--lw-line)',
          background: 'transparent', color: 'var(--lw-ink-2)',
          fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
        }} title="새 대화">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
          새 대화
        </button>
      )}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '5px 10px', borderRadius: 999, background: 'var(--lw-line-soft)',
        fontSize: 11, fontWeight: 500, color: 'var(--lw-ink-2)',
      }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#4CAF7C' }} />
        공식 문서 기반 · v2.1
      </div>
      <button onClick={onToggleTheme} style={{ ...iconBtnStyle, width: 30, height: 30 }}
              title={theme === 'light' ? '다크 모드' : '라이트 모드'}>
        {theme === 'light' ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="1.7" strokeLinecap="round">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
          </svg>
        )}
      </button>
    </div>
  </header>
);

// ─────────────────────────────────────────────────────────────
// Welcome screen
// ─────────────────────────────────────────────────────────────
const WelcomeScreen: React.FC<{ onPick: (q: string) => void }> = ({ onPick }) => (
  <div style={{
    flex: 1, display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
    padding: '32px 24px', textAlign: 'center', overflow: 'auto',
  }}>
    <div style={{ marginBottom: 18 }}>
      <Mascot size={64} />
    </div>
    <div style={{
      fontFamily: '"Noto Serif KR", serif', fontSize: 24, fontWeight: 700,
      color: 'var(--lw-ink)', letterSpacing: '-0.02em', lineHeight: 1.35, marginBottom: 10,
    }}>
      법은 <em style={{ color: 'var(--lw-red)', fontStyle: 'normal' }}>지어내면</em> 불법입니다.
    </div>
    <div style={{
      fontSize: 13.5, color: 'var(--lw-ink-2)', lineHeight: 1.6, maxWidth: 440, marginBottom: 4,
    }}>
      공식 문서에서만 답합니다. 근로기준법·최저임금법 등<br />
      고용노동부 원문에서 직접 인용하여 출처를 표기합니다.
    </div>

    <div style={{
      display: 'flex', alignItems: 'center', gap: 16, marginTop: 22, marginBottom: 30,
      fontSize: 10.5, color: 'var(--lw-muted)',
      fontFamily: '"JetBrains Mono", monospace', letterSpacing: '0.02em',
    }}>
      <span>공식 문서 <span style={{ color: 'var(--lw-ink-2)', fontWeight: 600 }}>87</span>건</span>
      <span style={{ width: 3, height: 3, background: 'var(--lw-line)', borderRadius: '50%' }} />
      <span>추측 답변 <span style={{ color: 'var(--lw-red)', fontWeight: 600 }}>0</span>건</span>
    </div>

    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, maxWidth: 460 }}>
      {SUGGESTED_QUESTIONS.map((q, i) => (
        <button key={i} onClick={() => onPick(q)} style={{
          padding: '10px 14px', borderRadius: 10, border: '1px solid var(--lw-line)',
          background: 'var(--lw-surface)', fontSize: 12.5, color: 'var(--lw-ink)',
          fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit',
          display: 'flex', alignItems: 'center', gap: 7,
        }}>
          <span style={{
            fontFamily: '"JetBrains Mono", monospace', fontSize: 9.5,
            color: 'var(--lw-muted)', letterSpacing: '0.05em',
          }}>0{i + 1}</span>
          {q}
        </button>
      ))}
    </div>
  </div>
);

// ─────────────────────────────────────────────────────────────
// Conversation
// ─────────────────────────────────────────────────────────────
const Conversation: React.FC<{ chat: Chat }> = ({ chat }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chat.messages.length, chat.messages[chat.messages.length - 1]?.role]);

  return (
    <div ref={scrollRef} style={{ flex: 1, overflow: 'auto', padding: '28px 24px 8px' }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        {chat.messages.map(m => {
          if (m.role === 'user') return <UserBubble key={m.id} text={m.text} />;
          if (m.role === 'typing') return <TypingBubble key={m.id} docs={m.searchingDocs || []} />;
          return <BotBubble key={m.id} msg={m} />;
        })}
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Composer
// ─────────────────────────────────────────────────────────────
const Composer: React.FC<{
  value: string; onChange: (v: string) => void; onSend: () => void;
  disabled?: boolean;
}> = ({ value, onChange, onSend, disabled }) => {
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
  }, [value]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) onSend();
    }
  };

  return (
    <div style={{
      padding: '14px 24px 18px',
      background: 'linear-gradient(to top, var(--lw-bg) 75%, transparent)',
      flexShrink: 0,
    }}>
      <div style={{
        maxWidth: 760, margin: '0 auto', background: 'var(--lw-surface)',
        border: '1px solid var(--lw-line)', borderRadius: 16,
        padding: '10px 12px 10px 18px',
        display: 'flex', alignItems: 'center', gap: 10,
        transition: 'border-color .15s',
      }}>
        <textarea
          ref={taRef} value={value} onChange={e => onChange(e.target.value)}
          onKeyDown={handleKey} rows={1} disabled={disabled}
          placeholder="질문을 입력하세요 — 예: 주휴수당 계산법"
          style={{
            flex: 1, border: 'none', outline: 'none', resize: 'none',
            background: 'transparent', fontSize: 14, lineHeight: '34px',
            color: 'var(--lw-ink)', fontFamily: 'inherit',
            minHeight: 34, maxHeight: 160, padding: 0,
          }} />
        <button disabled={disabled || !value.trim()} onClick={onSend} style={{
          height: 34, padding: '0 14px 0 12px', borderRadius: 10,
          background: (disabled || !value.trim()) ? 'var(--lw-line)' : 'var(--lw-red)',
          color: (disabled || !value.trim()) ? 'var(--lw-muted)' : '#ffffff',
          border: 'none',
          cursor: (disabled || !value.trim()) ? 'not-allowed' : 'pointer',
          display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, fontWeight: 600,
          fontFamily: 'inherit', transition: 'background .15s',
        }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12h14M13 5l7 7-7 7" />
          </svg>
          전송
        </button>
      </div>
      <div style={{
        maxWidth: 760, margin: '8px auto 0',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        fontSize: 10.5, color: 'var(--lw-muted)',
      }}>
        <span>Lodi는 고용노동부 공식 문서·법령만을 출처로 답변합니다. 지어내지 않습니다.</span>
        <span>Shift + Enter 줄바꿈</span>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// App
// ─────────────────────────────────────────────────────────────
const App: React.FC = () => {
  const [theme, setTheme] = useState<Theme>(loadTheme);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState(() => 'c-' + Date.now());
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    try { localStorage.setItem('lw-theme', theme); } catch { /* ignore */ }
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme(t => t === 'light' ? 'dark' : 'light');
  }, []);

  const newChat = useCallback(() => {
    setMessages([]);
    setSessionId('c-' + Date.now());
    setDraft('');
  }, []);

  const send = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;

    const now = Date.now();
    const userMsg: Message = {
      id: 'u-' + now, role: 'user', text: trimmed, timestamp: fmtTime(now),
    };
    const typingMsg: Message = {
      id: 't-' + now, role: 'typing', text: '', timestamp: fmtTime(now),
      searchingDocs: ['근로기준법', '최저임금법', '근로자퇴직급여 보장법'],
    };

    setMessages(prev => [...prev, userMsg, typingMsg]);
    setDraft('');
    setBusy(true);

    fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: trimmed, session_id: sessionId }),
    })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        const replyTime = Date.now();
        const botMsg: Message = {
          id: 'b-' + replyTime, role: 'bot',
          text: data.reply, timestamp: fmtTime(replyTime),
          sources: data.sources || [],
        };
        setMessages(prev => prev.filter(m => m.role !== 'typing').concat(botMsg));
      })
      .catch(() => {
        const replyTime = Date.now();
        const botMsg: Message = {
          id: 'b-' + replyTime, role: 'bot',
          text: '서버와 연결할 수 없습니다. 백엔드가 실행 중인지 확인해 주세요.\n\n'
            + '실행 방법: cd backend && uvicorn app.main:app --reload',
          timestamp: fmtTime(replyTime),
        };
        setMessages(prev => prev.filter(m => m.role !== 'typing').concat(botMsg));
      })
      .finally(() => setBusy(false));
  }, [busy, sessionId]);

  const handleSend = useCallback(() => send(draft), [send, draft]);
  const handlePick = useCallback((q: string) => {
    setDraft(q);
    setTimeout(() => send(q), 50);
  }, [send]);

  return (
    <div className="lw" data-theme={theme} style={{
      width: '100%', height: '100%', background: 'var(--lw-bg)', color: 'var(--lw-ink)',
      fontFamily: '"Noto Sans KR", system-ui, sans-serif',
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      <TopBar theme={theme} onToggleTheme={toggleTheme}
              onNewChat={newChat} hasMessages={messages.length > 0} />

      {messages.length > 0 ? (
        <Conversation chat={{ id: sessionId, title: '', createdAt: 0, updatedAt: 0, pinned: false, messages }} />
      ) : (
        <WelcomeScreen onPick={handlePick} />
      )}

      <Composer value={draft} onChange={setDraft}
                onSend={handleSend} disabled={busy} />
    </div>
  );
};

export default App;
