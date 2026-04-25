/* SimPanel + Reward Curves + Main App */

/* ── Mini Sparkline ── */
function Sparkline({ data, color, width, height }) {
  if (!data || data.length < 2) return null;
  const max = Math.max(...data), min = Math.min(...data);
  const range = max - min || 1;
  const points = data.map((v, i) =>
    (i / (data.length - 1)) * width + ',' + (height - ((v - min) / range) * (height - 4) - 2)
  ).join(' ');
  return React.createElement('svg', { width, height, style: { display: 'block' } },
    React.createElement('polyline', { points, fill: 'none', stroke: color, strokeWidth: 1.5,
      style: { filter: 'drop-shadow(0 0 4px ' + color + ')' } }),
  );
}

/* ── SimPanel ── */
function SimPanel({ step, maxSteps, actions, curves }) {
  const actionTypes = ['COOPERATE', 'SANCTION', 'AID_DISPATCH', 'MILITARIZE', 'TRADE', 'NEGOTIATE'];
  const actionColors = ['#22c55e', '#ef4444', '#3b82f6', '#f59e0b', '#14b8a6', '#8b5cf6'];
  const maxAction = Math.max(...(actions || [0]), 1);

  const panelStyle = {
    background: 'var(--glass-bg)', backdropFilter: 'var(--glass-blur)',
    border: '1px solid var(--glass-border)', borderRadius: 14,
    boxShadow: 'var(--shadow-glass)', padding: 16, fontFamily: 'var(--font-mono)', position: 'relative',
  };

  return React.createElement('div', { className: 'glass-appear', style: panelStyle },
    React.createElement('div', { style: { position: 'absolute', top: 0, left: 12, right: 12, height: 1,
      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2) 50%, transparent)', pointerEvents: 'none' } }),
    // Step counter
    React.createElement('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 } },
      React.createElement('span', { style: { fontSize: 10, fontWeight: 700, letterSpacing: '2px', color: 'rgba(255,255,255,0.35)' } }, 'SIMULATION'),
      React.createElement('span', { style: { fontSize: 12, fontWeight: 700, color: '#60a5fa' } }, 'STEP ' + step + ' / ' + maxSteps),
    ),
    // Progress bar
    React.createElement('div', { style: { height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, marginBottom: 14, overflow: 'hidden' } },
      React.createElement('div', { style: { height: '100%', width: ((step / maxSteps) * 100) + '%', borderRadius: 2,
        background: 'linear-gradient(90deg, #1d6fda, #4f9eff)', transition: 'width 0.3s ease' } }),
    ),
    // Action distribution
    React.createElement('div', { style: { fontSize: 9, color: 'rgba(255,255,255,0.3)', marginBottom: 6, letterSpacing: '1px' } }, 'AGENT ACTION DISTRIBUTION'),
    React.createElement('div', { style: { display: 'flex', gap: 4, alignItems: 'flex-end', height: 48, marginBottom: 14 } },
      ...(actions || []).map((v, i) =>
        React.createElement('div', { key: i, style: { flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 } },
          React.createElement('div', { style: { width: '100%', height: Math.max(4, (v / maxAction) * 40),
            background: 'linear-gradient(180deg, ' + actionColors[i] + ', ' + actionColors[i] + '88)',
            borderRadius: '3px 3px 0 0', transition: 'height 0.4s ease',
            boxShadow: '0 0 6px ' + actionColors[i] + '40' } }),
          React.createElement('span', { style: { fontSize: 7, color: 'rgba(255,255,255,0.25)', whiteSpace: 'nowrap' } },
            actionTypes[i].slice(0, 4)),
        )
      ),
    ),
    // 3 Reward curves
    React.createElement('div', { style: { fontSize: 9, color: 'rgba(255,255,255,0.3)', marginBottom: 8, letterSpacing: '1px' } }, 'REWARD CURVES'),
    React.createElement('div', { style: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 } },
      [
        { label: 'Global Welfare', data: curves.welfare, color: '#22c55e' },
        { label: 'Aid Dispatch', data: curves.aid, color: '#3b82f6' },
        { label: 'Arms Index', data: curves.arms, color: '#ef4444' },
      ].map((c, i) =>
        React.createElement('div', { key: i, style: { background: 'rgba(255,255,255,0.03)', borderRadius: 8,
          border: '1px solid rgba(255,255,255,0.05)', padding: '8px 6px' } },
          React.createElement('div', { style: { fontSize: 9, color: 'rgba(255,255,255,0.4)', marginBottom: 4 } }, c.label),
          React.createElement(Sparkline, { data: c.data, color: c.color, width: 80, height: 32 }),
        )
      ),
    ),
  );
}

/* ── SIMULATION ENGINE (mock) ── */
function useSimulation() {
  const [state, setState] = React.useState({
    running: false, step: 0, maxSteps: 200,
    actions: [2, 1, 3, 0, 2, 1],
    arcs: [],
    disasterCountry: null,
    brief: null, briefLoading: false,
    coldWar: { detected: false, step: null, trigger: null },
    armsRace: { detected: false, step: null, trigger: null },
    freeRider: { count: 0, names: [], trigger: null },
    curves: { welfare: [0], aid: [0], arms: [1] },
    rotation: 0,
  });

  const stateRef = React.useRef(state);
  stateRef.current = state;
  const timerRef = React.useRef(null);

  const SCRIPT = [
    { at: 5, fn: s => ({ ...s, arcs: [{ from: 'RUS', to: 'USA', type: 'SANCTION' }],
      brief: { brief: 'Rising geopolitical tensions between major powers as Russia imposes economic sanctions on US-aligned trade routes.', priority_response: 'Initiate multilateral diplomatic channels immediately to prevent escalation.', risk_level: 'MEDIUM', crisis_type: 'GEOPOLITICAL TENSION', step: s.step, model: 'llama-3.3-70b' } }) },
    { at: 15, fn: s => ({ ...s, arcs: [...s.arcs, { from: 'USA', to: 'RUS', type: 'SANCTION' }, { from: 'GBR', to: 'RUS', type: 'SANCTION' }] }) },
    { at: 25, fn: s => ({ ...s, arcs: [...s.arcs, { from: 'CHN', to: 'RUS', type: 'TRADE' }] }) },
    { at: 40, fn: s => ({ ...s, disasterCountry: 'IND',
      brief: { brief: 'A severe cyclone has made landfall across coastal zones in South Asia, triggering mass displacement and infrastructure collapse.', priority_response: 'Deploy multilateral humanitarian aid immediately with priority to coastal Zone 3 and Zone 7.', risk_level: 'CRITICAL', crisis_type: 'NATURAL DISASTER', step: s.step, model: 'llama-3.3-70b' },
      arcs: s.arcs.filter(a => a.type !== 'AID') }) },
    { at: 50, fn: s => ({ ...s, arcs: [...s.arcs, { from: 'USA', to: 'IND', type: 'AID' }, { from: 'GBR', to: 'IND', type: 'AID' }] }) },
    { at: 65, fn: s => ({ ...s, arcs: [...s.arcs, { from: 'BRA', to: 'IND', type: 'AID' }] }) },
    { at: 80, fn: s => ({ ...s, coldWar: { detected: true, step: 83, trigger: 'bloc_count=2, cross_bloc_rel=-0.61' } }) },
    { at: 100, fn: s => ({ ...s, freeRider: { count: 1, names: ['China'], trigger: 'China  climate=0.68, pledge_rate=0.04' } }) },
    { at: 120, fn: s => ({ ...s, disasterCountry: null,
      brief: { brief: 'Cyclone relief operations stabilizing. Two geopolitical blocs have formed with increasing polarization across trade and military dimensions.', priority_response: 'Establish emergency inter-bloc communication protocols to prevent miscalculation.', risk_level: 'HIGH', crisis_type: 'GEOPOLITICAL BIFURCATION', step: s.step, model: 'llama-3.3-70b' } }) },
    { at: 140, fn: s => ({ ...s, armsRace: { detected: true, step: 140, trigger: 'all Δmilitary>0 for 5 consecutive steps' },
      actions: [1, 3, 1, 4, 1, 2] }) },
    { at: 170, fn: s => ({ ...s, armsRace: { ...s.armsRace, detected: false },
      actions: [3, 1, 2, 1, 3, 2],
      brief: { brief: 'Arms race spiral broken as agents learn militarization is costly. Cooperative policies re-emerging across multiple dimensions.', priority_response: 'Lock in de-escalation gains with binding multilateral agreements.', risk_level: 'MEDIUM', crisis_type: 'DE-ESCALATION', step: s.step, model: 'llama-3.3-70b' } }) },
  ];

  const tick = React.useCallback(() => {
    setState(prev => {
      if (!prev.running || prev.step >= prev.maxSteps) return { ...prev, running: false };
      let next = { ...prev, step: prev.step + 1, rotation: prev.rotation + 0.15 };

      // Apply script events
      SCRIPT.forEach(evt => { if (evt.at === next.step) next = evt.fn(next); });

      // Random action jitter
      next.actions = next.actions.map(v => Math.max(0, v + (Math.random() - 0.5) * 1.2));

      // Curves
      const w = prev.curves.welfare;
      const a = prev.curves.aid;
      const ar = prev.curves.arms;
      next.curves = {
        welfare: [...w, w[w.length - 1] + (Math.random() - 0.35) * 0.1],
        aid: [...a, a[a.length - 1] + (next.step > 40 && next.step < 130 ? 0.06 : -0.01) + (Math.random() - 0.5) * 0.04],
        arms: [...ar, ar[ar.length - 1] + (next.step > 130 ? -0.03 : 0.015) + (Math.random() - 0.5) * 0.03],
      };

      return next;
    });
  }, []);

  const start = React.useCallback(() => {
    setState(prev => ({ ...prev, running: true }));
  }, []);
  const pause = React.useCallback(() => {
    setState(prev => ({ ...prev, running: false }));
  }, []);
  const reset = React.useCallback(() => {
    setState({
      running: false, step: 0, maxSteps: 200,
      actions: [2, 1, 3, 0, 2, 1], arcs: [], disasterCountry: null,
      brief: null, briefLoading: false,
      coldWar: { detected: false, step: null, trigger: null },
      armsRace: { detected: false, step: null, trigger: null },
      freeRider: { count: 0, names: [], trigger: null },
      curves: { welfare: [0], aid: [0], arms: [1] }, rotation: 0,
    });
  }, []);

  React.useEffect(() => {
    if (state.running) {
      timerRef.current = setInterval(tick, 250);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [state.running, tick]);

  return { state, start, pause, reset };
}

Object.assign(window, { SimPanel, Sparkline, useSimulation });
