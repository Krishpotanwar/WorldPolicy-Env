/* DebateTranscriptPanel + VoteBar */

const STANCE_STYLES = {
  support: { label: 'SUPPORTS', bg: 'rgba(34,197,94,0.15)', border: 'rgba(34,197,94,0.4)', color: '#22c55e' },
  oppose:  { label: 'OPPOSES',  bg: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.4)', color: '#ef4444' },
  modify:  { label: 'MODIFIES', bg: 'rgba(245,158,11,0.15)', border: 'rgba(245,158,11,0.4)', color: '#f59e0b' },
  neutral: { label: 'NEUTRAL',  bg: 'rgba(148,163,184,0.15)', border: 'rgba(148,163,184,0.4)', color: '#94a3b8' },
  mediate: { label: 'MEDIATES', bg: 'rgba(20,184,166,0.15)', border: 'rgba(20,184,166,0.4)', color: '#14b8a6' },
};

function StancePill({ stance }) {
  const s = STANCE_STYLES[stance] || STANCE_STYLES.neutral;
  return React.createElement('span', {
    style: {
      fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700, letterSpacing: '0.5px',
      padding: '2px 7px', borderRadius: 3,
      background: s.bg, border: '1px solid ' + s.border, color: s.color,
    }
  }, s.label);
}

function UtteranceRow({ u, isActive, isNew }) {
  const pnlText = u.pnlDeltas ? Object.entries(u.pnlDeltas)
    .filter(([,v]) => v !== 0)
    .map(([k,v]) => k + ' ' + (v > 0 ? '+' : '') + v.toFixed(3))
    .join(', ') : '';

  return React.createElement('div', {
    className: isNew ? 'glass-appear' : '',
    style: {
      display: 'flex', gap: 0, padding: '10px 12px 10px 0',
      background: isActive ? u.speakerTint + '0f' : 'transparent',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
      transition: 'background 0.3s',
    }
  },
    // Left rail
    React.createElement('div', {
      style: {
        width: isActive ? 6 : 4, flexShrink: 0, borderRadius: 2,
        background: u.speakerTint + (isActive ? 'ff' : 'cc'),
        marginRight: 12,
        boxShadow: isActive ? '0 0 8px ' + u.speakerTint + '40' : 'none',
      }
    }),
    // Content
    React.createElement('div', { style: { flex: 1, minWidth: 0 } },
      // Header
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 } },
        React.createElement('span', {
          style: { fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
            letterSpacing: '1.2px', color: u.speakerTint }
        }, u.speakerName.toUpperCase()),
        React.createElement(StancePill, { stance: u.stance }),
        isActive && React.createElement('div', {
          style: { display: 'flex', alignItems: 'center', gap: 4, marginLeft: 'auto' }
        },
          React.createElement('div', { className: 'led led-green led-pulse', style: { width: 6, height: 6 } }),
          React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 8, color: 'rgba(255,255,255,0.35)' } }, 'SPEAKING'),
        ),
      ),
      // Body
      React.createElement('div', {
        style: {
          fontFamily: 'var(--font-ui)', fontSize: 13, lineHeight: 1.55,
          color: 'rgba(255,255,255,0.85)',
          display: '-webkit-box', WebkitLineClamp: 4, WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }
      }, '"' + u.text + '"'),
      // Meta
      React.createElement('div', {
        style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: 'rgba(255,255,255,0.25)',
          marginTop: 6 }
      },
        'step ' + u.step + (pnlText ? '  ·  pnlΔ: ' + pnlText : ''),
      ),
    ),
  );
}

function VoteBar({ tally }) {
  if (!tally) return null;
  const total = tally.support + tally.oppose + tally.modify || 1;
  const passed = tally.support > tally.oppose;
  const bars = [
    { label: 'Support', count: tally.support, color: '#22c55e', pct: (tally.support/total*100) },
    { label: 'Oppose', count: tally.oppose, color: '#ef4444', pct: (tally.oppose/total*100) },
    { label: 'Modify', count: tally.modify, color: '#f59e0b', pct: (tally.modify/total*100) },
  ];

  return React.createElement('div', {
    style: {
      padding: '12px 16px', borderTop: '1px solid rgba(255,255,255,0.08)',
      background: 'rgba(255,255,255,0.02)',
    }
  },
    React.createElement('div', {
      style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }
    },
      React.createElement('span', {
        style: { fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
          letterSpacing: '1.5px', color: 'rgba(255,255,255,0.35)' }
      }, 'VOTE TALLY'),
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 6 } },
        React.createElement('div', { className: 'led ' + (passed ? 'led-green' : 'led-red'), style: { width: 8, height: 8 } }),
        React.createElement('span', {
          style: { fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
            color: passed ? '#22c55e' : '#ef4444' }
        }, passed ? 'PASSED' : 'FAILED'),
      ),
    ),
    ...bars.map((b, i) =>
      React.createElement('div', { key: i, style: { marginBottom: 4 } },
        React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', marginBottom: 2 } },
          React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: b.color } }, b.label),
          React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: 'rgba(255,255,255,0.4)' } }, b.count),
        ),
        React.createElement('div', {
          style: { height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden',
            border: '1px solid rgba(255,255,255,0.04)', boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.3)' }
        },
          React.createElement('div', {
            style: {
              height: '100%', width: b.pct + '%', borderRadius: 3,
              background: b.color, boxShadow: '0 0 8px ' + b.color + '40',
              transition: 'width 1.2s cubic-bezier(0.16,1,0.3,1)',
            }
          }),
        ),
      )
    ),
  );
}

function RoundDivider({ round }) {
  return React.createElement('div', {
    style: {
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '10px 16px', background: 'rgba(139,92,246,0.06)',
      borderTop: '1px solid rgba(139,92,246,0.2)',
      borderBottom: '1px solid rgba(139,92,246,0.2)',
    }
  },
    React.createElement('div', {
      style: { flex: 1, height: 1, background: 'linear-gradient(90deg, transparent, rgba(139,92,246,0.3), transparent)' }
    }),
    React.createElement('span', {
      style: {
        fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
        letterSpacing: '2px', color: 'rgba(139,92,246,0.7)', whiteSpace: 'nowrap',
      }
    }, 'ROUND ' + round),
    React.createElement('div', {
      style: { flex: 1, height: 1, background: 'linear-gradient(90deg, transparent, rgba(139,92,246,0.3), transparent)' }
    }),
  );
}

function ConnectionErrorBanner({ status, error, currentRound, step }) {
  if (!error && status !== 'disconnected' && status !== 'error') return null;
  const isDisconnect = status === 'disconnected';
  return React.createElement('div', {
    style: {
      padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 8,
      background: isDisconnect ? 'rgba(239,68,68,0.08)' : 'rgba(245,158,11,0.08)',
      borderTop: '1px solid ' + (isDisconnect ? 'rgba(239,68,68,0.3)' : 'rgba(245,158,11,0.3)'),
      borderBottom: '1px solid ' + (isDisconnect ? 'rgba(239,68,68,0.3)' : 'rgba(245,158,11,0.3)'),
    }
  },
    React.createElement('div', {
      className: 'led ' + (isDisconnect ? 'led-red' : 'led-amber led-pulse'),
      style: { width: 6, height: 6, flexShrink: 0 },
    }),
    React.createElement('span', {
      style: { fontFamily: 'var(--font-mono)', fontSize: 10, color: isDisconnect ? '#ef4444' : '#f59e0b' },
    }, isDisconnect
      ? 'Connection lost — last received: Round ' + (currentRound || '?') + ', Step ' + (step || '?')
      : (error || 'Reconnecting...')
    ),
  );
}

function DebateTranscriptPanel({ utterances, activeSpeakerId, focusedId, voteTally, onClearFocus, roundDividers, currentRound, totalRounds, connectionStatus, connectionError, debateStep }) {
  const scrollRef = React.useRef(null);
  const autoScrollRef = React.useRef(true);
  const prevLenRef = React.useRef(0);

  // Filter logic
  const filtered = focusedId ? utterances.filter(u =>
    u.speakerId === focusedId ||
    u.text.toLowerCase().includes((AGENTS.find(a=>a.id===focusedId)?.name||'').toLowerCase()) ||
    u.stance === 'mediate'
  ) : utterances;

  // Auto-scroll
  React.useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      autoScrollRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 200;
    };
    el.addEventListener('scroll', onScroll);
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  React.useEffect(() => {
    if (autoScrollRef.current && scrollRef.current && utterances.length > prevLenRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
    prevLenRef.current = utterances.length;
  }, [utterances.length]);

  const panelStyle = {
    display: 'flex', flexDirection: 'column',
    background: 'var(--glass-bg)', backdropFilter: 'var(--glass-blur)',
    border: '1px solid var(--glass-border)', borderRadius: 14,
    boxShadow: 'var(--shadow-glass)', overflow: 'hidden', minHeight: 0, flex: 1,
    position: 'relative',
  };

  return React.createElement('div', { style: panelStyle },
    // Top highlight
    React.createElement('div', { style: { position: 'absolute', top: 0, left: 12, right: 12, height: 1,
      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2) 50%, transparent)', pointerEvents: 'none', zIndex: 1 } }),
    // Header
    React.createElement('div', {
      style: { padding: '10px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }
    },
      React.createElement('span', {
        style: { fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
          letterSpacing: '2px', color: 'rgba(255,255,255,0.35)' }
      }, 'DEBATE CHAMBER' + (currentRound && totalRounds ? '  ·  ROUND ' + currentRound + '/' + totalRounds : '')),
      focusedId
        ? React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
            React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: 'rgba(255,255,255,0.4)' } },
              'Viewing: ' + focusedId + ' — ' + filtered.length + ' of ' + utterances.length),
            React.createElement('span', {
              onClick: onClearFocus,
              style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: '#3b82f6', cursor: 'pointer' }
            }, 'Clear filter'),
          )
        : React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: 'rgba(255,255,255,0.25)' } },
            filtered.length + ' speeches'),
    ),
    // Transcript scroll
    React.createElement('div', {
      ref: scrollRef, className: 'panel-scroll',
      style: { flex: 1, overflowY: 'auto', minHeight: 0 }
    },
      filtered.length === 0
        ? React.createElement('div', { style: { padding: 32, textAlign: 'center', fontFamily: 'var(--font-mono)',
            fontSize: 11, color: 'rgba(255,255,255,0.2)' } },
            'Waiting for debate to begin...')
        : (() => {
            const dividerMap = {};
            (roundDividers || []).forEach(d => { dividerMap[d.afterIndex] = d.round; });
            const elements = [];
            filtered.forEach((u, i) => {
              if (dividerMap[i]) {
                elements.push(React.createElement(RoundDivider, { key: 'rd-' + dividerMap[i], round: dividerMap[i] }));
              }
              elements.push(React.createElement(UtteranceRow, {
                key: u.step + '-' + u.speakerId + '-' + i, u,
                isActive: activeSpeakerId === u.speakerId && i === filtered.length - 1,
                isNew: i === filtered.length - 1,
              }));
            });
            return elements;
          })(),
    ),
    // Connection error banner
    React.createElement(ConnectionErrorBanner, {
      status: connectionStatus, error: connectionError,
      currentRound: currentRound, step: debateStep,
    }),
    // Vote
    React.createElement(VoteBar, { tally: voteTally }),
  );
}

Object.assign(window, { DebateTranscriptPanel, VoteBar, StancePill, RoundDivider, ConnectionErrorBanner, STANCE_STYLES });
