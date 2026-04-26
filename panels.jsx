/* Panel Components — all glass cards for WorldPolicy V6.1 */

/* ── ClaimBoundaryBanner ── */
function ClaimBoundaryBanner({ mode, checkpoint }) {
  const bannerStyles = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 20px', background: 'rgba(255,255,255,0.03)',
    backdropFilter: 'blur(24px)', borderBottom: '1px solid rgba(255,255,255,0.06)',
    fontFamily: 'var(--font-mono)', fontSize: '11px', flexShrink: 0,
  };
  return React.createElement('div', { style: bannerStyles },
    React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
      React.createElement('span', { style: { color: 'rgba(255,255,255,0.3)' } }, '⚙'),
      React.createElement('span', { style: { color: 'rgba(255,255,255,0.35)', letterSpacing: '1px' } }, 'SCRIPTED EVENTS'),
      React.createElement('span', { style: { color: 'rgba(255,255,255,0.12)', margin: '0 8px' } }, '────────'),
      React.createElement('span', { style: { color: 'rgba(255,255,255,0.4)' } }, 'World crises and event sequences'),
    ),
    React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
      React.createElement('span', { style: { color: '#60a5fa' } }, '🧠'),
      React.createElement('span', { style: { color: '#60a5fa', letterSpacing: '1px' } }, 'TRAINED POLICY'),
      React.createElement('span', { style: { color: 'rgba(255,255,255,0.12)', margin: '0 8px' } }, '────────'),
      React.createElement('span', { style: { color: 'rgba(255,255,255,0.4)' } },
        'Agent responses, reward curves (checkpoint: ' + (checkpoint || 'mappo_50k.pt') + ')'
      ),
    )
  );
}

/* ── CrisisBriefCard ── */
function CrisisBriefCard({ brief, isLoading }) {
  const cardStyle = {
    background: 'linear-gradient(135deg, rgba(239,68,68,0.06) 0%, rgba(255,255,255,0.04) 50%, rgba(239,68,68,0.03) 100%)',
    backdropFilter: 'var(--glass-blur)', border: '1px solid rgba(239,68,68,0.25)',
    borderRadius: 14, boxShadow: '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.08)',
    padding: 16, position: 'relative', overflow: 'hidden',
  };
  if (!brief && !isLoading) return null;

  const riskColors = { LOW: '#22c55e', MEDIUM: '#f59e0b', HIGH: '#f97316', CRITICAL: '#ef4444' };
  const riskColor = brief ? (riskColors[brief.risk_level] || '#ef4444') : '#ef4444';

  return React.createElement('div', { className: 'glass-appear', style: cardStyle },
    React.createElement('div', { style: { position: 'absolute', top: 0, left: 12, right: 12, height: 1,
      background: 'linear-gradient(90deg, transparent, rgba(239,68,68,0.4) 50%, transparent)', pointerEvents: 'none' } }),
    // Header
    React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 } },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
        React.createElement('span', { style: { fontSize: 14 } }, '🇺🇳'),
        React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
          letterSpacing: '1.5px', color: 'rgba(255,255,255,0.5)' } }, 'UN SECURITY COUNCIL'),
      ),
      brief && React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 6 } },
        React.createElement('div', { className: 'led ' + (brief.risk_level === 'CRITICAL' ? 'led-red led-pulse' : brief.risk_level === 'HIGH' ? 'led-amber' : 'led-green') }),
        React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, color: riskColor } }, brief.risk_level),
      ),
    ),
    // Ruled line
    React.createElement('div', { style: { height: 1, background: 'linear-gradient(90deg, transparent, rgba(239,68,68,0.3) 15%, rgba(239,68,68,0.15) 85%, transparent)', margin: '0 0 10px' } }),
    // Crisis type + step
    brief && React.createElement('div', { style: { fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.4)', marginBottom: 10 } },
      (brief.crisis_type || 'NATURAL DISASTER') + ' — South Asia  •  Step ' + (brief.step || 0)
    ),
    // Situation
    React.createElement('div', { style: { fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700, letterSpacing: '1.5px', color: 'rgba(239,68,68,0.6)', marginBottom: 4 } }, 'SITUATION'),
    React.createElement('div', { style: { fontFamily: 'var(--font-ui)', fontSize: 12, color: 'rgba(255,255,255,0.7)', lineHeight: 1.5, marginBottom: 12 } },
      isLoading ? 'Generating briefing...' : (brief ? brief.brief : '')
    ),
    // Llama recommendation
    brief && brief.priority_response && [
      React.createElement('div', { key: 'lbl', style: { fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700, letterSpacing: '1.5px', color: 'rgba(59,130,246,0.7)', marginBottom: 4 } }, 'META LLAMA RECOMMENDATION'),
      React.createElement('div', { key: 'val', style: { fontFamily: 'var(--font-ui)', fontSize: 12, color: 'rgba(200,220,255,0.85)', lineHeight: 1.5, marginBottom: 12,
        padding: '8px 10px', background: 'rgba(59,130,246,0.08)', borderRadius: 8, borderLeft: '2px solid rgba(59,130,246,0.4)' } },
        brief.priority_response
      ),
    ],
    // Footer
    React.createElement('div', { style: { height: 1, background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.06) 50%, transparent)', margin: '4px 0 8px' } }),
    React.createElement('div', { style: { fontFamily: 'var(--font-mono)', fontSize: 9, color: 'rgba(255,255,255,0.25)' } },
      'Generated by Meta Llama 3.3-70b via Groq  •  Cached'
    ),
  );
}

/* ── TrainingFactsCard ── */
function TrainingFactsCard() {
  const facts = [
    ['Architecture', 'Shared MLP 36→128→128 + 6 actor heads'],
    ['Critic', '216→256→256→1 (centralized)'],
    ['Parameters', '~450K'],
    ['Training Steps', '50,000 parallel env steps'],
    ['Rollout Length', '1,024'],
    ['Checkpoint', 'mappo_50k.pt  [SHA: a3f2c8...]'],
    ['Framework', 'PyTorch 2.x'],
  ];
  const cardStyle = {
    background: 'linear-gradient(180deg, rgba(20,28,48,0.95) 0%, rgba(12,18,35,0.98) 100%)',
    backdropFilter: 'var(--glass-blur)', border: '1px solid rgba(255,255,255,0.10)',
    borderRadius: 12, boxShadow: 'var(--shadow-glass)', padding: '14px 16px',
    fontFamily: 'var(--font-mono)', position: 'relative',
  };
  return React.createElement('div', { className: 'glass-appear', style: cardStyle },
    React.createElement('div', { style: { position: 'absolute', top: 0, left: 12, right: 12, height: 1,
      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2) 50%, transparent)', pointerEvents: 'none' } }),
    React.createElement('div', { style: { fontSize: 10, fontWeight: 700, letterSpacing: '2px', color: 'rgba(255,255,255,0.35)',
      borderBottom: '1px solid rgba(255,255,255,0.07)', paddingBottom: 8, marginBottom: 8 } },
      'MAPPO POLICY — TRAINING PROVENANCE [DEMO]'
    ),
    ...facts.map(([k, v], i) =>
      React.createElement('div', { key: i, style: { display: 'grid', gridTemplateColumns: '120px 1fr', gap: '4px 12px',
        padding: '3px 0', borderBottom: i < facts.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none' } },
        React.createElement('span', { style: { fontSize: 10, color: 'rgba(255,255,255,0.35)' } }, k),
        React.createElement('span', { style: { fontSize: 10, color: 'rgba(255,255,255,0.8)' } }, v),
      )
    ),
    // Status LEDs
    React.createElement('div', { style: { display: 'flex', gap: 16, marginTop: 10, paddingTop: 8,
      borderTop: '1px solid rgba(255,255,255,0.06)' } },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'rgba(255,255,255,0.5)' } },
        React.createElement('div', { className: 'led led-green', style: { width: 8, height: 8 } }), 'Training complete'
      ),
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'rgba(255,255,255,0.5)' } },
        React.createElement('div', { className: 'led led-green', style: { width: 8, height: 8 } }), 'Checkpoint verified'
      ),
    ),
  );
}

/* ── EmergentBadgePanel ── */
function EmergentBadgePanel({ coldWar, armsRace, freeRider }) {
  const badges = [
    { label: 'COLD WAR BIFURCATION', active: coldWar.detected, step: coldWar.step,
      desc: 'Two opposing blocs formed — self-organized',
      trigger: coldWar.trigger || 'bloc_count=2, cross_bloc_rel=-0.61', color: '#ef4444' },
    { label: 'ARMS RACE SPIRAL', active: armsRace.detected, step: armsRace.step,
      desc: 'All 6 nations militarizing simultaneously',
      trigger: armsRace.trigger || 'all Δmilitary>0 for 5 consecutive steps', color: '#f59e0b' },
    { label: 'FREE RIDER DETECTED', active: freeRider.count > 0, step: null,
      desc: 'Benefiting from pledges without contributing',
      trigger: freeRider.trigger || (freeRider.names.join(', ') + '  climate=0.68, pledge_rate=0.04'),
      extra: freeRider.count > 0 ? freeRider.count + ' nation' + (freeRider.count > 1 ? 's' : '') : null,
      color: '#8b5cf6' },
  ];
  const panelStyle = {
    background: 'linear-gradient(180deg, rgba(15,20,35,0.9) 0%, rgba(10,14,26,0.95) 100%)',
    backdropFilter: 'var(--glass-blur)', border: '1px solid var(--glass-border)',
    borderRadius: 14, boxShadow: 'var(--shadow-glass)', padding: 16,
    fontFamily: 'var(--font-mono)', position: 'relative',
  };
  return React.createElement('div', { className: 'glass-appear', style: panelStyle },
    React.createElement('div', { style: { position: 'absolute', top: 0, left: 12, right: 12, height: 1,
      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2) 50%, transparent)', pointerEvents: 'none' } }),
    React.createElement('div', { style: { fontSize: 10, fontWeight: 700, letterSpacing: '2px', color: 'rgba(255,255,255,0.35)',
      borderBottom: '1px solid rgba(255,255,255,0.07)', paddingBottom: 8, marginBottom: 12 } },
      'EMERGENT PHENOMENA MONITOR'
    ),
    ...badges.map((b, i) =>
      React.createElement('div', { key: i, style: {
        display: 'flex', gap: 10, padding: '8px 0', alignItems: 'flex-start',
        borderBottom: i < badges.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
        ...(b.active ? { borderLeft: '2px solid ' + b.color, paddingLeft: 8, background: b.color + '0a', borderRadius: '0 6px 6px 0' } : {}),
      } },
        React.createElement('div', { className: 'led ' + (b.active ? (b.color === '#ef4444' ? 'led-red led-pulse' : b.color === '#f59e0b' ? 'led-amber led-pulse' : 'led-blue led-pulse') : ''),
          style: { marginTop: 2 } }),
        React.createElement('div', { style: { flex: 1 } },
          React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' } },
            React.createElement('span', { style: { fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.75)' } }, b.label),
            React.createElement('span', { style: { fontSize: 10, fontWeight: 700, color: b.active ? b.color : 'rgba(255,255,255,0.2)' } },
              b.active ? ('DETECTED' + (b.step ? ' step ' + b.step : '') + (b.extra ? '  ' + b.extra : '')) : 'Not active'
            ),
          ),
          React.createElement('div', { style: { fontSize: 10, color: 'rgba(255,255,255,0.4)', marginTop: 2 } }, b.desc),
          React.createElement('div', { style: { fontSize: 9, color: 'rgba(255,255,255,0.2)', marginTop: 3 } },
            (b.active ? 'Trigger: ' : 'Condition: ') + b.trigger
          ),
        ),
      )
    ),
  );
}

/* ── EvalSummaryCard ── */
function EvalSummaryCard({ data, episodes, checkpoint }) {
  const maxReward = Math.max(...data.map(d => d.mean + d.std));
  const cardStyle = {
    background: 'var(--glass-bg)', backdropFilter: 'var(--glass-blur)',
    border: '1px solid var(--glass-border)', borderRadius: 14,
    boxShadow: 'var(--shadow-glass)', padding: 16, fontFamily: 'var(--font-mono)', position: 'relative',
  };
  return React.createElement('div', { className: 'glass-appear', style: cardStyle },
    React.createElement('div', { style: { position: 'absolute', top: 0, left: 12, right: 12, height: 1,
      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2) 50%, transparent)', pointerEvents: 'none' } }),
    React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', marginBottom: 4 } },
      React.createElement('span', { style: { fontSize: 10, fontWeight: 700, letterSpacing: '2px', color: 'rgba(255,255,255,0.35)' } }, 'POLICY EVALUATION'),
      React.createElement('span', { style: { fontSize: 9, color: 'rgba(255,255,255,0.25)' } }, episodes + ' episodes, 5 seeds'),
    ),
    React.createElement('div', { style: { fontSize: 9, color: 'rgba(255,255,255,0.2)', marginBottom: 12 } }, 'Checkpoint: ' + checkpoint),
    // Bars
    ...data.map((d, i) => {
      const pct = ((d.mean / maxReward) * 100).toFixed(0);
      const isWinner = d.name === 'MAPPO';
      return React.createElement('div', { key: i, style: {
        padding: '6px 8px', marginBottom: 4, borderRadius: 8,
        ...(isWinner ? { background: 'rgba(59,130,246,0.06)', borderLeft: '2px solid #3b82f6' } : {}),
      } },
        React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 } },
          React.createElement('span', { style: { fontSize: 11, fontWeight: 600, color: isWinner ? '#60a5fa' : 'rgba(255,255,255,0.6)' } },
            (isWinner ? '▶ ' : '') + d.name),
          React.createElement('span', { style: { fontSize: 10, color: 'rgba(255,255,255,0.5)' } },
            d.mean.toFixed(2) + ' ± ' + d.std.toFixed(2) + (isWinner ? '  ✓' : '')),
        ),
        React.createElement('div', { style: { height: 8, background: 'rgba(255,255,255,0.06)', borderRadius: 4,
          border: '1px solid rgba(255,255,255,0.04)', boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.4)', overflow: 'hidden' } },
          React.createElement('div', { style: { height: '100%', width: pct + '%', borderRadius: 4, transition: 'width 1.2s cubic-bezier(0.16,1,0.3,1)',
            background: isWinner ? 'linear-gradient(90deg, #1d6fda, #4f9eff)' : ('linear-gradient(90deg, ' + d.color + 'cc, ' + d.color + ')'),
            boxShadow: isWinner ? '0 0 12px rgba(59,130,246,0.4)' : 'none' } }),
        ),
      );
    }),
    // Summary
    React.createElement('div', { style: { marginTop: 8, fontSize: 10, color: 'rgba(255,255,255,0.4)', lineHeight: 1.5 } },
      (() => { const m = data.find(d => d.name === 'MAPPO'), r = data.find(d => d.name === 'Rule-Based');
        return m && r && r.mean > 0
          ? 'MAPPO outperforms rule-based by +' + ((m.mean - r.mean) / r.mean * 100).toFixed(1) + '%'
          : 'Policy evaluation results'; })(),
      React.createElement('br'),
      'Mean over ' + episodes + ' evaluation episodes, 5 random seeds'
    ),
  );
}

/* ── ArchitectureDiagramPanel ── */
function ArchitectureDiagramPanel() {
  const [open, setOpen] = React.useState(false);
  const headerStyle = {
    background: 'var(--glass-bg)', backdropFilter: 'var(--glass-blur)',
    border: '1px solid var(--glass-border)', borderRadius: 10,
    padding: '10px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
    fontFamily: 'var(--font-mono)', fontSize: 11, color: 'rgba(255,255,255,0.5)',
    transition: 'background 0.2s', userSelect: 'none',
  };
  const nodes = [
    { x: 160, y: 50, w: 170, h: 36, label: '6 Country Agents', color: '#3b82f6' },
    { x: 160, y: 110, w: 170, h: 36, label: 'MAPPO PyTorch', color: '#8b5cf6' },
    { x: 430, y: 80, w: 140, h: 36, label: 'World State', color: '#22c55e' },
    { x: 660, y: 80, w: 140, h: 36, label: 'Event Engine', color: '#f59e0b' },
    { x: 430, y: 180, w: 170, h: 36, label: 'DisasterEnvWrapper', color: '#ef4444' },
    { x: 430, y: 240, w: 140, h: 36, label: 'disasterman', color: '#ef4444' },
    { x: 430, y: 300, w: 190, h: 36, label: 'ZoneScorerNet + Llama', color: '#60a5fa' },
    { x: 700, y: 300, w: 100, h: 36, label: 'Groq API', color: '#14b8a6' },
    { x: 160, y: 380, w: 120, h: 36, label: 'FastAPI', color: '#a78bfa' },
    { x: 370, y: 380, w: 140, h: 36, label: 'SSE /stream', color: '#a78bfa' },
    { x: 590, y: 380, w: 200, h: 36, label: 'React Globe Frontend', color: '#3b82f6' },
  ];
  const arrows = [
    [245, 128, 430, 98], [570, 98, 660, 98], [500, 116, 500, 180],
    [500, 216, 500, 240], [500, 276, 500, 300], [620, 318, 700, 318],
    [160, 148, 160, 380], [280, 398, 370, 398], [510, 398, 590, 398],
  ];

  return React.createElement('div', { style: { margin: '0 16px 8px', flexShrink: 0 } },
    React.createElement('div', { style: headerStyle, onClick: () => setOpen(!open),
      onMouseEnter: e => e.currentTarget.style.background = 'var(--glass-bg-hover)',
      onMouseLeave: e => e.currentTarget.style.background = 'var(--glass-bg)' },
      React.createElement('span', { style: { transition: 'transform 0.2s', transform: open ? 'rotate(90deg)' : 'rotate(0)' } }, '▶'),
      'System Architecture'
    ),
    open && React.createElement('div', { className: 'glass-panel glass-appear',
      style: { marginTop: 8, padding: 20, borderRadius: 12, overflow: 'auto' } },
      React.createElement('svg', { viewBox: '0 0 860 430', style: { width: '100%', height: 'auto' } },
        // Arrows
        ...arrows.map(([x1, y1, x2, y2], i) =>
          React.createElement('line', { key: 'a' + i, x1, y1, x2, y2, stroke: 'rgba(255,255,255,0.15)', strokeWidth: 1.5,
            markerEnd: 'url(#arrowhead)' })
        ),
        // Arrow marker
        React.createElement('defs', null,
          React.createElement('marker', { id: 'arrowhead', markerWidth: 8, markerHeight: 6, refX: 8, refY: 3, orient: 'auto' },
            React.createElement('polygon', { points: '0 0, 8 3, 0 6', fill: 'rgba(255,255,255,0.3)' })
          )
        ),
        // Nodes
        ...nodes.map((n, i) => React.createElement('g', { key: i },
          React.createElement('rect', { x: n.x, y: n.y, width: n.w, height: n.h, rx: 8,
            fill: n.color + '15', stroke: n.color + '40', strokeWidth: 1 }),
          React.createElement('text', { x: n.x + n.w / 2, y: n.y + n.h / 2 + 4, textAnchor: 'middle',
            fill: 'rgba(255,255,255,0.7)', fontSize: 11, fontFamily: 'var(--font-mono)' }, n.label),
        )),
        // Disaster threshold label
        React.createElement('text', { x: 520, y: 158, fill: 'rgba(255,255,255,0.25)', fontSize: 9,
          fontFamily: 'var(--font-mono)' }, 'disaster_severity > 0.7'),
      ),
    ),
  );
}

/* ── WorldOutcomeSummaryCard — V6.1 post-vote summary ── */
function WorldOutcomeSummaryCard({ voteTally, pnlRows, utterances, crisisLabel, onDismiss }) {
  if (!voteTally) return null;

  const passed = (voteTally.support || 0) > (voteTally.oppose || 0);
  const verdictColor = passed ? '#22c55e' : '#ef4444';
  const verdictLabel = passed ? 'RESOLUTION PASSED' : 'RESOLUTION FAILED';

  // Top P&L movers: |Δgdp| highest 3
  const movers = (pnlRows || [])
    .map(r => ({ id: r.countryId, tint: r.tint, gdp: r.metrics?.gdp || 0, welfare: r.metrics?.welfare || 0 }))
    .filter(r => r.id !== 'UN')
    .sort((a, b) => Math.abs(b.gdp) - Math.abs(a.gdp))
    .slice(0, 3);

  const unCite = (utterances || [])
    .filter(u => u.speakerId === 'UN' && u.authorityCitation)
    .map(u => u.authorityCitation)
    .pop() || null;

  const cardStyle = {
    position: 'fixed', left: '50%', top: '50%',
    transform: 'translate(-50%, -50%)', zIndex: 50,
    width: 520, maxWidth: '92vw',
    background: 'linear-gradient(180deg, rgba(22,28,48,0.97), rgba(10,14,26,0.98))',
    backdropFilter: 'blur(40px)',
    border: '1px solid ' + verdictColor + '66',
    borderRadius: 18,
    boxShadow: '0 24px 80px rgba(0,0,0,0.7), inset 0 1px 0 rgba(255,255,255,0.08), 0 0 40px ' + verdictColor + '22',
    padding: 20, fontFamily: 'var(--font-mono)',
  };

  return React.createElement('div', { className: 'glass-appear', style: cardStyle },
    // Header
    React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 } },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
        React.createElement('div', { className: 'led led-' + (passed ? 'green' : 'red') + ' led-pulse' }),
        React.createElement('span', { style: { fontSize: 12, fontWeight: 700, letterSpacing: '2px', color: verdictColor } }, verdictLabel),
      ),
      onDismiss && React.createElement('button', { onClick: onDismiss, style: {
        background: 'transparent', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 6,
        color: 'rgba(255,255,255,0.5)', cursor: 'pointer', fontSize: 10, padding: '4px 10px',
      } }, 'DISMISS'),
    ),
    // Crisis
    React.createElement('div', { style: { fontSize: 11, color: 'rgba(255,255,255,0.55)', marginBottom: 12 } },
      'Crisis: ', React.createElement('span', { style: { color: 'rgba(255,255,255,0.85)', fontWeight: 600 } }, crisisLabel || 'South Asia Cyclone'),
    ),
    // Vote split
    React.createElement('div', { style: { fontSize: 9, color: 'rgba(255,255,255,0.35)', letterSpacing: '1.5px', marginBottom: 6 } }, 'VOTE SPLIT'),
    React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 } },
      [['SUPPORT', voteTally.support || 0, '#22c55e'],
       ['OPPOSE', voteTally.oppose || 0, '#ef4444'],
       ['MODIFY', voteTally.modify || 0, '#f59e0b']].map(([l, v, c]) =>
        React.createElement('div', { key: l, style: {
          padding: '8px 10px', background: c + '14', borderRadius: 8, border: '1px solid ' + c + '33',
        } },
          React.createElement('div', { style: { fontSize: 18, fontWeight: 700, color: c } }, v),
          React.createElement('div', { style: { fontSize: 8, color: 'rgba(255,255,255,0.4)', letterSpacing: '1px', marginTop: 2 } }, l),
        )
      ),
    ),
    // Top P&L movers
    movers.length > 0 && React.createElement('div', { style: { marginBottom: 14 } },
      React.createElement('div', { style: { fontSize: 9, color: 'rgba(255,255,255,0.35)', letterSpacing: '1.5px', marginBottom: 6 } }, 'TOP P&L MOVERS'),
      React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 4 } },
        movers.map(m =>
          React.createElement('div', { key: m.id, style: {
            display: 'grid', gridTemplateColumns: '60px 1fr 80px', gap: 8,
            padding: '6px 10px', background: 'rgba(255,255,255,0.03)', borderRadius: 6,
            borderLeft: '2px solid ' + m.tint,
          } },
            React.createElement('span', { style: { fontSize: 10, fontWeight: 700, color: m.tint } }, m.id),
            React.createElement('span', { style: { fontSize: 10, color: 'rgba(255,255,255,0.5)' } }, 'GDP Δ · welfare Δ'),
            React.createElement('span', { style: {
              fontSize: 10, textAlign: 'right',
              color: m.gdp >= 0 ? '#22c55e' : '#ef4444', fontWeight: 600,
            } }, (m.gdp >= 0 ? '+' : '') + m.gdp.toFixed(3)),
          )
        ),
      ),
    ),
    // UN cite
    unCite && React.createElement('div', { style: {
      padding: '10px 12px', background: 'rgba(234,179,8,0.08)', border: '1px solid rgba(234,179,8,0.3)',
      borderRadius: 8, marginBottom: 12,
    } },
      React.createElement('div', { style: { fontSize: 9, color: 'rgba(234,179,8,0.8)', letterSpacing: '1.5px', marginBottom: 4 } }, 'UN AUTHORITY INVOKED'),
      React.createElement('div', { style: { fontSize: 11, color: 'rgba(255,255,255,0.82)' } }, unCite),
    ),
    // Teaser
    React.createElement('div', { style: { fontSize: 10, color: 'rgba(255,255,255,0.35)', textAlign: 'center', marginTop: 8,
      paddingTop: 10, borderTop: '1px solid rgba(255,255,255,0.06)' } },
      'Next round in 8 steps — relationship matrix updated'),
  );
}

Object.assign(window, { ClaimBoundaryBanner, CrisisBriefCard, TrainingFactsCard, EmergentBadgePanel, EvalSummaryCard, ArchitectureDiagramPanel, WorldOutcomeSummaryCard });
