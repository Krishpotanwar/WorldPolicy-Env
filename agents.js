/* agents.js — Single source of truth for agent roster, tints, and globe coordinates.
   Backend canonical: debate_orchestrator.py AGENTS_CONFIG.
   All frontend files read from window.AGENTS, window.COUNTRIES_MARKERS, window.COMPANIES. */

const AGENTS = [
  { id: 'USA',    name: 'United States',  code: 'US', tint: '#3b82f6', lat: 38.9,   lon: -77.0 },
  { id: 'CHN',    name: 'China',          code: 'CN', tint: '#ef4444', lat: 39.9,   lon: 116.4 },
  { id: 'RUS',    name: 'Russia',         code: 'RU', tint: '#8b5cf6', lat: 55.8,   lon: 37.6 },
  { id: 'IND',    name: 'India',          code: 'IN', tint: '#f59e0b', lat: 28.6,   lon: 77.2 },
  { id: 'DPRK',   name: 'North Korea',    code: 'KP', tint: '#ef4444', lat: 39.0,   lon: 125.8 },
  { id: 'SAU',    name: 'Saudi Arabia',    code: 'SA', tint: '#22c55e', lat: 24.7,   lon: 46.7 },
  { id: 'UNESCO', name: 'UNESCO',          code: '\u{1F54A}', tint: '#14b8a6', lat: 48.85, lon: 2.35 },
];

const COUNTRIES_MARKERS = AGENTS.map(a => ({
  id: a.id, name: a.id === 'UNESCO' ? 'UNESCO (Paris)' : a.name,
  lat: a.lat, lon: a.lon, color: a.tint,
})).concat([
  { id: 'GBR', name: 'United Kingdom', lat: 51.5,  lon: -0.1,  color: '#8b5cf6' },
  { id: 'BRA', name: 'Brazil',         lat: -15.8, lon: -47.9, color: '#14b8a6' },
]);

const COMPANIES = [
  { symbol: 'AAPL',  name: 'Apple',      countryId: 'USA',  currency: '$', price: 189.32, pct: 0.8 },
  { symbol: 'BYDDY', name: 'BYD',        countryId: 'CHN',  currency: '\u00A5', price: 214.10, pct: -1.2 },
  { symbol: 'GAZP',  name: 'Gazprom',    countryId: 'RUS',  currency: '\u20BD', price: 142.00, pct: -2.1 },
  { symbol: 'RELI',  name: 'Reliance',   countryId: 'IND',  currency: '\u20B9', price: 2847.50, pct: 0.4 },
  { symbol: 'KOMID', name: 'KOMID Corp', countryId: 'DPRK', currency: '\u20A9', price: 88.00, pct: -0.5 },
  { symbol: '2222',  name: 'Aramco',     countryId: 'SAU',  currency: '\uFDFC', price: 32.40, pct: 1.3 },
];

const ARC_COLORS = {
  SANCTION: '#ef4444',
  AID:     '#3b82f6',
  TRADE:   '#22c55e',
  DEFAULT: '#f59e0b',
};

const STANCE_MAP = {
  support: { type: 'AID',      label: 'SUPPORTS', bg: 'rgba(34,197,94,0.15)', border: 'rgba(34,197,94,0.4)', color: '#22c55e' },
  oppose:  { type: 'SANCTION', label: 'OPPOSES',  bg: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.4)', color: '#ef4444' },
  modify:  { type: 'TRADE',    label: 'MODIFIES', bg: 'rgba(245,158,11,0.15)', border: 'rgba(245,158,11,0.4)', color: '#f59e0b' },
  neutral: { type: 'TRADE',    label: 'NEUTRAL',  bg: 'rgba(148,163,184,0.15)', border: 'rgba(148,163,184,0.4)', color: '#94a3b8' },
  mediate: { type: 'TRADE',    label: 'MEDIATES', bg: 'rgba(20,184,166,0.15)', border: 'rgba(20,184,166,0.4)', color: '#14b8a6' },
};

Object.assign(window, { AGENTS, COUNTRIES_MARKERS, COMPANIES, ARC_COLORS, STANCE_MAP });
