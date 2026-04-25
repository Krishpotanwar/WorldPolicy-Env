/* ChamberView — theater mode + LayoutModeToggle + UNESCOMediatorCard + RhetoricColdWarAlert */

function LayoutModeToggle({ mode, onChange }) {
  const modes = ['globe', 'split', 'chamber'];
  const labels = ['Globe', 'Split', 'Chamber'];
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
          borderRight: i < 2 ? '1px solid rgba(255,255,255,0.08)' : 'none',
          transition: 'all 0.15s ease',
        }
      }, labels[i])
    ),
  );
}

/* ── UNESCOMediatorCard ── */
function UNESCOMediatorCard({ utterance, authorityScope, heritageAtRisk, isAuthoritative }) {
  if (!utterance) return null;
  const cardStyle = {
    background: 'linear-gradient(135deg, rgba(20,184,166,0.06) 0%, rgba(255,255,255,0.04) 50%, rgba(20,184,166,0.03) 100%)',
    backdropFilter: 'var(--glass-blur)', border: '1px solid rgba(20,184,166,0.25)',
    borderRadius: 14, boxShadow: 'var(--shadow-glass)', padding: 16,
    width: 320, position: 'relative', overflow: 'hidden',
  };

  return React.createElement('div', { className: 'glass-appear', style: cardStyle },
    React.createElement('div', { style: { position: 'absolute', top: 0, left: 12, right: 12, height: 1,
      background: 'linear-gradient(90deg, transparent, rgba(20,184,166,0.4) 50%, transparent)', pointerEvents: 'none' } }),
    // Header
    React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 } },
      React.createElement(UNESCOLaurel, { size: 24 }),
      React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
        letterSpacing: '1.5px', color: '#14b8a6' } }, 'UNESCO · MEDIATOR DOSSIER'),
    ),
    // Authority chips
    authorityScope && authorityScope.length > 0 && React.createElement('div', {
      style: { display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10 }
    },
      authorityScope.map((s, i) =>
        React.createElement('span', { key: i, style: {
          fontFamily: 'var(--font-mono)', fontSize: 9, padding: '2px 6px', borderRadius: 3,
          background: 'rgba(20,184,166,0.15)', border: '1px solid rgba(20,184,166,0.3)',
          color: '#14b8a6',
        } }, s)
      ),
    ),
    // Heritage at risk
    heritageAtRisk && heritageAtRisk.length > 0 && [
      React.createElement('div', { key: 'hl', style: { fontFamily: 'var(--font-mono)', fontSize: 9,
        fontWeight: 700, letterSpacing: '1.5px', color: 'rgba(255,255,255,0.3)', marginBottom: 6 } },
        'HERITAGE AT RISK'),
      ...heritageAtRisk.slice(0, 3).map((h, i) => {
        const agent = AGENTS.find(a => a.id === h.countryId);
        return React.createElement('div', { key: i, style: { display: 'flex', alignItems: 'center', gap: 8,
          marginBottom: 4 } },
          React.createElement('div', { style: { width: 6, height: 6, borderRadius: '50%',
            background: agent?.tint || '#fff', flexShrink: 0 } }),
          React.createElement('span', { style: { fontFamily: 'var(--font-ui)', fontSize: 10,
            color: 'rgba(255,255,255,0.6)', flex: 1 } }, h.siteName),
          React.createElement('div', { style: { width: 48, height: 4, borderRadius: 2,
            background: 'rgba(255,255,255,0.06)', overflow: 'hidden' } },
            React.createElement('div', { style: { height: '100%', width: (h.riskScore * 100) + '%',
              borderRadius: 2,
              background: h.riskScore > 0.7 ? '#ef4444' : h.riskScore > 0.4 ? '#f59e0b' : '#22c55e' } }),
          ),
        );
      }),
    ],
    // Quote
    React.createElement('div', { style: { marginTop: 10, padding: '8px 10px', borderLeft: '2px solid rgba(20,184,166,0.4)',
      background: 'rgba(20,184,166,0.06)', borderRadius: '0 6px 6px 0' } },
      React.createElement('div', { style: { fontFamily: 'var(--font-ui)', fontSize: 12, fontStyle: 'italic',
        color: 'rgba(255,255,255,0.75)', lineHeight: 1.5 } },
        '"' + utterance.text + '"'),
    ),
    // Authority badge
    React.createElement('div', { style: { display: 'flex', justifyContent: 'flex-end', marginTop: 8 } },
      React.createElement('span', {
        style: {
          fontFamily: 'var(--font-mono)', fontSize: 8, fontWeight: 700, letterSpacing: '1px',
          padding: '2px 8px', borderRadius: 3,
          background: isAuthoritative ? 'rgba(34,197,94,0.15)' : 'rgba(245,158,11,0.15)',
          border: '1px solid ' + (isAuthoritative ? 'rgba(34,197,94,0.3)' : 'rgba(245,158,11,0.3)'),
          color: isAuthoritative ? '#22c55e' : '#f59e0b',
        }
      }, isAuthoritative ? 'WITHIN MANDATE ✓' : 'ADVISORY — NON-BINDING'),
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
function ChamberView({ activeSpeakerId, utterances, focusedId, voteTally, onFocus, onClearFocus }) {
  const agents = AGENTS;
  // Semicircle layout — UNESCO at top center
  const reordered = [agents[0], agents[1], agents[2], agents[6], agents[3], agents[4], agents[5]]; // UNESCO center
  const count = reordered.length;

  return React.createElement('div', {
    style: {
      flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0,
      background: 'radial-gradient(ellipse at 50% 80%, rgba(59,130,246,0.04) 0%, #050810 60%)',
    }
  },
    // Semicircle portraits
    React.createElement('div', {
      style: {
        position: 'relative', height: 220, flexShrink: 0,
        margin: '20px auto', width: '100%', maxWidth: 700,
        overflow: 'visible',
      }
    },
      reordered.map((agent, i) => {
        // Tighter arc: -70° to +70° (140° spread) to keep agents within bounds
        const angle = -70 + (140 / (count - 1)) * i;
        const rad = angle * Math.PI / 180;
        // Use percentage-based positioning relative to the container
        const x = 50 + Math.sin(rad) * 42; // 42% spread from center
        const y = 30 + (1 - Math.cos(rad)) * 90; // vertical arc depth
        const isActive = activeSpeakerId === agent.id;

        return React.createElement('div', {
          key: agent.id,
          style: {
            position: 'absolute', left: x + '%', top: y,
            transform: 'translateX(-50%)' + (isActive ? ' scale(1.3) translateY(-16px)' : ''),
            transition: 'all 0.5s cubic-bezier(0.16,1,0.3,1)',
            zIndex: isActive ? 10 : 1,
          }
        },
          // Spotlight for active
          isActive && React.createElement('div', {
            style: {
              position: 'absolute', top: -100, left: '50%', transform: 'translateX(-50%)',
              width: 120, height: 160,
              background: 'conic-gradient(from 180deg at 50% 0%, transparent 150deg, ' + agent.tint + '20 170deg, ' + agent.tint + '30 180deg, ' + agent.tint + '20 190deg, transparent 210deg)',
              pointerEvents: 'none',
            }
          }),
          React.createElement(AgentPortrait, {
            agent,
            isActive,
            isInvolved: true,
            isPeripheral: false,
            isFocused: focusedId === agent.id,
            tooltip: null,
            onClick: () => onFocus(agent.id),
          }),
        );
      }),
    ),
    // Transcript — larger font
    React.createElement('div', { style: { flex: 1, margin: '0 40px', minHeight: 0 } },
      React.createElement(DebateTranscriptPanel, {
        utterances, activeSpeakerId, focusedId, voteTally, onClearFocus,
      }),
    ),
  );
}

Object.assign(window, { LayoutModeToggle, UNESCOMediatorCard, RhetoricColdWarAlert, ChamberView });
