/* Globe — accurate country boundaries from Natural Earth 110m TopoJSON */

// 7-agent council. P1 plan: marker entries must exist for every speakerId so the
// debate-driven activeSpeaker pulse can find a coordinate. GBR + BRA kept as
// neutral-coloured nodes for visual variety.
const COUNTRIES_MARKERS = [
  { id: 'USA',    name: 'United States',  lat: 38.9,  lon: -77.0,  color: '#3b82f6' },
  { id: 'RUS',    name: 'Russia',         lat: 55.8,  lon: 37.6,   color: '#ef4444' },
  { id: 'CHN',    name: 'China',          lat: 39.9,  lon: 116.4,  color: '#f59e0b' },
  { id: 'IND',    name: 'India',          lat: 28.6,  lon: 77.2,   color: '#22c55e' },
  { id: 'DPRK',   name: 'North Korea',    lat: 39.0,  lon: 125.8,  color: '#ef4444' },
  { id: 'SAU',    name: 'Saudi Arabia',   lat: 24.7,  lon: 46.7,   color: '#22c55e' },
  { id: 'UNESCO', name: 'UNESCO (Paris)', lat: 48.85, lon: 2.35,   color: '#14b8a6' },
  { id: 'GBR',    name: 'United Kingdom', lat: 51.5,  lon: -0.1,   color: '#8b5cf6' },
  { id: 'BRA',    name: 'Brazil',         lat: -15.8, lon: -47.9,  color: '#14b8a6' },
];

// Orthographic projection
function ortho(lat, lon, cx, cy, R, cLon, cLat) {
  const d = Math.PI / 180;
  const sLat = Math.sin(lat*d), cLat2 = Math.cos(lat*d);
  const dL = (lon - cLon)*d;
  const sCL = Math.sin(cLat*d), cCL = Math.cos(cLat*d);
  return {
    x: cx + R * cLat2 * Math.sin(dL),
    y: cy - R * (cCL * sLat - sCL * cLat2 * Math.cos(dL)),
    z: sCL * sLat + cCL * cLat2 * Math.cos(dL)
  };
}

// Convert TopoJSON to GeoJSON features
function topoToGeo(topo) {
  const obj = topo.objects[Object.keys(topo.objects)[0]];
  const arcsData = topo.arcs;
  const tf = topo.transform;
  // Decode quantized arcs
  const decoded = arcsData.map(arc => {
    let x = 0, y = 0;
    return arc.map(([dx, dy]) => {
      x += dx; y += dy;
      return [x * tf.scale[0] + tf.translate[0], y * tf.scale[1] + tf.translate[1]];
    });
  });
  function decodeArc(idx) {
    if (idx >= 0) return decoded[idx].slice();
    const a = decoded[~idx].slice(); a.reverse(); return a;
  }
  function decodeRing(indices) {
    let coords = [];
    indices.forEach(idx => {
      const a = decodeArc(idx);
      if (coords.length) a.shift(); // remove duplicate join point
      coords = coords.concat(a);
    });
    return coords;
  }
  return obj.geometries.map(geom => {
    let polys = [];
    if (geom.type === 'Polygon') {
      polys = [geom.arcs.map(ring => decodeRing(ring))];
    } else if (geom.type === 'MultiPolygon') {
      polys = geom.arcs.map(poly => poly.map(ring => decodeRing(ring)));
    }
    return { id: geom.id, properties: geom.properties || {}, polygons: polys };
  });
}

const STARS = Array.from({length: 180}, () => ({
  x: Math.random(), y: Math.random(), r: Math.random()*1.1+0.3, a: Math.random()*0.5+0.2
}));

function GlobeCanvas({ step, arcs, disasterCountry, activeSpeakerId, debateArcs, crisisCountry }) {
  const canvasRef = React.useRef(null);
  const frameRef = React.useRef(null);
  const rotRef = React.useRef({ lon: -40, lat: 15 });
  const dragRef = React.useRef(null);
  const velRef = React.useRef(0.12);
  const geoRef = React.useRef(null);
  const [loaded, setLoaded] = React.useState(false);

  // Load world boundary data
  React.useEffect(() => {
    fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
      .then(r => r.json())
      .then(topo => {
        geoRef.current = topoToGeo(topo);
        setLoaded(true);
      })
      .catch(err => console.warn('Globe data load failed:', err));
  }, []);

  // Drag
  React.useEffect(() => {
    const c = canvasRef.current; if (!c) return;
    let timer = null;
    const down = e => {
      const p = e.touches?e.touches[0]:e;
      dragRef.current = { sx:p.clientX, sy:p.clientY, slon:rotRef.current.lon, slat:rotRef.current.lat };
      velRef.current = 0; clearTimeout(timer); e.preventDefault();
    };
    const move = e => {
      if (!dragRef.current) return;
      const p = e.touches?e.touches[0]:e;
      rotRef.current.lon = dragRef.current.slon - (p.clientX-dragRef.current.sx)*0.35;
      rotRef.current.lat = Math.max(-60,Math.min(60, dragRef.current.slat + (p.clientY-dragRef.current.sy)*0.35));
    };
    const up = () => { dragRef.current=null; timer=setTimeout(()=>velRef.current=0.12, 1500); };
    c.addEventListener('mousedown',down); c.addEventListener('touchstart',down,{passive:false});
    window.addEventListener('mousemove',move); window.addEventListener('touchmove',move,{passive:false});
    window.addEventListener('mouseup',up); window.addEventListener('touchend',up);
    return () => {
      c.removeEventListener('mousedown',down); c.removeEventListener('touchstart',down);
      window.removeEventListener('mousemove',move); window.removeEventListener('touchmove',move);
      window.removeEventListener('mouseup',up); window.removeEventListener('touchend',up);
      clearTimeout(timer);
    };
  }, []);

  // Render loop
  React.useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let alive = true;
    window.__gd = { arcs, disasterCountry, step, activeSpeaker: activeSpeakerId, debateArcs: debateArcs || [], crisisCountry: crisisCountry || null };

    function render() {
      if (!alive) return;
      if (!dragRef.current && velRef.current > 0) rotRef.current.lon -= velRef.current;

      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      const pw = Math.round(rect.width*dpr), ph = Math.round(rect.height*dpr);
      if (canvas.width!==pw||canvas.height!==ph) { canvas.width=pw; canvas.height=ph; }
      ctx.setTransform(dpr,0,0,dpr,0,0);

      const W=rect.width, H=rect.height;
      const cx=W/2, cy=H/2, R=Math.min(W,H)*0.42;
      const cLon=rotRef.current.lon, cLat=rotRef.current.lat;
      ctx.clearRect(0,0,W,H);

      // Stars
      STARS.forEach(s => {
        const tw = 0.7+0.3*Math.sin(Date.now()/1200+s.x*80);
        ctx.beginPath(); ctx.arc(s.x*W,s.y*H,s.r,0,Math.PI*2);
        ctx.fillStyle='rgba(255,255,255,'+(s.a*tw).toFixed(3)+')'; ctx.fill();
      });

      // Atmosphere
      const atmo = ctx.createRadialGradient(cx,cy,R*0.92,cx,cy,R*1.35);
      atmo.addColorStop(0,'rgba(70,140,255,0.14)');
      atmo.addColorStop(0.5,'rgba(40,100,230,0.05)');
      atmo.addColorStop(1,'transparent');
      ctx.fillStyle=atmo; ctx.beginPath(); ctx.arc(cx,cy,R*1.35,0,Math.PI*2); ctx.fill();

      // Ocean
      const oG = ctx.createRadialGradient(cx-R*0.25,cy-R*0.25,R*0.05,cx+R*0.1,cy+R*0.1,R*1.05);
      oG.addColorStop(0,'#1a4080'); oG.addColorStop(0.35,'#0f2d5c');
      oG.addColorStop(0.7,'#0a1f42'); oG.addColorStop(1,'#061228');
      ctx.beginPath(); ctx.arc(cx,cy,R,0,Math.PI*2); ctx.fillStyle=oG; ctx.fill();

      ctx.save();
      ctx.beginPath(); ctx.arc(cx,cy,R,0,Math.PI*2); ctx.clip();

      // Grid
      ctx.strokeStyle='rgba(100,170,255,0.035)'; ctx.lineWidth=0.4;
      for (let lat=-60;lat<=60;lat+=30) {
        ctx.beginPath(); let s=false;
        for (let lon=-180;lon<=180;lon+=4) {
          const p=ortho(lat,lon,cx,cy,R,cLon,cLat);
          if(p.z<0){s=false;continue;} s?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y); s=true;
        } ctx.stroke();
      }
      for (let lon=-180;lon<180;lon+=30) {
        ctx.beginPath(); let s=false;
        for (let lat=-90;lat<=90;lat+=4) {
          const p=ortho(lat,lon,cx,cy,R,cLon,cLat);
          if(p.z<0){s=false;continue;} s?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y); s=true;
        } ctx.stroke();
      }

      // Country polygons from real data
      const features = geoRef.current;
      if (features) {
        features.forEach(feat => {
          feat.polygons.forEach(poly => {
            poly.forEach((ring, ri) => {
              // Project ring — break at horizon
              let segs = [], cur = [];
              ring.forEach(([lon, lat]) => {
                const p = ortho(lat, lon, cx, cy, R, cLon, cLat);
                if (p.z > -0.02) cur.push(p);
                else if (cur.length) { segs.push(cur); cur = []; }
              });
              if (cur.length) segs.push(cur);

              segs.forEach(seg => {
                if (seg.length < 3 && ri === 0) return;
                if (seg.length < 2) return;
                ctx.beginPath();
                seg.forEach((p,i) => i===0?ctx.moveTo(p.x,p.y):ctx.lineTo(p.x,p.y));
                if (ri === 0) {
                  ctx.closePath();
                  ctx.fillStyle = 'rgba(30,100,50,0.35)';
                  ctx.fill();
                }
                ctx.strokeStyle = 'rgba(80,200,110,0.4)';
                ctx.lineWidth = 0.6;
                ctx.stroke();
              });
            });
          });
        });

        // Country border lines (render again on top for clarity)
        ctx.strokeStyle = 'rgba(100,220,130,0.18)';
        ctx.lineWidth = 0.3;
        features.forEach(feat => {
          feat.polygons.forEach(poly => {
            poly.forEach(ring => {
              ctx.beginPath(); let s = false;
              ring.forEach(([lon,lat]) => {
                const p = ortho(lat,lon,cx,cy,R,cLon,cLat);
                if (p.z < 0) { s=false; return; }
                s ? ctx.lineTo(p.x,p.y) : ctx.moveTo(p.x,p.y); s=true;
              });
              ctx.stroke();
            });
          });
        });
      }

      ctx.restore();

      // Specular
      const sp = ctx.createRadialGradient(cx-R*0.35,cy-R*0.35,0,cx-R*0.15,cy-R*0.15,R*0.55);
      sp.addColorStop(0,'rgba(255,255,255,0.06)'); sp.addColorStop(1,'transparent');
      ctx.beginPath(); ctx.arc(cx,cy,R,0,Math.PI*2); ctx.fillStyle=sp; ctx.fill();

      // Rim glow
      const rim = ctx.createRadialGradient(cx,cy,R*0.92,cx,cy,R);
      rim.addColorStop(0,'transparent'); rim.addColorStop(1,'rgba(80,160,255,0.18)');
      ctx.beginPath(); ctx.arc(cx,cy,R,0,Math.PI*2); ctx.fillStyle=rim; ctx.fill();
      ctx.strokeStyle='rgba(100,180,255,0.18)'; ctx.lineWidth=1.5; ctx.stroke();

      // Data: merge sim arcs with debate-derived arcs
      const simArcs = window.__gd?.arcs || [];
      const dArcs = window.__gd?.debateArcs || [];
      const curArcs = simArcs.concat(dArcs);
      const curDisaster = window.__gd?.disasterCountry;
      const curCrisisCountry = window.__gd?.crisisCountry;

      // Country marker nodes
      const pos = {};
      COUNTRIES_MARKERS.forEach(c => {
        const p = ortho(c.lat,c.lon,cx,cy,R,cLon,cLat);
        pos[c.id] = p;
        if (p.z<0.05) return;

        const nr = 5+p.z*6;
        const al = 0.3+p.z*0.7;
        const isDis = curDisaster===c.id || curCrisisCountry===c.id;

        ctx.beginPath(); ctx.arc(p.x,p.y,nr*3,0,Math.PI*2);
        ctx.fillStyle=c.color+'12'; ctx.fill();

        if (isDis) {
          const t=Date.now()/250;
          [0,1].forEach(ring=>{
            const s=1+0.3*Math.sin(t+ring*1.5);
            ctx.beginPath(); ctx.arc(p.x,p.y,nr*(3.5+ring*1.5)*s,0,Math.PI*2);
            ctx.strokeStyle='rgba(239,68,68,'+(0.5-ring*0.2).toFixed(2)+')';
            ctx.lineWidth=2; ctx.stroke();
          });
        }

        ctx.shadowColor=c.color; ctx.shadowBlur=16;
        const g=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,nr);
        g.addColorStop(0,'#ffffff'); g.addColorStop(0.25,c.color); g.addColorStop(1,c.color+'00');
        ctx.beginPath(); ctx.arc(p.x,p.y,nr,0,Math.PI*2);
        ctx.fillStyle=g; ctx.fill(); ctx.shadowBlur=0;

        ctx.font='500 10px Inter, sans-serif'; ctx.textAlign='center';
        ctx.fillStyle='rgba(255,255,255,'+al.toFixed(2)+')';
        ctx.fillText(c.name,p.x,p.y+nr+15);
      });

      // P1 — Active-speaker pulse: dual concentric ring on the dot of whichever
      // agent is currently delivering an utterance. Read from window.__gd to stay
      // consistent with the existing arcs/disasterCountry pattern (no per-frame
      // React reads). Tinted in the agent's color.
      const curSpeaker = window.__gd?.activeSpeaker;
      if (curSpeaker && pos[curSpeaker] && pos[curSpeaker].z > 0.05) {
        const sp = pos[curSpeaker];
        const agent = COUNTRIES_MARKERS.find(a => a.id === curSpeaker);
        const tint = agent?.color || '#ffffff';
        const t = Date.now() / 300;
        const pulse = Math.sin(t) * 0.5 + 0.5; // 0→1 oscillation
        // Inner ring
        ctx.beginPath();
        ctx.arc(sp.x, sp.y, 12 + pulse * 6, 0, Math.PI * 2);
        ctx.strokeStyle = tint + '99';
        ctx.lineWidth = 2.5;
        ctx.stroke();
        // Outer ring (phase-shifted)
        ctx.beginPath();
        ctx.arc(sp.x, sp.y, 18 + pulse * 4, 0, Math.PI * 2);
        ctx.strokeStyle = tint + '44';
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Arcs
      curArcs.forEach(arc => {
        const f=pos[arc.from],t=pos[arc.to];
        if(!f||!t||f.z<0||t.z<0) return;
        const mx=(f.x+t.x)/2, d=Math.hypot(t.x-f.x,t.y-f.y);
        const my=(f.y+t.y)/2-d*0.38;
        const col=arc.type==='SANCTION'?'#ef4444':arc.type==='AID'?'#3b82f6':arc.type==='TRADE'?'#22c55e':'#f59e0b';

        ctx.beginPath(); ctx.moveTo(f.x,f.y); ctx.quadraticCurveTo(mx,my,t.x,t.y);
        ctx.strokeStyle=col+'25'; ctx.lineWidth=arc.type==='AID'?8:5;
        ctx.setLineDash([]); ctx.stroke();

        ctx.beginPath(); ctx.moveTo(f.x,f.y); ctx.quadraticCurveTo(mx,my,t.x,t.y);
        ctx.strokeStyle=col+'cc'; ctx.lineWidth=arc.type==='AID'?2.5:1.5;
        ctx.setLineDash(arc.type==='SANCTION'?[5,4]:[]); ctx.stroke(); ctx.setLineDash([]);

        const q=(Date.now()%1800)/1800;
        const px=(1-q)*(1-q)*f.x+2*(1-q)*q*mx+q*q*t.x;
        const py=(1-q)*(1-q)*f.y+2*(1-q)*q*my+q*q*t.y;
        ctx.shadowColor=col; ctx.shadowBlur=10;
        ctx.beginPath(); ctx.arc(px,py,3,0,Math.PI*2);
        ctx.fillStyle='#fff'; ctx.fill(); ctx.shadowBlur=0;
      });

      // Coalition rendering: connect nations that share the same stance via debate arcs
      if (dArcs.length >= 2) {
        const stanceGroups = {};
        dArcs.forEach(arc => {
          const key = arc.type;
          if (!stanceGroups[key]) stanceGroups[key] = new Set();
          stanceGroups[key].add(arc.from);
        });
        Object.entries(stanceGroups).forEach(([type, agents]) => {
          if (agents.size < 3) return;
          const agentList = Array.from(agents);
          const col = type === 'AID' ? '#22c55e' : type === 'SANCTION' ? '#ef4444' : '#f59e0b';
          for (let i = 0; i < agentList.length; i++) {
            for (let j = i + 1; j < agentList.length; j++) {
              const fa = pos[agentList[i]], fb = pos[agentList[j]];
              if (!fa || !fb || fa.z < 0 || fb.z < 0) continue;
              ctx.beginPath(); ctx.moveTo(fa.x, fa.y); ctx.lineTo(fb.x, fb.y);
              ctx.strokeStyle = col + '18'; ctx.lineWidth = 1.5;
              ctx.setLineDash([3, 5]); ctx.stroke(); ctx.setLineDash([]);
            }
          }
        });
      }

      // Loading indicator
      if (!geoRef.current) {
        ctx.font='500 12px Inter, sans-serif'; ctx.textAlign='center';
        ctx.fillStyle='rgba(255,255,255,0.3)';
        ctx.fillText('Loading country boundaries...', cx, cy+R+24);
      }

      frameRef.current = requestAnimationFrame(render);
    }
    render();
    return () => { alive=false; cancelAnimationFrame(frameRef.current); };
  }, []);

  React.useEffect(() => {
    if(window.__gd){
      window.__gd.arcs = arcs;
      window.__gd.disasterCountry = disasterCountry;
      window.__gd.step = step;
      window.__gd.activeSpeaker = activeSpeakerId;
      window.__gd.debateArcs = debateArcs || [];
      window.__gd.crisisCountry = crisisCountry || null;
    }
  }, [arcs, disasterCountry, step, activeSpeakerId, debateArcs, crisisCountry]);

  return React.createElement('canvas', {
    ref: canvasRef,
    style: { width:'100%', height:'100%', display:'block', cursor:'grab' }
  });
}

window.GlobeCanvas = GlobeCanvas;
window.COUNTRIES = COUNTRIES_MARKERS;
