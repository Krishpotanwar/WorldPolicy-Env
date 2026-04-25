/* CountryPnLLedger + CompanyPnLStrip */

const PNL_METRICS = ['gdp','jobs','energy','influence','welfare','heritage','military'];
const PNL_HEADERS = ['GDP Δ','Jobs','Energy','Influence','Welfare','Heritage','Military'];

function PnLCell({ value, delta, tint }) {
  const isPos = value > 0, isNeg = value < 0;
  const flashing = delta && delta !== 0;
  const [flash, setFlash] = React.useState(false);

  React.useEffect(() => {
    if (flashing) { setFlash(true); const t = setTimeout(() => setFlash(false), 600); return () => clearTimeout(t); }
  }, [delta]);

  return React.createElement('td', {
    style: {
      fontFamily: 'var(--font-mono)', fontSize: 10, textAlign: 'right', padding: '4px 8px',
      color: isPos ? '#22c55e' : isNeg ? '#ef4444' : 'rgba(255,255,255,0.35)',
      background: flash ? (tint + '66') : isPos ? 'rgba(34,197,94,0.03)' : isNeg ? 'rgba(239,68,68,0.03)' : 'transparent',
      transition: 'background 0.6s ease',
    }
  }, value === null ? '—' : (value > 0 ? '+' : '') + value.toFixed(3));
}

function CountryPnLLedger({ rows, activeSpeakerId }) {
  const style = {
    background: 'var(--glass-bg)', backdropFilter: 'var(--glass-blur)',
    border: '1px solid var(--glass-border)', borderRadius: 12,
    boxShadow: 'var(--shadow-glass)', overflow: 'hidden', position: 'relative', flexShrink: 0,
  };

  return React.createElement('div', { style },
    React.createElement('div', { style: { position: 'absolute', top: 0, left: 12, right: 12, height: 1,
      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2) 50%, transparent)', pointerEvents: 'none' } }),
    React.createElement('div', { style: { padding: '8px 12px 4px', fontFamily: 'var(--font-mono)', fontSize: 9,
      fontWeight: 700, letterSpacing: '2px', color: 'rgba(255,255,255,0.3)' } },
      'COUNTRY P&L · REAL-TIME DELTA PER DEBATE ROUND'),
    React.createElement('div', { style: { overflowX: 'auto' } },
      React.createElement('table', {
        style: { width: '100%', borderCollapse: 'collapse', minWidth: 600 }
      },
        React.createElement('thead', null,
          React.createElement('tr', null,
            React.createElement('th', { style: { fontFamily: 'var(--font-mono)', fontSize: 9, textAlign: 'left',
              padding: '4px 12px', color: 'rgba(255,255,255,0.3)', letterSpacing: '1px',
              borderBottom: '1px solid rgba(255,255,255,0.08)' } }, 'COUNTRY'),
            ...PNL_HEADERS.map((h, i) =>
              React.createElement('th', { key: i, style: { fontFamily: 'var(--font-mono)', fontSize: 9,
                textAlign: 'right', padding: '4px 8px', color: 'rgba(255,255,255,0.3)',
                letterSpacing: '1px', borderBottom: '1px solid rgba(255,255,255,0.08)' } }, h)
            ),
          ),
        ),
        React.createElement('tbody', null,
          (rows || []).map(row => {
            const isActive = activeSpeakerId === row.countryId;
            const isUNESCO = row.countryId === 'UNESCO';
            return React.createElement('tr', {
              key: row.countryId,
              style: {
                borderLeft: isActive ? '3px solid ' + row.tint : '3px solid transparent',
                background: isActive ? row.tint + '0d' : 'transparent',
                transition: 'background 0.3s',
              }
            },
              React.createElement('td', {
                style: { fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700,
                  padding: '4px 12px', color: row.tint, letterSpacing: '0.5px' }
              }, row.countryId),
              ...PNL_METRICS.map((m, i) => {
                const val = isUNESCO && m !== 'heritage' ? null : (row.metrics?.[m] || 0);
                const delta = row.deltasSinceLastTick?.[m] || 0;
                return React.createElement(PnLCell, { key: i, value: val, delta, tint: row.tint });
              }),
            );
          }),
        ),
      ),
    ),
  );
}

/* ── CompanyPnLStrip ── */
const COMPANIES = [
  { symbol: 'AAPL', name: 'Apple', countryId: 'USA', currency: '$', price: 189.32, pct: 0.8 },
  { symbol: 'BYDDY', name: 'BYD', countryId: 'CHN', currency: '¥', price: 214.10, pct: -1.2 },
  { symbol: 'GAZP', name: 'Gazprom', countryId: 'RUS', currency: '₽', price: 142.00, pct: -2.1 },
  { symbol: 'RELI', name: 'Reliance', countryId: 'IND', currency: '₹', price: 2847.50, pct: 0.4 },
  { symbol: 'KOMID', name: 'KOMID Corp', countryId: 'DPRK', currency: '₩', price: 88.00, pct: -0.5 },
  { symbol: '2222', name: 'Aramco', countryId: 'SAU', currency: '﷼', price: 32.40, pct: 1.3 },
];

function CompanyPnLStrip({ ticks, activeSpeakerId, countryTints, marketLive }) {
  const items = ticks || COMPANIES;
  const tints = countryTints || {};
  AGENTS.forEach(a => { if (!tints[a.id]) tints[a.id] = a.tint; });

  const paused = items.some(t => t.countryId === activeSpeakerId);

  // P3 — derive live state from the data itself (any tick with live:true) AND
  // honour an explicit prop override from the parent (set when /market-data
  // returns yf_loaded:true with at least one live ticker).
  const anyTickLive = items.some(t => t && t.live);
  const isLive = Boolean(marketLive) || anyTickLive;

  const stripStyle = {
    height: 40, overflow: 'hidden', flexShrink: 0,
    background: 'rgba(255,255,255,0.02)', borderTop: '1px solid rgba(255,255,255,0.06)',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
    display: 'flex', alignItems: 'center', position: 'relative',
  };

  const trackStyle = {
    display: 'flex', alignItems: 'center', gap: 0,
    animation: 'ticker-scroll 35s linear infinite',
    animationPlayState: paused ? 'paused' : 'running',
    whiteSpace: 'nowrap',
  };

  const renderTick = (t, i) => {
    const tint = tints[t.countryId] || '#fff';
    const isUp = (t.pct || t.percentChange || 0) >= 0;
    const isHighlighted = activeSpeakerId === t.countryId;
    return React.createElement('div', {
      key: i,
      style: {
        display: 'flex', alignItems: 'center', gap: 6, padding: '0 16px',
        background: isHighlighted ? tint + '1a' : 'transparent',
        transition: 'background 0.3s',
      }
    },
      React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 700, color: tint } }, t.symbol),
      React.createElement('span', { style: { fontSize: 12, color: isUp ? '#22c55e' : '#ef4444' } }, isUp ? '▲' : '▼'),
      React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'rgba(255,255,255,0.8)' } },
        t.currency + t.price.toFixed(2)),
      React.createElement('span', { style: { fontFamily: 'var(--font-mono)', fontSize: 10,
        color: isUp ? '#22c55e' : '#ef4444' } },
        (isUp ? '+' : '') + (t.pct || t.percentChange || 0).toFixed(1) + '%'),
      React.createElement('span', { style: { color: 'rgba(255,255,255,0.12)', margin: '0 4px', fontSize: 14 } }, '│'),
    );
  };

  // Duplicate for seamless loop
  const allItems = [...items, ...items];

  return React.createElement('div', { style: stripStyle },
    // P3 — LIVE / SCRIPTED data-provenance badge, pinned top-left over the ticker.
    React.createElement('div', {
      style: {
        position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)',
        display: 'flex', alignItems: 'center', gap: 5, padding: '2px 8px',
        borderRadius: 4, zIndex: 2,
        background: isLive ? 'rgba(34,197,94,0.12)' : 'rgba(245,158,11,0.10)',
        border: '1px solid ' + (isLive ? 'rgba(34,197,94,0.35)' : 'rgba(245,158,11,0.30)'),
      },
      title: isLive
        ? 'Live yfinance data — fetched every 60s from /market-data'
        : 'Static seed — yfinance unreachable or returned no live tickers',
    },
      React.createElement('div', {
        className: 'led ' + (isLive ? 'led-green led-pulse' : 'led-amber'),
        style: { width: 6, height: 6 },
      }),
      React.createElement('span', {
        style: {
          fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
          letterSpacing: '1.5px',
          color: isLive ? '#86efac' : '#fcd34d',
        },
      }, isLive ? 'MARKETS LIVE' : 'MARKETS STATIC'),
    ),
    // The ticker track itself (with extra left padding so the badge doesn't overlap)
    React.createElement('div', { style: { ...trackStyle, paddingLeft: 130 } },
      allItems.map((t, i) => renderTick(t, i)),
    ),
  );
}

/* ── SSE hooks for server-driven P&L ── */

function useCountryPnLStream() {
  const [rows, setRows] = React.useState(
    AGENTS.map(a => ({
      countryId: a.id, countryName: a.name, tint: a.tint,
      metrics: { gdp: 0, jobs: 0, energy: 0, influence: 0, welfare: 0, heritage: 0, military: 0 },
      deltasSinceLastTick: {},
    }))
  );
  const [status, setStatus] = React.useState('idle');
  const esRef = React.useRef(null);

  const start = React.useCallback(() => {
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    setStatus('connecting');
    const apiBase = (typeof window !== 'undefined' && window.WP_API_BASE) || '';
    const es = new EventSource(apiBase + '/stream/country-pnl');
    esRef.current = es;

    es.addEventListener('pnl_tick', (e) => {
      const tick = JSON.parse(e.data);
      setRows(prev => prev.map(row => {
        if (row.countryId !== tick.countryId) return { ...row, deltasSinceLastTick: {} };
        const deltas = tick.deltas || {};
        const newMetrics = { ...row.metrics };
        Object.entries(deltas).forEach(([k, v]) => {
          if (k in newMetrics) newMetrics[k] = (newMetrics[k] || 0) + v;
        });
        return { ...row, metrics: newMetrics, deltasSinceLastTick: deltas };
      }));
    });

    es.addEventListener('pnl_end', () => {
      setStatus('complete');
      if (esRef.current) { esRef.current.close(); esRef.current = null; }
    });

    es.onopen = () => setStatus('streaming');
    es.onerror = () => {
      setStatus('error');
      if (esRef.current) { esRef.current.close(); esRef.current = null; }
    };
  }, []);

  const reset = React.useCallback(() => {
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    setStatus('idle');
    setRows(AGENTS.map(a => ({
      countryId: a.id, countryName: a.name, tint: a.tint,
      metrics: { gdp: 0, jobs: 0, energy: 0, influence: 0, welfare: 0, heritage: 0, military: 0 },
      deltasSinceLastTick: {},
    })));
  }, []);

  React.useEffect(() => () => { if (esRef.current) esRef.current.close(); }, []);

  return { rows, status, start, reset };
}

function useCompanyPnLStream() {
  const [ticks, setTicks] = React.useState(COMPANIES.map(c => ({ ...c })));
  const [status, setStatus] = React.useState('idle');
  const esRef = React.useRef(null);

  const start = React.useCallback(() => {
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    setStatus('connecting');
    const apiBase = (typeof window !== 'undefined' && window.WP_API_BASE) || '';
    const es = new EventSource(apiBase + '/stream/company-pnl');
    esRef.current = es;

    es.addEventListener('pnl_tick', (e) => {
      const tick = JSON.parse(e.data);
      if (!tick.symbol) return;
      setTicks(prev => prev.map(t => {
        if (t.symbol !== tick.symbol) return t;
        return { ...t, price: tick.price ?? t.price, pct: tick.pct ?? t.pct, live: !!tick.live };
      }));
    });

    es.addEventListener('pnl_end', () => {
      setStatus('complete');
      if (esRef.current) { esRef.current.close(); esRef.current = null; }
    });

    es.onopen = () => setStatus('streaming');
    es.onerror = () => {
      setStatus('error');
      if (esRef.current) { esRef.current.close(); esRef.current = null; }
    };
  }, []);

  const reset = React.useCallback(() => {
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    setStatus('idle');
    setTicks(COMPANIES.map(c => ({ ...c })));
  }, []);

  React.useEffect(() => () => { if (esRef.current) esRef.current.close(); }, []);

  return { ticks, status, start, reset };
}

Object.assign(window, { CountryPnLLedger, CompanyPnLStrip, COMPANIES, PNL_METRICS, useCountryPnLStream, useCompanyPnLStream });
