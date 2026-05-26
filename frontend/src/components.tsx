import React from 'react';
import type { Source, Message } from './types';
import { Mascot } from './mascot';

const RichText: React.FC<{ text: string }> = ({ text }) => {
  const parts: React.ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\{\{[^}]+\}\})/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('**')) {
      parts.push(<strong key={i++} style={{ fontWeight: 700 }}>{tok.slice(2, -2)}</strong>);
    } else {
      parts.push(<span key={i++} style={{
        background: 'rgba(192,57,43,0.08)', padding: '1px 4px', borderRadius: 3,
      }}>{tok.slice(2, -2)}</span>);
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return <>{parts}</>;
};

const SourceBadge: React.FC<{ source: Source }> = ({ source }) => (
  <span style={{
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '4px 9px 4px 8px', borderRadius: 5,
    background: source.highlight ? 'rgba(192,57,43,0.07)' : 'var(--lw-line-soft)',
    border: `1px solid ${source.highlight ? 'rgba(192,57,43,0.22)' : 'var(--lw-line)'}`,
    color: source.highlight ? 'var(--lw-red)' : 'var(--lw-ink-2)',
    fontSize: 11, fontWeight: 500,
  }}>
    <svg width="9" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
      <path d="M14 3v6h6" />
    </svg>
    <span>{source.doc}</span>
    <span style={{ color: 'var(--lw-muted)' }}>·</span>
    <span>{source.article}</span>
  </span>
);

export const UserBubble: React.FC<{ text: string }> = ({ text }) => (
  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 20, animation: 'lwFadeIn .25s ease' }}>
    <div style={{
      maxWidth: '75%', padding: '11px 18px', borderRadius: 22,
      background: 'var(--lw-navy)', color: 'var(--lw-on-navy)',
      fontSize: 14.5, lineHeight: 1.55, whiteSpace: 'pre-wrap',
    }}>{text}</div>
  </div>
);

export const BotBubble: React.FC<{ msg: Message }> = ({ msg }) => (
  <div style={{ display: 'flex', gap: 12, marginBottom: 22, alignItems: 'flex-start', animation: 'lwFadeIn .25s ease' }}>
    <div style={{ flexShrink: 0, marginTop: 2 }}><Mascot size={32} /></div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--lw-ink)' }}>Lori</span>
        <span style={{ fontSize: 10.5, color: 'var(--lw-muted)' }}>법률 어시스턴트 · {msg.timestamp}</span>
      </div>
      <div style={{
        background: 'var(--lw-surface)', border: '1px solid var(--lw-line)',
        borderRadius: '4px 16px 16px 16px', padding: '14px 18px',
        fontSize: 14.5, lineHeight: 1.7, color: 'var(--lw-ink)',
      }}>
        <RichText text={msg.text} />

        {msg.sources && msg.sources.length > 0 && msg.sources[0].quote && (
          <div style={{
            marginTop: 12, padding: '10px 12px', background: 'var(--lw-line-soft)',
            borderRadius: 8, fontSize: 12.5, color: 'var(--lw-ink-2)', lineHeight: 1.6,
          }}>
            <div style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--lw-muted)', letterSpacing: '0.05em', marginBottom: 4 }}>
              법령 원문 · {msg.sources[0].doc} {msg.sources[0].article}
            </div>
            <span style={{ fontFamily: '"Noto Serif KR", serif' }}>
              "{msg.sources[0].quote}"
            </span>
          </div>
        )}

        {msg.sources && msg.sources.length > 0 && (
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 12,
            paddingTop: 10, borderTop: '1px dashed var(--lw-line)',
          }}>
            <span style={{ fontSize: 11, color: 'var(--lw-muted)', marginRight: 2, lineHeight: '22px' }}>출처</span>
            {msg.sources.map((s, i) => <SourceBadge key={i} source={s} />)}
          </div>
        )}
      </div>
    </div>
  </div>
);

export const TypingBubble: React.FC<{ docs: string[] }> = ({ docs }) => (
  <div style={{ display: 'flex', gap: 12, marginBottom: 22, alignItems: 'flex-start', animation: 'lwFadeIn .25s ease' }}>
    <div style={{ flexShrink: 0, marginTop: 2 }}><Mascot size={32} /></div>
    <div style={{ flex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--lw-ink)' }}>Lori</span>
        <span style={{ fontSize: 10.5, color: 'var(--lw-muted)' }}>공식 문서 검색 중…</span>
      </div>
      <div style={{
        background: 'var(--lw-surface)', border: '1px solid var(--lw-line)',
        borderRadius: '4px 16px 16px 16px', padding: '14px 18px',
        display: 'inline-flex', alignItems: 'center', gap: 6,
      }}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            width: 6, height: 6, borderRadius: '50%', background: 'var(--lw-muted)',
            animation: `lwDot 1.2s ${i * 0.15}s infinite ease-in-out`,
          }} />
        ))}
      </div>
      <div style={{
        marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center',
        fontSize: 10.5, color: 'var(--lw-muted)',
      }}>
        <span>검색 중인 문서:</span>
        {docs.map((d, i) => (
          <span key={i} style={{
            padding: '2px 8px', borderRadius: 4,
            background: i === 0 ? 'rgba(26,43,74,0.06)' : 'transparent',
            border: i === 0 ? '1px solid transparent' : '1px solid var(--lw-line)',
            color: i === 0 ? 'var(--lw-navy)' : 'var(--lw-muted)',
            fontSize: 10, fontWeight: 500,
          }}>{d}</span>
        ))}
      </div>
    </div>
  </div>
);
