/* ChamberView — theater mode + LayoutModeToggle + RhetoricColdWarAlert */

function LayoutModeToggle({ mode, onChange }) {
  const modes = ['globe', 'split', 'chamber', 'case_studies'];
  const labels = ['Globe', 'Split', 'Chamber', 'Case Studies'];
  return React.createElement('div', {
    style: {
      display: 'inline-flex', borderRadius: 10, overflow: 'hidden',
      border: '1px solid var(--glass-border-bright)',
      boxShadow: 'var(--shadow-button)',
    }
  },
    modes.map((m, i) =>
      React.createElement('button', {
        key: m,
        onClick: () => onChange(m),
        style: {
          fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
          letterSpacing: '0.5px', padding: '6px 16px', border: 'none', cursor: 'pointer',
          color: mode === m ? '#fff' : 'rgba(255,255,255,0.5)',
          background: mode === m
            ? 'linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(255,255,255,0.06) 100%)'
            : 'linear-gradient(180deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 100%)',
          boxShadow: mode === m ? 'inset 0 2px 4px rgba(0,0,0,0.4), inset 0 -1px 0 rgba(255,255,255,0.05)' : 'none',
          borderRight: i < 3 ? '1px solid rgba(255,255,255,0.08)' : 'none',
          transition: 'all 0.15s ease',
        }
      }, labels[i])
    ),
  );
}

/* ── RhetoricColdWarAlert ── */
function RhetoricColdWarAlert({ alert, onDismiss }) {
  const [visible, setVisible] = React.useState(true);
  React.useEffect(() => {
    const t = setTimeout(() => { setVisible(false); onDismiss && onDismiss(); }, 12000);
    return () => clearTimeout(t);
  }, []);

  if (!visible || !alert) return null;

  return React.createElement('div', {
    className: 'glass-appear',
    onClick: () => { setVisible(false); onDismiss && onDismiss(); },
    style: {
      position: 'fixed', top: 60, right: 16, zIndex: 200,
      background: 'linear-gradient(135deg, rgba(239,68,68,0.1) 0%, rgba(255,255,255,0.04) 100%)',
      backdropFilter: 'var(--glass-blur)', border: '1px solid rgba(239,68,68,0.35)',
      borderRadius: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.5)', padding: '12px 16px',
      maxWidth: 360, cursor: 'pointer',
    }
  },
    React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 } },
      React.createElement('div', { className: 'led led-red led-pulse' }),
      React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700,
        color: '#ef4444', letterSpacing: '0.5px' } }, 'EMERGENT: RHETORIC COLD WAR'),
    ),
    React.createElement('div', { style: { fontFamily: 'var(--font-ui)', fontSize: 11,
      color: 'rgba(255,255,255,0.7)', lineHeight: 1.4, marginBottom: 4 } },
      alert.agents[0] + ' and ' + alert.agents[1] + ' — ' + alert.count + ' consecutive OPPOSE stances'),
    React.createElement('div', { style: { fontFamily: 'var(--font-mono)', fontSize: 9,
      color: 'rgba(255,255,255,0.25)' } },
      'Topic: ' + alert.topic + '  ·  rhetoric_divergence_index=' + alert.index.toFixed(2)),
  );
}

/* ── ChamberView (theater mode) ── */
function ChamberView({ activeSpeakerId, utterances, focusedId, voteTally, onFocus, onClearFocus,
  roundDividers, currentRound, totalRounds, connectionStatus, connectionError, debateStep,
  debateHistory, onLoadHistory }) {

  return React.createElement('div', {
    style: {
      flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0,
      background: 'radial-gradient(ellipse at 50% 80%, rgba(59,130,246,0.04) 0%, #050810 60%)',
    }
  },
    React.createElement('div', { style: { flex: 1, margin: '0 24px', minHeight: 0, display: 'flex' } },
      React.createElement(DebateTranscriptPanel, {
        utterances, activeSpeakerId, focusedId, voteTally, onClearFocus,
        roundDividers, currentRound, totalRounds, connectionStatus, connectionError, debateStep,
        debateHistory, onLoadHistory,
      }),
    ),
  );
}

Object.assign(window, { LayoutModeToggle, RhetoricColdWarAlert, ChamberView });
