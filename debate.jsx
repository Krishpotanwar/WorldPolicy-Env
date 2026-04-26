/* DebateTranscriptPanel + VoteBar + TypewriterText + ThinkingIndicator */
/* STANCE_MAP imported from agents.js (window.STANCE_MAP) */
const STANCE_STYLES = window.STANCE_MAP;

const TYPEWRITER_WPS = 8;

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

function TypewriterText({ text, wordsPerSecond }) {
  const words = React.useMemo(() => text.split(/(\s+)/), [text]);
  const [visibleCount, setVisibleCount] = React.useState(0);
  const totalWords = React.useMemo(() => words.filter(w => w.trim()).length, [words]);
  const done = visibleCount >= totalWords;

  React.useEffect(() => {
    setVisibleCount(0);
    const interval = 1000 / (wordsPerSecond || TYPEWRITER_WPS);
    let count = 0;
    const timer = setInterval(() => {
      count++;
      setVisibleCount(count);
      if (count >= words.filter(w => w.trim()).length) clearInterval(timer);
    }, interval);
    return () => clearInterval(timer);
  }, [text]);

  if (done) return '"' + text + '"';

  let wordsSeen = 0;
  let result = '"';
  for (let i = 0; i < words.length; i++) {
    if (words[i].trim()) {
      wordsSeen++;
      if (wordsSeen > visibleCount) break;
    }
    result += words[i];
  }

  return React.createElement('span', null,
    result,
    React.createElement('span', {
      style: {
        display: 'inline-block', width: 6, height: 14, marginLeft: 2,
        background: 'rgba(255,255,255,0.6)',
        animation: 'blink-cursor 0.8s steps(1) infinite',
        verticalAlign: 'text-bottom',
      }
    }),
  );
}

function ThinkingIndicator({ speakerTint }) {
  return React.createElement('div', {
    style: {
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.04)',
    }
  },
    React.createElement('div', {
      style: {
        width: 4, height: 24, flexShrink: 0, borderRadius: 2,
        background: speakerTint || 'rgba(255,255,255,0.2)',
      }
    }),
    React.createElement('div', { style: { display: 'flex', gap: 4, alignItems: 'center' } },
      [0, 1, 2].map(i =>
        React.createElement('div', {
          key: i,
          style: {
            width: 5, height: 5, borderRadius: '50%',
            background: 'rgba(255,255,255,0.35)',
            animation: 'thinking-dot 1.4s ease-in-out ' + (i * 0.2) + 's infinite',
          }
        })
      ),
    ),
    React.createElement('span', {
      style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: 'rgba(255,255,255,0.2)',
        letterSpacing: '1px', marginLeft: 4 }
    }, 'PREPARING RESPONSE...'),
  );
}

function ExpandableText({ text, isNew }) {
  const CHAR_LIMIT = 200;
  const isLong = text.length > CHAR_LIMIT;
  const [expanded, setExpanded] = React.useState(false);

  if (isNew) {
    return React.createElement(TypewriterText, { text: text, wordsPerSecond: TYPEWRITER_WPS });
  }

  if (!isLong) return '"' + text + '"';

  if (expanded) {
    return React.createElement('span', null,
      '"' + text + '"',
      React.createElement('span', {
        onClick: (e) => { e.stopPropagation(); setExpanded(false); },
        style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: '#3b82f6',
          cursor: 'pointer', marginLeft: 6 },
      }, 'Show less'),
    );
  }

  return React.createElement('span', null,
    '"' + text.slice(0, CHAR_LIMIT) + '..."',
    React.createElement('span', {
      onClick: (e) => { e.stopPropagation(); setExpanded(true); },
      style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: '#3b82f6',
        cursor: 'pointer', marginLeft: 6 },
    }, 'Show more'),
  );
}

function CitationExpander({ citation, isAuthoritative }) {
  const [open, setOpen] = React.useState(false);
  const chips = citation.split(';').map(s => s.trim()).filter(Boolean);

  return React.createElement('div', { style: { marginTop: 6 } },
    React.createElement('div', {
      style: { display: 'flex', alignItems: 'center', gap: 8 }
    },
      React.createElement('span', {
        onClick: () => setOpen(!open),
        style: {
          fontFamily: 'var(--font-mono)', fontSize: 9, color: '#eab308',
          cursor: 'pointer', userSelect: 'none',
        }
      }, open ? 'Hide mandate ▾' : 'View mandate ▸'),
      React.createElement('span', {
        style: {
          fontFamily: 'var(--font-mono)', fontSize: 8, fontWeight: 700,
          letterSpacing: '0.5px', padding: '1px 6px', borderRadius: 3,
          background: isAuthoritative ? 'rgba(34,197,94,0.12)' : 'rgba(245,158,11,0.12)',
          border: '1px solid ' + (isAuthoritative ? 'rgba(34,197,94,0.25)' : 'rgba(245,158,11,0.25)'),
          color: isAuthoritative ? '#22c55e' : '#f59e0b',
        }
      }, isAuthoritative ? 'WITHIN MANDATE ✓' : 'ADVISORY'),
    ),
    open && React.createElement('div', {
      style: { display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }
    },
      chips.map((chip, i) =>
        React.createElement('span', {
          key: i,
          style: {
            fontFamily: 'var(--font-mono)', fontSize: 9, padding: '2px 6px', borderRadius: 3,
            background: 'rgba(234,179,8,0.1)', border: '1px solid rgba(234,179,8,0.25)',
            color: 'rgba(234,179,8,0.8)',
          }
        }, chip)
      ),
    ),
  );
}

function UtteranceRow({ u, isActive, isNew }) {
  const isUN = u.speakerId === 'UN';
  const pnlText = u.pnlDeltas ? Object.entries(u.pnlDeltas)
    .filter(([,v]) => v !== 0)
    .map(([k,v]) => k + ' ' + (v > 0 ? '+' : '') + v.toFixed(3))
    .join(', ') : '';

  const row = React.createElement('div', {
    className: isNew ? 'glass-appear' : '',
    style: {
      display: 'flex', gap: 0, padding: '10px 12px 10px 0',
      background: isUN ? 'rgba(234,179,8,0.04)' : (isActive ? u.speakerTint + '0f' : 'transparent'),
      borderBottom: '1px solid rgba(255,255,255,0.04)',
      transition: 'background 0.3s',
    }
  },
    React.createElement('div', {
      style: {
        width: isActive ? 6 : 4, flexShrink: 0, borderRadius: 2,
        background: u.speakerTint + (isActive ? 'ff' : 'cc'),
        marginRight: 12,
        boxShadow: isActive ? '0 0 8px ' + u.speakerTint + '40' : 'none',
      }
    }),
    React.createElement('div', { style: { flex: 1, minWidth: 0 } },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 } },
        React.createElement('span', {
          style: { fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
            letterSpacing: '1.2px', color: u.speakerTint }
        }, u.speakerName.toUpperCase()),
        isUN && React.createElement('span', {
          style: {
            fontFamily: 'var(--font-mono)', fontSize: 8, fontWeight: 700,
            letterSpacing: '0.8px', padding: '1px 6px', borderRadius: 3,
            background: 'rgba(234,179,8,0.12)', border: '1px solid rgba(234,179,8,0.3)',
            color: '#eab308',
          }
        }, 'UN MEDIATOR'),
        React.createElement(StancePill, { stance: u.stance }),
        isActive && React.createElement('div', {
          style: { display: 'flex', alignItems: 'center', gap: 4, marginLeft: 'auto' }
        },
          React.createElement('div', { className: 'led led-green led-pulse', style: { width: 6, height: 6 } }),
          React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 8, color: 'rgba(255,255,255,0.35)' } }, 'SPEAKING'),
        ),
      ),
      React.createElement('div', {
        style: {
          fontFamily: 'var(--font-ui)', fontSize: 13, lineHeight: 1.55,
          color: 'rgba(255,255,255,0.85)',
        }
      }, React.createElement(ExpandableText, { text: u.text, isNew: isNew })),
      isUN && u.authorityCitation && React.createElement(CitationExpander, {
        citation: u.authorityCitation,
        isAuthoritative: u.isAuthoritative,
      }),
      React.createElement('div', {
        style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: 'rgba(255,255,255,0.25)',
          marginTop: 6 }
      },
        'step ' + u.step + (pnlText ? '  ·  pnlΔ: ' + pnlText : ''),
      ),
    ),
  );

  if (isUN) {
    return React.createElement(React.Fragment, null,
      React.createElement('div', {
        style: { height: 1, background: 'linear-gradient(90deg, transparent, rgba(234,179,8,0.35) 50%, transparent)' }
      }),
      row,
    );
  }
  return row;
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

function DebateOutcomeBanner({ voteTally }) {
  if (!voteTally) return null;
  const total = voteTally.support + voteTally.oppose + voteTally.modify || 1;
  const passed = voteTally.support > voteTally.oppose;
  return React.createElement('div', {
    style: {
      margin: '8px 12px', padding: '12px 16px', borderRadius: 10,
      background: passed ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
      border: '1px solid ' + (passed ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'),
    }
  },
    React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 } },
      React.createElement('div', { className: 'led ' + (passed ? 'led-green' : 'led-red'), style: { width: 8, height: 8 } }),
      React.createElement('span', {
        style: { fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
          letterSpacing: '1px', color: passed ? '#22c55e' : '#ef4444' }
      }, passed ? 'RESOLUTION PASSED' : 'RESOLUTION FAILED'),
    ),
    React.createElement('div', {
      style: { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.5)', lineHeight: 1.6 }
    },
      'Support: ' + voteTally.support + ' (' + Math.round(voteTally.support/total*100) + '%)' +
      '  ·  Oppose: ' + voteTally.oppose + ' (' + Math.round(voteTally.oppose/total*100) + '%)' +
      '  ·  Modify: ' + voteTally.modify + ' (' + Math.round(voteTally.modify/total*100) + '%)'
    ),
  );
}

function DebateTranscriptPanel({ utterances, activeSpeakerId, focusedId, voteTally, onClearFocus,
  roundDividers, currentRound, totalRounds, connectionStatus, connectionError, debateStep,
  debateHistory, onLoadHistory }) {

  const scrollRef = React.useRef(null);
  const autoScrollRef = React.useRef(true);
  const prevLenRef = React.useRef(0);
  const [historyOpen, setHistoryOpen] = React.useState(false);

  const filtered = focusedId ? utterances.filter(u =>
    u.speakerId === focusedId ||
    u.text.toLowerCase().includes((AGENTS.find(a=>a.id===focusedId)?.name||'').toLowerCase()) ||
    u.stance === 'mediate'
  ) : utterances;

  const isStreaming = connectionStatus === 'streaming';
  const isComplete = connectionStatus === 'complete';

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
      requestAnimationFrame(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      });
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

  const history = debateHistory || [];

  return React.createElement('div', { style: panelStyle },
    React.createElement('div', { style: { position: 'absolute', top: 0, left: 12, right: 12, height: 1,
      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2) 50%, transparent)', pointerEvents: 'none', zIndex: 1 } }),

    React.createElement('div', {
      style: { padding: '10px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }
    },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
        React.createElement('span', {
          style: { fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
            letterSpacing: '2px', color: 'rgba(255,255,255,0.35)' }
        }, 'DEBATE CHAMBER' + (currentRound && totalRounds ? '  ·  ROUND ' + currentRound + '/' + totalRounds : '')),

        isStreaming && React.createElement('div', {
          style: { display: 'flex', alignItems: 'center', gap: 4 }
        },
          React.createElement('div', { className: 'led led-green led-pulse', style: { width: 5, height: 5 } }),
          React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 8, color: '#22c55e' } }, 'LIVE'),
        ),

        isComplete && utterances.length > 0 && React.createElement('span', {
          style: { fontFamily: 'var(--font-mono)', fontSize: 8, color: 'rgba(255,255,255,0.3)',
            padding: '1px 6px', borderRadius: 3, background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.08)' }
        }, 'ENDED'),
      ),

      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, position: 'relative' } },
        focusedId
          ? React.createElement(React.Fragment, null,
              React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: 'rgba(255,255,255,0.4)' } },
                'Viewing: ' + focusedId + ' — ' + filtered.length + ' of ' + utterances.length),
              React.createElement('span', {
                onClick: onClearFocus,
                style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: '#3b82f6', cursor: 'pointer' }
              }, 'Clear filter'),
            )
          : React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: 'rgba(255,255,255,0.25)' } },
              filtered.length + ' speeches'),

        history.length > 0 && React.createElement('span', {
          onClick: () => setHistoryOpen(!historyOpen),
          style: {
            fontFamily: 'var(--font-mono)', fontSize: 9, color: '#8b5cf6', cursor: 'pointer',
            padding: '2px 6px', borderRadius: 3,
            background: historyOpen ? 'rgba(139,92,246,0.15)' : 'transparent',
            border: '1px solid ' + (historyOpen ? 'rgba(139,92,246,0.3)' : 'transparent'),
          }
        }, 'History (' + history.length + ')'),

        historyOpen && React.createElement('div', {
          style: {
            position: 'absolute', top: '100%', right: 0, marginTop: 4, zIndex: 50,
            background: 'rgba(10,12,20,0.95)', border: '1px solid rgba(139,92,246,0.3)',
            borderRadius: 8, padding: 4, minWidth: 220, maxHeight: 200, overflowY: 'auto',
            boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
          }
        },
          history.map((h, i) =>
            React.createElement('div', {
              key: i,
              onClick: () => { onLoadHistory && onLoadHistory(h); setHistoryOpen(false); },
              style: {
                padding: '6px 10px', cursor: 'pointer', borderRadius: 4,
                fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.6)',
                transition: 'background 0.15s',
              },
              onMouseEnter: (e) => { e.currentTarget.style.background = 'rgba(139,92,246,0.1)'; },
              onMouseLeave: (e) => { e.currentTarget.style.background = 'transparent'; },
            },
              React.createElement('div', { style: { color: 'rgba(255,255,255,0.8)', marginBottom: 2 } },
                (h.crisisType || 'Debate').replace(/_/g, ' ')),
              React.createElement('div', { style: { fontSize: 8, color: 'rgba(255,255,255,0.3)' } },
                new Date(h.timestamp).toLocaleString() + ' · ' + h.utterances.length + ' speeches · ' +
                h.rounds + ' rounds'),
            )
          ),
        ),
      ),
    ),

    React.createElement('div', {
      ref: scrollRef, className: 'panel-scroll',
      style: { flex: 1, overflowY: 'auto', minHeight: 0 }
    },
      filtered.length === 0
        ? React.createElement('div', { style: { padding: 32, textAlign: 'center', fontFamily: 'var(--font-mono)',
            fontSize: 11, color: 'rgba(255,255,255,0.2)' } },
            isStreaming ? 'Connecting to debate stream...' : 'Waiting for debate to begin...')
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
                isNew: i === filtered.length - 1 && isStreaming,
              }));
            });

            if (isComplete && voteTally) {
              elements.push(React.createElement(DebateOutcomeBanner, { key: 'outcome-banner', voteTally: voteTally }));
            }

            if (isStreaming && filtered.length > 0) {
              const lastAgent = AGENTS.find(a => a.id === activeSpeakerId);
              elements.push(React.createElement(ThinkingIndicator, {
                key: 'thinking',
                speakerTint: lastAgent?.tint,
              }));
            }

            return elements;
          })(),
    ),

    React.createElement(ConnectionErrorBanner, {
      status: connectionStatus, error: connectionError,
      currentRound: currentRound, step: debateStep,
    }),
    React.createElement(VoteBar, { tally: voteTally }),
  );
}

Object.assign(window, {
  DebateTranscriptPanel, VoteBar, StancePill, RoundDivider, ConnectionErrorBanner,
  ThinkingIndicator, TypewriterText, ExpandableText, DebateOutcomeBanner, CitationExpander,
  STANCE_STYLES,
});
