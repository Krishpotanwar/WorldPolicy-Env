/* AgentPortraitStrip — 7 circular portraits with hover/click/active states */

const AGENTS = [
  { id: 'USA', name: 'United States', code: 'US', tint: '#3b82f6' },
  { id: 'CHN', name: 'China', code: 'CN', tint: '#ef4444' },
  { id: 'RUS', name: 'Russia', code: 'RU', tint: '#8b5cf6' },
  { id: 'IND', name: 'India', code: 'IN', tint: '#f59e0b' },
  { id: 'DPRK', name: 'North Korea', code: 'KP', tint: '#ef4444' },
  { id: 'SAU', name: 'Saudi Arabia', code: 'SA', tint: '#22c55e' },
  { id: 'UNESCO', name: 'UNESCO', code: '🕊', tint: '#14b8a6' },
];

function UNESCOLaurel({ size }) {
  return React.createElement('svg', { width: size, height: size, viewBox: '0 0 48 48', style: { display: 'block' } },
    // Laurel branches
    React.createElement('g', { fill: 'none', stroke: '#14b8a6', strokeWidth: 1.2, opacity: 0.8 },
      // Left branch
      React.createElement('path', { d: 'M24 40 C18 36, 12 30, 10 22' }),
      React.createElement('path', { d: 'M14 34 C12 32, 10 28, 10 24' }),
      React.createElement('path', { d: 'M16 36 C14 33, 11 30, 11 26' }),
      React.createElement('path', { d: 'M18 38 C15 35, 13 32, 12 28' }),
      // Leaves left
      React.createElement('ellipse', { cx: 11, cy: 24, rx: 3, ry: 1.5, transform: 'rotate(-30 11 24)', fill: '#14b8a6', fillOpacity: 0.2 }),
      React.createElement('ellipse', { cx: 12, cy: 28, rx: 3, ry: 1.5, transform: 'rotate(-20 12 28)', fill: '#14b8a6', fillOpacity: 0.2 }),
      React.createElement('ellipse', { cx: 14, cy: 31, rx: 3, ry: 1.5, transform: 'rotate(-10 14 31)', fill: '#14b8a6', fillOpacity: 0.2 }),
      // Right branch
      React.createElement('path', { d: 'M24 40 C30 36, 36 30, 38 22' }),
      React.createElement('path', { d: 'M34 34 C36 32, 38 28, 38 24' }),
      React.createElement('path', { d: 'M32 36 C34 33, 37 30, 37 26' }),
      React.createElement('path', { d: 'M30 38 C33 35, 35 32, 36 28' }),
      // Leaves right
      React.createElement('ellipse', { cx: 37, cy: 24, rx: 3, ry: 1.5, transform: 'rotate(30 37 24)', fill: '#14b8a6', fillOpacity: 0.2 }),
      React.createElement('ellipse', { cx: 36, cy: 28, rx: 3, ry: 1.5, transform: 'rotate(20 36 28)', fill: '#14b8a6', fillOpacity: 0.2 }),
      React.createElement('ellipse', { cx: 34, cy: 31, rx: 3, ry: 1.5, transform: 'rotate(10 34 31)', fill: '#14b8a6', fillOpacity: 0.2 }),
    ),
    // Globe in center
    React.createElement('circle', { cx: 24, cy: 20, r: 8, fill: 'none', stroke: '#14b8a6', strokeWidth: 1, opacity: 0.6 }),
    React.createElement('ellipse', { cx: 24, cy: 20, rx: 3, ry: 8, fill: 'none', stroke: '#14b8a6', strokeWidth: 0.6, opacity: 0.4 }),
    React.createElement('line', { x1: 16, y1: 20, x2: 32, y2: 20, stroke: '#14b8a6', strokeWidth: 0.6, opacity: 0.4 }),
  );
}

function AgentPortrait({ agent, isActive, isInvolved, isPeripheral, isFocused, onHover, onClick, tooltip, sentiment }) {
  const [hovered, setHovered] = React.useState(false);
  const [justPromoted, setJustPromoted] = React.useState(false);
  const prevInvolvedRef = React.useRef(isInvolved);
  const prevPeripheralRef = React.useRef(isPeripheral);

  React.useEffect(() => {
    const wasUninvolved = !prevInvolvedRef.current && !prevPeripheralRef.current;
    const nowActive = isInvolved || isPeripheral;
    if (wasUninvolved && nowActive) {
      setJustPromoted(true);
      const t = setTimeout(() => setJustPromoted(false), 1500);
      return () => clearTimeout(t);
    }
    prevInvolvedRef.current = isInvolved;
    prevPeripheralRef.current = isPeripheral;
  }, [isInvolved, isPeripheral]);

  const isUNESCO = agent.id === 'UNESCO';
  const dim = !isInvolved && !isPeripheral && !isActive && !isFocused;

  const containerStyle = {
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
    cursor: 'pointer', userSelect: 'none', position: 'relative',
    opacity: dim ? 0.45 : 1,
    filter: dim ? 'saturate(0.3)' : 'none',
    transition: 'all 0.25s cubic-bezier(0.16,1,0.3,1)',
    transform: isFocused ? 'scale(1.15)' : hovered ? 'scale(1.08)' : 'scale(1)',
  };

  const discStyle = {
    width: 72, height: 72, borderRadius: '50%', position: 'relative',
    background: isUNESCO
      ? 'linear-gradient(135deg, rgba(20,184,166,0.08) 0%, rgba(255,255,255,0.04) 100%)'
      : 'linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
    backdropFilter: 'blur(16px)',
    border: '2px solid ' + agent.tint + (isFocused ? 'ff' : hovered ? '80' : '33'),
    boxShadow: [
      '0 4px 16px rgba(0,0,0,0.4)',
      'inset 0 1px 0 rgba(255,255,255,0.08)',
      isActive ? '0 0 20px ' + agent.tint + '60, 0 0 40px ' + agent.tint + '20' : '',
      isFocused ? '0 0 24px ' + agent.tint + '50' : '',
    ].filter(Boolean).join(', '),
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    transition: 'all 0.25s cubic-bezier(0.16,1,0.3,1)',
  };

  // Active speaker pulse ring
  const pulseRing = isActive && React.createElement('div', {
    style: {
      position: 'absolute', inset: -6, borderRadius: '50%',
      border: '2px solid ' + agent.tint,
      animation: 'portrait-pulse 1.5s ease-in-out infinite',
      pointerEvents: 'none',
    }
  });

  // Crisis involvement ring
  const crisisRing = isInvolved && React.createElement('div', {
    style: {
      position: 'absolute', inset: -10, borderRadius: '50%',
      border: '1.5px solid rgba(245,158,11,0.3)',
      pointerEvents: 'none',
    }
  });

  // Promotion flash ring
  const promotionFlash = justPromoted && React.createElement('div', {
    style: {
      position: 'absolute', inset: -14, borderRadius: '50%',
      border: '2px solid ' + agent.tint,
      animation: 'portrait-pulse 0.75s ease-out forwards',
      pointerEvents: 'none',
      boxShadow: '0 0 16px ' + agent.tint + '60',
    }
  });

  // Active LED
  const liveLed = isActive && React.createElement('div', {
    style: {
      position: 'absolute', top: 2, right: 2, width: 14, height: 14,
      borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(0,0,0,0.6)', border: '1px solid rgba(255,255,255,0.1)',
      zIndex: 2,
    }
  },
    React.createElement('div', { className: 'led led-green led-pulse', style: { width: 6, height: 6 } })
  );

  // Focus tick
  const focusTick = isFocused && React.createElement('div', {
    style: {
      position: 'absolute', bottom: -8, left: '50%', transform: 'translateX(-50%)',
      width: 0, height: 0, borderLeft: '5px solid transparent', borderRight: '5px solid transparent',
      borderTop: '6px solid ' + agent.tint,
    }
  });

  // P4 — Public sentiment chip (tone-colored dot bottom-right of the disc).
  // Hidden when no sentiment data has loaded yet. Subtle pulse if live.
  const sentimentChip = sentiment && sentiment.color && React.createElement('div', {
    style: {
      position: 'absolute', bottom: 2, right: 2, width: 14, height: 14,
      borderRadius: '50%',
      background: 'rgba(0,0,0,0.7)',
      border: '1px solid rgba(255,255,255,0.12)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 2,
    },
    title: 'Public sentiment (last 24h, GDELT tone): ' + sentiment.label
      + ' (' + (sentiment.tone >= 0 ? '+' : '') + Number(sentiment.tone).toFixed(2) + ')'
      + (sentiment.live ? ' — live' : ' — fallback')
      + ', n=' + (sentiment.sample_size || 0) + ' articles',
  },
    React.createElement('div', {
      style: {
        width: 7, height: 7, borderRadius: '50%',
        background: sentiment.color,
        boxShadow: sentiment.live ? ('0 0 6px ' + sentiment.color) : 'none',
        opacity: sentiment.live ? 1 : 0.7,
      }
    })
  );

  // Tooltip
  const tooltipEl = hovered && tooltip && React.createElement('div', {
    style: {
      position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)',
      marginTop: 12, padding: '8px 12px', borderRadius: 8, whiteSpace: 'nowrap',
      background: 'rgba(10,14,26,0.95)', backdropFilter: 'blur(16px)',
      border: '1px solid rgba(255,255,255,0.1)', boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
      fontFamily: 'var(--font-mono)', fontSize: 10, color: 'rgba(255,255,255,0.7)',
      zIndex: 50, pointerEvents: 'none',
    }
  },
    React.createElement('div', { style: { color: agent.tint, fontWeight: 700, marginBottom: 2 } }, agent.name),
    tooltip.stance && React.createElement('div', { style: { color: 'rgba(255,255,255,0.5)' } }, tooltip.stance),
    tooltip.lastStep != null && React.createElement('div', { style: { color: 'rgba(255,255,255,0.3)', marginTop: 2 } }, 'Last spoke: step ' + tooltip.lastStep),
  );

  return React.createElement('div', {
    style: containerStyle,
    onMouseEnter: () => { setHovered(true); onHover && onHover(agent.id); },
    onMouseLeave: () => { setHovered(false); onHover && onHover(null); },
    onClick: () => onClick && onClick(agent.id),
  },
    React.createElement('div', { style: discStyle },
      pulseRing, crisisRing, promotionFlash, liveLed, sentimentChip,
      isUNESCO
        ? React.createElement(UNESCOLaurel, { size: 44 })
        : React.createElement('span', {
            style: { fontFamily: 'var(--font-mono)', fontSize: 22, fontWeight: 700,
              color: agent.tint, letterSpacing: 2, opacity: 0.9 }
          }, agent.code),
      focusTick,
    ),
    React.createElement('span', {
      style: { fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 600,
        letterSpacing: '0.8px', color: 'rgba(255,255,255,0.6)', textAlign: 'center' }
    }, agent.id === 'DPRK' ? 'N. KOREA' : agent.id),
    isUNESCO && React.createElement('span', {
      style: { fontFamily: 'var(--font-mono)', fontSize: 7, letterSpacing: '1px',
        color: '#14b8a6', opacity: 0.6, marginTop: -2 }
    }, 'MEDIATOR · NON-VOTING'),
    tooltipEl,
  );
}

function AgentPortraitStrip({ activeSpeakerId, focusedId, involvement, tooltips, onHover, onClick, sentimentByAgent }) {
  const inv = involvement || {};
  const sents = sentimentByAgent || {};
  return React.createElement('div', {
    style: {
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      gap: 0, padding: '12px 20px', flexShrink: 0,
      background: 'rgba(255,255,255,0.02)', borderBottom: '1px solid rgba(255,255,255,0.06)',
    }
  },
    AGENTS.map((agent, i) => React.createElement(React.Fragment, { key: agent.id },
      i === 6 && React.createElement('div', { style: { width: 20 } }), // gap before UNESCO
      React.createElement(AgentPortrait, {
        agent,
        isActive: activeSpeakerId === agent.id,
        isInvolved: inv.involved?.includes(agent.id),
        isPeripheral: inv.peripheral?.includes(agent.id) || agent.id === 'UNESCO',
        isFocused: focusedId === agent.id,
        tooltip: tooltips?.[agent.id] || null,
        sentiment: sents[agent.id] || null,
        onHover, onClick,
      }),
      i < 5 && React.createElement('div', { style: { width: 12 } }),
    )),
  );
}

Object.assign(window, { AGENTS, AgentPortraitStrip, AgentPortrait, UNESCOLaurel });
