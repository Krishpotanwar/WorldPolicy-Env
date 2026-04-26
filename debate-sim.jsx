/* debate-sim.jsx — SSE-driven debate engine consuming /stream/debate */

const WP_HISTORY_KEY = 'wp_debate_history';
const WP_HISTORY_MAX = 10;

function _loadDebateHistory() {
  try {
    const raw = localStorage.getItem(WP_HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (_) { return []; }
}

function _saveDebateSession(session) {
  try {
    const history = _loadDebateHistory();
    history.unshift(session);
    if (history.length > WP_HISTORY_MAX) history.length = WP_HISTORY_MAX;
    localStorage.setItem(WP_HISTORY_KEY, JSON.stringify(history));
    return history;
  } catch (_) { return []; }
}

function useDebateStream() {
  const [state, setState] = React.useState({
    running: false, step: 0, maxSteps: 50,
    utterances: [], activeSpeakerId: null,
    pnlRows: AGENTS.map(a => ({
      countryId: a.id, countryName: a.name, tint: a.tint,
      metrics: { gdp: 0, jobs: 0, energy: 0, influence: 0, welfare: 0, heritage: 0, military: 0 },
      deltasSinceLastTick: {},
    })),
    companyTicks: COMPANIES.map(c => ({ ...c })),
    marketLive: false,
    sentimentByAgent: {},
    sentimentLive: false,
    voteTally: null,
    rhetoricAlert: null,
    involvement: { involved: [], peripheral: [], uninvolved: [] },
    currentRound: 0,
    totalRounds: 0,
    roundDividers: [],
    debateArcs: [],
    crisisCountry: null,
    crisisType: 'natural_disaster',
    connectionStatus: 'idle',
    connectionError: null,
    liveMode: 'canned',
    debateHistory: _loadDebateHistory(),
  });

  const stateRef = React.useRef(state);
  stateRef.current = state;
  const esRef = React.useRef(null);
  const retryRef = React.useRef(0);
  const marketTimerRef = React.useRef(null);
  const sentimentTimerRef = React.useRef(null);
  const _debug = typeof localStorage !== 'undefined' && localStorage.getItem('wp:debug');

  function _log() {
    if (_debug) console.debug('[debate-stream]', ...arguments);
  }

  function closeSSE() {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  }

  function deriveArcs(utterances) {
    const arcs = [];
    const seen = new Set();
    utterances.forEach(u => {
      const mentions = u.mentionedCountries || [];
      const type = (STANCE_MAP[u.stance] || STANCE_MAP.neutral).type;
      mentions.forEach(target => {
        const key = u.speakerId + '->' + target + ':' + type;
        if (!seen.has(key) && u.speakerId !== target) {
          seen.add(key);
          arcs.push({ from: u.speakerId, to: target, type: type });
        }
      });
    });
    return arcs;
  }

  function applyPnLDeltas(rows, deltas, speakerId) {
    if (!deltas || Object.keys(deltas).length === 0) return rows;
    return rows.map(row => {
      const delta = deltas[row.countryId] || 0;
      if (delta === 0) return { ...row, deltasSinceLastTick: {} };
      return {
        ...row,
        metrics: {
          ...row.metrics,
          gdp: row.metrics.gdp + delta,
          welfare: row.metrics.welfare + delta * 0.5,
          influence: row.metrics.influence + delta * 0.3,
        },
        deltasSinceLastTick: { gdp: delta, welfare: delta * 0.5, influence: delta * 0.3 },
      };
    });
  }

  function subscribeSSE(url, isLive) {
    closeSSE();
    retryRef.current = 0;

    setState(prev => ({
      ...prev,
      running: true,
      connectionStatus: 'connecting',
      connectionError: null,
      liveMode: isLive ? 'live' : 'canned',
    }));

    const es = new EventSource(url);
    esRef.current = es;

    es.addEventListener('round_start', (e) => {
      const data = JSON.parse(e.data);
      _log('round_start', data);
      setState(prev => {
        const roundNum = (data.round_number || prev.currentRound + 1);
        const dividers = roundNum > 1
          ? [...prev.roundDividers, { afterIndex: prev.utterances.length, round: roundNum }]
          : prev.roundDividers;
        return {
          ...prev,
          currentRound: roundNum,
          totalRounds: data.max_rounds || prev.totalRounds,
          crisisType: data.crisis_type || prev.crisisType,
          crisisCountry: data.crisis_country || prev.crisisCountry,
          involvement: data.involvement || prev.involvement,
          connectionStatus: 'streaming',
          roundDividers: dividers,
        };
      });
    });

    es.addEventListener('utterance', (e) => {
      const u = JSON.parse(e.data);
      _log('utterance', u.speakerId, u.stance);
      setState(prev => {
        const newUtterances = [...prev.utterances, u];
        const newPnl = applyPnLDeltas(prev.pnlRows, u.pnlDeltas, u.speakerId);
        const newArcs = deriveArcs(newUtterances);
        const newStep = prev.step + 1;

        return {
          ...prev,
          utterances: newUtterances,
          activeSpeakerId: u.speakerId,
          step: newStep,
          pnlRows: newPnl,
          debateArcs: newArcs,
        };
      });
    });

    es.addEventListener('round_end', (e) => {
      const data = JSON.parse(e.data);
      _log('round_end', data);
      setState(prev => ({
        ...prev,
        voteTally: data.vote_tally || prev.voteTally,
        activeSpeakerId: null,
      }));
    });

    es.addEventListener('debate_end', (e) => {
      const data = JSON.parse(e.data);
      _log('debate_end', data);
      closeSSE();
      setState(prev => {
        const tally = data.vote_tally || prev.voteTally;
        const session = {
          timestamp: new Date().toISOString(),
          crisisType: prev.crisisType,
          utterances: prev.utterances,
          voteTally: tally,
          rounds: prev.currentRound,
          liveMode: prev.liveMode,
        };
        const updatedHistory = _saveDebateSession(session);
        return {
          ...prev,
          running: false,
          voteTally: tally,
          activeSpeakerId: null,
          connectionStatus: 'complete',
          rhetoricAlert: data.rhetoric_alert || prev.rhetoricAlert,
          debateHistory: updatedHistory,
        };
      });
    });

    es.addEventListener('error_event', (e) => {
      const data = JSON.parse(e.data);
      _log('error', data);
      setState(prev => ({
        ...prev,
        connectionError: data.error || 'Unknown server error',
        connectionStatus: 'error',
      }));
    });

    es.onerror = () => {
      const maxRetries = 4;
      const currentRetry = retryRef.current;

      if (currentRetry >= maxRetries) {
        _log('max retries reached, giving up');
        closeSSE();
        setState(prev => ({
          ...prev,
          running: false,
          connectionStatus: 'disconnected',
          connectionError: 'Connection lost after ' + maxRetries + ' retries. Server may be down.',
        }));
        return;
      }

      const delay = Math.min(1000 * Math.pow(2, currentRetry), 10000);
      _log('connection error, retry', currentRetry + 1, 'in', delay, 'ms');
      retryRef.current = currentRetry + 1;
      setState(prev => ({
        ...prev,
        connectionStatus: 'reconnecting',
        connectionError: 'Reconnecting (attempt ' + (currentRetry + 1) + '/' + maxRetries + ')...',
      }));

      closeSSE();
      setTimeout(() => {
        if (stateRef.current.running) {
          subscribeSSE(url, isLive);
        }
      }, delay);
    };

    es.onopen = () => {
      _log('SSE connection opened');
      retryRef.current = 0;
      setState(prev => ({
        ...prev,
        connectionStatus: 'connected',
        connectionError: null,
      }));
    };
  }

  // -- Market data polling (unchanged from original) --
  const fetchMarketSnapshot = React.useCallback(async () => {
    try {
      const apiBase = (typeof window !== 'undefined' && window.WP_API_BASE) || '';
      const r = await fetch(apiBase + '/market-data', { cache: 'no-store' });
      if (!r.ok) return;
      const j = await r.json();
      if (!j || !Array.isArray(j.companies)) return;
      const liveBySym = {};
      j.companies.forEach(c => { liveBySym[c.symbol] = c; });
      setState(prev => {
        const merged = prev.companyTicks.map(t => {
          const live = liveBySym[t.symbol];
          if (!live) return t;
          return { ...t, price: live.price, pct: live.pct, live: !!live.live };
        });
        return { ...prev, companyTicks: merged, marketLive: !!j.live };
      });
    } catch (e) { /* offline: keep scripted */ }
  }, []);

  React.useEffect(() => {
    fetchMarketSnapshot();
    marketTimerRef.current = setInterval(fetchMarketSnapshot, 60000);
    return () => clearInterval(marketTimerRef.current);
  }, [fetchMarketSnapshot]);

  // -- Sentiment polling (unchanged from original) --
  const fetchSentiment = React.useCallback(async () => {
    try {
      const apiBase = (typeof window !== 'undefined' && window.WP_API_BASE) || '';
      const r = await fetch(apiBase + '/sentiment', { cache: 'no-store' });
      if (!r.ok) return;
      const j = await r.json();
      if (!j || !j.sentiments) return;
      setState(prev => ({ ...prev, sentimentByAgent: j.sentiments, sentimentLive: !!j.live }));
    } catch (e) { /* offline: keep empty */ }
  }, []);

  React.useEffect(() => {
    fetchSentiment();
    sentimentTimerRef.current = setInterval(fetchSentiment, 60000);
    return () => clearInterval(sentimentTimerRef.current);
  }, [fetchSentiment]);

  // -- Cleanup on unmount --
  React.useEffect(() => {
    return () => closeSSE();
  }, []);

  // -- Public API --

  const startLive = React.useCallback(async (opts) => {
    const apiBase = (typeof window !== 'undefined' && window.WP_API_BASE) || '';
    const crisisType = (opts && opts.crisisType) || 'natural_disaster';
    const crisisDescription = (opts && opts.crisisDescription) || '';
    const mappoAction = (opts && opts.mappoAction) || 'AID_DISPATCH_COORDINATED';
    const maxRounds = (opts && opts.maxRounds) || 3;

    setState(prev => ({ ...prev, connectionStatus: 'calling', connectionError: null }));

    try {
      const r = await fetch(apiBase + '/live-debate?crisis_type=' + encodeURIComponent(crisisType) +
        '&crisis_description=' + encodeURIComponent(crisisDescription) +
        '&mappo_action=' + encodeURIComponent(mappoAction) +
        '&max_rounds=' + maxRounds, { method: 'POST' });
      const j = await r.json();
      const isLive = !!j.live;
      const forceCanned = !isLive;
      const url = apiBase + '/stream/debate?crisis_type=' + encodeURIComponent(crisisType) +
        '&crisis_description=' + encodeURIComponent(crisisDescription) +
        '&mappo_action=' + encodeURIComponent(mappoAction) +
        '&force_canned=' + forceCanned + '&max_rounds=' + maxRounds;
      subscribeSSE(url, isLive);
      return { live: isLive, roundId: j.round_id };
    } catch (e) {
      _log('POST /live-debate failed, falling back to canned SSE', e);
      const url = apiBase + '/stream/debate?crisis_type=' + encodeURIComponent(crisisType) +
        '&crisis_description=' + encodeURIComponent(crisisDescription) +
        '&mappo_action=' + encodeURIComponent(mappoAction) +
        '&force_canned=true&max_rounds=' + maxRounds;
      subscribeSSE(url, false);
      return { live: false, roundId: null };
    }
  }, []);

  const startCanned = React.useCallback((opts) => {
    const apiBase = (typeof window !== 'undefined' && window.WP_API_BASE) || '';
    const crisisType = (opts && opts.crisisType) || 'natural_disaster';
    const crisisDescription = (opts && opts.crisisDescription) || '';
    const maxRounds = (opts && opts.maxRounds) || 3;
    const url = apiBase + '/stream/debate?crisis_type=' + encodeURIComponent(crisisType) +
      '&crisis_description=' + encodeURIComponent(crisisDescription) +
      '&force_canned=true&max_rounds=' + maxRounds;
    subscribeSSE(url, false);
  }, []);

  const pause = React.useCallback(() => {
    closeSSE();
    setState(prev => ({ ...prev, running: false, connectionStatus: 'paused' }));
  }, []);

  const reset = React.useCallback(() => {
    closeSSE();
    setState({
      running: false, step: 0, maxSteps: 50,
      utterances: [], activeSpeakerId: null,
      pnlRows: AGENTS.map(a => ({
        countryId: a.id, countryName: a.name, tint: a.tint,
        metrics: { gdp: 0, jobs: 0, energy: 0, influence: 0, welfare: 0, heritage: 0, military: 0 },
        deltasSinceLastTick: {},
      })),
      companyTicks: COMPANIES.map(c => ({ ...c })),
      marketLive: false,
      sentimentByAgent: {},
      sentimentLive: false,
      voteTally: null,
      rhetoricAlert: null,
      involvement: { involved: [], peripheral: [], uninvolved: [] },
      currentRound: 0,
      totalRounds: 0,
      roundDividers: [],
      debateArcs: [],
      crisisCountry: null,
      crisisType: 'natural_disaster',
      connectionStatus: 'idle',
      connectionError: null,
      liveMode: 'canned',
      debateHistory: _loadDebateHistory(),
    });
  }, []);

  const loadHistory = React.useCallback((session) => {
    closeSSE();
    setState(prev => ({
      ...prev,
      running: false,
      utterances: session.utterances || [],
      voteTally: session.voteTally || null,
      currentRound: session.rounds || 0,
      totalRounds: session.rounds || 0,
      crisisType: session.crisisType || 'natural_disaster',
      activeSpeakerId: null,
      connectionStatus: 'complete',
      connectionError: null,
      liveMode: session.liveMode || 'canned',
      roundDividers: [],
    }));
  }, []);

  return { state, startLive, startCanned, pause, reset, loadHistory };
}

Object.assign(window, { useDebateStream });
