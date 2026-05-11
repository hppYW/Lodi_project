import React from 'react';

export const Mascot: React.FC<{ size?: number }> = ({ size = 32 }) => (
  <svg width={size} height={size} viewBox="0 0 40 40" aria-label="Lori" role="img"
       style={{ display: 'block', borderRadius: '50%' }}>
    <circle cx="20" cy="20" r="20" fill="#1A2B4A" />
    <rect x="19.25" y="10" width="1.5" height="20" fill="#fff" />
    <rect x="8" y="14.25" width="24" height="1.5" fill="#fff" />
    <path d="M8 15 L6 20 L14 20 L12 15 Z" fill="#fff" opacity="0.92" />
    <path d="M32 15 L34 20 L26 20 L28 15 Z" fill="#fff" opacity="0.92" />
    <circle cx="20" cy="10" r="1.6" fill="#C0392B" />
    <rect x="15.5" y="29.5" width="9" height="1.25" fill="#fff" />
  </svg>
);

export const Wordmark: React.FC = () => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
    <div style={{
      width: 28, height: 28, borderRadius: 6, background: 'var(--lw-navy)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: '"Noto Serif KR", serif', fontWeight: 700,
      color: 'var(--lw-on-navy)', fontSize: 16, position: 'relative',
    }}>
      法
      <span style={{
        position: 'absolute', right: -2, top: -2,
        width: 6, height: 6, borderRadius: '50%', background: 'var(--lw-red)',
      }} />
    </div>
    <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1 }}>
      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--lw-ink)', letterSpacing: '-0.01em' }}>
        LawDong
      </span>
      <span style={{ fontSize: 10.5, fontWeight: 500, color: 'var(--lw-muted)', marginTop: 3, letterSpacing: '0.02em' }}>
        Labor Law · Source-grounded
      </span>
    </div>
  </div>
);
