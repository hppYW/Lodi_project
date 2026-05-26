import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import type { Theme, Message, Chat, AppState } from './types';
import { Wordmark } from './mascot';
import { Mascot } from './mascot';
import { UserBubble, BotBubble, TypingBubble } from './components';
import { findKBEntry, SUGGESTED_QUESTIONS, SEED_CHATS, fmtTime, groupChatsByDate } from './data';

const STORAGE_KEY = 'lw-state-v1';

function loadState(): AppState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.chats) return parsed;
    }
  } catch { /* ignore */ }
  return {
    chats: SEED_CHATS,
    activeChatId: null,
    theme: 'light',
    sidebarOpen: true,
  };
}

function saveState(s: AppState) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); } catch { /* ignore */ }
}

const iconBtnStyle: React.CSSProperties = {
  width: 32, height: 32, borderRadius: 8, border: '1px solid var(--lw-line)',
  background: 'transparent', color: 'var(--lw-ink-2)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
};

const groupHeaderStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  fontSize: 10.5, fontWeight: 600, color: 'var(--lw-muted)',
  letterSpacing: '0.06em', padding: '6px 8px 4px',
};

// ─────────────────────────────────────────────────────────────
// ChatItem
// ─────────────────────────────────────────────────────────────
const ChatItem: React.FC<{
  chat: Chat; active: boolean;
  onSelect: () => void; onTogglePin: () => void;
}> = ({ chat, active, onSelect, onTogglePin }) => {
  const [hover, setHover] = useState(false);
  return (
    <div
      onClick={onSelect}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '7px 10px', borderRadius: 7, marginBottom: 1,
        cursor: 'pointer',
        background: active ? 'var(--lw-pill)' : (hover ? 'var(--lw-line-soft)' : 'transparent'),
        color: active ? 'var(--lw-ink)' : 'var(--lw-ink-2)',
        fontWeight: active ? 600 : 400, fontSize: 12.5,
      }}>
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
        {chat.title}
      </span>
      {(hover || chat.pinned) && (
        <button onClick={(e) => { e.stopPropagation(); onTogglePin(); }} style={{
          border: 'none', background: 'transparent', cursor: 'pointer', padding: 2,
          color: chat.pinned ? 'var(--lw-red)' : 'var(--lw-muted)',
          display: 'flex', alignItems: 'center',
        }} title={chat.pinned ? '즐겨찾기 해제' : '즐겨찾기'}>
          <svg width="11" height="11" viewBox="0 0 24 24"
               fill={chat.pinned ? 'currentColor' : 'none'} stroke="currentColor"
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2l1 7 5 3-6 1-2 9-2-9-6-1 5-3 1-7h4z" />
          </svg>
        </button>
      )}
      {active && !hover && !chat.pinned && (
        <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--lw-red)', flexShrink: 0 }} />
      )}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────
// Sidebar
// ─────────────────────────────────────────────────────────────
const Sidebar: React.FC<{
  state: AppState;
  onNewChat: () => void;
  onSelect: (id: string) => void;
  onTogglePin: (id: string) => void;
  onCollapse: () => void;
}> = ({ state, onNewChat, onSelect, onTogglePin, onCollapse }) => {
  const [search, setSearch] = useState('');

  if (!state.sidebarOpen) {
    return (
      <div style={{
        width: 56, borderRight: '1px solid var(--lw-line)', background: 'var(--lw-surface)',
        display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '14px 0', gap: 14,
        flexShrink: 0,
      }}>
        <button onClick={onCollapse} style={{
          width: 32, height: 32, borderRadius: 8, background: 'var(--lw-navy)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: '"Noto Serif KR", serif', fontWeight: 700, color: 'var(--lw-on-navy)', fontSize: 15,
          border: 'none', cursor: 'pointer',
        }} title="사이드바 열기">法</button>
        <button onClick={onNewChat} style={iconBtnStyle} title="새 대화">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="1.8" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
        </button>
      </div>
    );
  }

  const filtered = search.trim()
    ? state.chats.filter(c => c.title.toLowerCase().includes(search.toLowerCase().trim()))
    : state.chats;
  const pinned = filtered.filter(c => c.pinned);
  const unpinned = filtered.filter(c => !c.pinned);
  const groups = groupChatsByDate(unpinned);

  return (
    <aside style={{
      width: 252, flexShrink: 0, borderRight: '1px solid var(--lw-line)',
      background: 'var(--lw-surface)', display: 'flex', flexDirection: 'column',
      fontSize: 13, color: 'var(--lw-ink-2)',
    }}>
      <div style={{ padding: '16px 16px 12px', display: 'flex', alignItems: 'center' }}>
        <Wordmark />
        <button onClick={onCollapse} style={{
          marginLeft: 'auto', width: 26, height: 26, borderRadius: 6, border: 'none',
          background: 'transparent', color: 'var(--lw-muted)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} title="사이드바 접기">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="1.8" strokeLinecap="round"><path d="M15 6l-6 6 6 6" /></svg>
        </button>
      </div>

      <div style={{ padding: '4px 12px 10px' }}>
        <button onClick={onNewChat} style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 12px', borderRadius: 10, background: 'var(--lw-navy)',
          color: 'var(--lw-on-navy)', border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
          fontFamily: 'inherit',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>
          새 대화 시작하기
        </button>
      </div>

      <div style={{ padding: '2px 12px 14px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '7px 10px', borderRadius: 8,
          background: 'var(--lw-line-soft)', color: 'var(--lw-muted)',
        }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round">
            <circle cx="11" cy="11" r="6" /><path d="m20 20-3.5-3.5" />
          </svg>
          <input value={search} onChange={e => setSearch(e.target.value)}
                 placeholder="대화 검색"
                 style={{
                   flex: 1, border: 'none', outline: 'none', background: 'transparent',
                   fontSize: 12, color: 'var(--lw-ink)', fontFamily: 'inherit',
                 }} />
          {search && (
            <button onClick={() => setSearch('')} style={{
              border: 'none', background: 'transparent', color: 'var(--lw-muted)',
              cursor: 'pointer', padding: 0, display: 'flex',
            }}>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth="2" strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
            </button>
          )}
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '0 12px 12px' }}>
        {pinned.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={groupHeaderStyle}>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
                <path d="M14 2l1 7 5 3-6 1-2 9-2-9-6-1 5-3 1-7h4z" opacity="0.85" />
              </svg>
              즐겨찾기
            </div>
            {pinned.map(c => (
              <ChatItem key={c.id} chat={c} active={c.id === state.activeChatId}
                        onSelect={() => onSelect(c.id)}
                        onTogglePin={() => onTogglePin(c.id)} />
            ))}
          </div>
        )}

        {groups.map(g => (
          <div key={g.group} style={{ marginBottom: 14 }}>
            <div style={groupHeaderStyle}>{g.group}</div>
            {g.items.map(c => (
              <ChatItem key={c.id} chat={c} active={c.id === state.activeChatId}
                        onSelect={() => onSelect(c.id)}
                        onTogglePin={() => onTogglePin(c.id)} />
            ))}
          </div>
        ))}

        {filtered.length === 0 && (
          <div style={{ padding: '20px 8px', color: 'var(--lw-muted)', fontSize: 12, textAlign: 'center' }}>
            검색 결과가 없습니다
          </div>
        )}
      </div>

      <div style={{
        borderTop: '1px solid var(--lw-line-soft)', padding: '10px 14px',
        display: 'flex', alignItems: 'center', gap: 10, fontSize: 11.5, color: 'var(--lw-muted)',
      }}>
        <div style={{
          width: 22, height: 22, borderRadius: '50%', background: 'var(--lw-pill)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontWeight: 600, color: 'var(--lw-ink-2)', fontSize: 10,
        }}>김</div>
        <span>김민재</span>
      </div>
    </aside>
  );
};

// ─────────────────────────────────────────────────────────────
// TopBar
// ─────────────────────────────────────────────────────────────
const TopBar: React.FC<{
  sidebarOpen: boolean; onToggleSidebar: () => void;
  theme: Theme; onToggleTheme: () => void;
  chatTitle?: string;
}> = ({ sidebarOpen, onToggleSidebar, theme, onToggleTheme, chatTitle }) => (
  <header style={{
    height: 52, borderBottom: '1px solid var(--lw-line)',
    background: 'var(--lw-surface)', display: 'flex', alignItems: 'center',
    padding: '0 20px', gap: 12, flexShrink: 0,
  }}>
    <button onClick={onToggleSidebar} style={{ ...iconBtnStyle, width: 30, height: 30 }}
            title={sidebarOpen ? '사이드바 접기' : '사이드바 열기'}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           strokeWidth="1.8" strokeLinecap="round">
        <rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16" />
      </svg>
    </button>

    {!sidebarOpen && <div style={{ marginLeft: 2 }}><Wordmark /></div>}

    {chatTitle && sidebarOpen && (
      <div style={{
        fontSize: 13, fontWeight: 600, color: 'var(--lw-ink)',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        maxWidth: 380,
      }}>{chatTitle}</div>
    )}

    <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
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
const WelcomeScreen: React.FC<{ onPick: (q: string) => void; chatCount: number }> = ({ onPick, chatCount }) => (
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
      <span>나의 대화 <span style={{ color: 'var(--lw-ink-2)', fontWeight: 600 }}>{chatCount}</span>건</span>
      <span style={{ width: 3, height: 3, background: 'var(--lw-line)', borderRadius: '50%' }} />
      <span>추측 답변 <span style={{ color: 'var(--lw-red)', fontWeight: 600 }}>0</span>건</span>
    </div>

    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', maxWidth: 560 }}>
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
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          paddingBottom: 20, marginBottom: 20, borderBottom: '1px solid var(--lw-line)',
        }}>
          <span style={{
            fontFamily: '"JetBrains Mono", monospace', fontSize: 10, color: 'var(--lw-muted)',
            padding: '2px 7px', borderRadius: 4, border: '1px solid var(--lw-line)',
          }}>#{chat.id.slice(-4).toUpperCase()}</span>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--lw-ink)' }}>{chat.title}</span>
        </div>

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
        display: 'flex', alignItems: 'flex-end', gap: 10,
        transition: 'border-color .15s',
      }}>
        <textarea
          ref={taRef} value={value} onChange={e => onChange(e.target.value)}
          onKeyDown={handleKey} rows={1} disabled={disabled}
          placeholder="질문을 입력하세요 — 예: 주휴수당 계산법"
          style={{
            flex: 1, border: 'none', outline: 'none', resize: 'none',
            background: 'transparent', fontSize: 14, lineHeight: 1.5,
            color: 'var(--lw-ink)', fontFamily: 'inherit',
            minHeight: 24, maxHeight: 160, padding: '4px 0',
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
  const [state, setState] = useState<AppState>(() => loadState());
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => { saveState(state); }, [state]);

  const activeChat = useMemo(
    () => state.chats.find(c => c.id === state.activeChatId) || null,
    [state.chats, state.activeChatId]
  );

  const newChat = useCallback(() => {
    setState(s => ({ ...s, activeChatId: null }));
    setDraft('');
  }, []);

  const selectChat = useCallback((id: string) => {
    setState(s => ({ ...s, activeChatId: id }));
  }, []);

  const togglePin = useCallback((id: string) => {
    setState(s => ({
      ...s,
      chats: s.chats.map(c => c.id === id ? { ...c, pinned: !c.pinned } : c),
    }));
  }, []);

  const toggleSidebar = useCallback(() => {
    setState(s => ({ ...s, sidebarOpen: !s.sidebarOpen }));
  }, []);

  const toggleTheme = useCallback(() => {
    setState(s => ({ ...s, theme: s.theme === 'light' ? 'dark' : 'light' }));
  }, []);

  const send = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;

    const now = Date.now();
    const userMsg: Message = {
      id: 'u-' + now, role: 'user', text: trimmed, timestamp: fmtTime(now),
    };
    const entry = findKBEntry(trimmed);
    const typingMsg: Message = {
      id: 't-' + now, role: 'typing', text: '', timestamp: fmtTime(now),
      searchingDocs: entry.searchingDocs,
    };

    let chatId = state.activeChatId;
    setState(s => {
      let chats = s.chats;
      if (!chatId) {
        const newId = 'c-' + now;
        chatId = newId;
        const newChatObj: Chat = {
          id: newId,
          title: trimmed.length > 24 ? trimmed.slice(0, 24) + '…' : trimmed,
          createdAt: now, updatedAt: now, pinned: false,
          messages: [userMsg, typingMsg],
        };
        chats = [newChatObj, ...chats];
      } else {
        chats = chats.map(c => c.id === chatId
          ? { ...c, updatedAt: now, messages: [...c.messages, userMsg, typingMsg] }
          : c);
      }
      return { ...s, chats, activeChatId: chatId };
    });
    setDraft('');
    setBusy(true);

    setTimeout(() => {
      const replyTime = Date.now();
      const botMsg: Message = {
        id: 'b-' + replyTime, role: 'bot',
        text: entry.reply, timestamp: fmtTime(replyTime), sources: entry.sources,
      };
      setState(s => ({
        ...s,
        chats: s.chats.map(c => c.id === chatId
          ? { ...c, updatedAt: replyTime,
              messages: c.messages.filter(m => m.role !== 'typing').concat(botMsg) }
          : c),
      }));
      setBusy(false);
    }, 1600);
  }, [busy, state.activeChatId]);

  const handleSend = useCallback(() => send(draft), [send, draft]);
  const handlePick = useCallback((q: string) => {
    setDraft(q);
    setTimeout(() => send(q), 50);
  }, [send]);

  return (
    <div className="lw" data-theme={state.theme} style={{
      width: '100%', height: '100%', background: 'var(--lw-bg)', color: 'var(--lw-ink)',
      fontFamily: '"Noto Sans KR", system-ui, sans-serif',
      display: 'flex', overflow: 'hidden',
    }}>
      <Sidebar state={state}
               onNewChat={newChat} onSelect={selectChat}
               onTogglePin={togglePin} onCollapse={toggleSidebar} />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <TopBar sidebarOpen={state.sidebarOpen} onToggleSidebar={toggleSidebar}
                theme={state.theme} onToggleTheme={toggleTheme}
                chatTitle={activeChat?.title} />

        {activeChat && activeChat.messages.length > 0 ? (
          <Conversation chat={activeChat} />
        ) : (
          <WelcomeScreen onPick={handlePick} chatCount={state.chats.length} />
        )}

        <Composer value={draft} onChange={setDraft}
                  onSend={handleSend} disabled={busy} />
      </div>
    </div>
  );
};

export default App;
