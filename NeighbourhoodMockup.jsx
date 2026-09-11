import React, { useState, useMemo } from "react";
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Cell, Tooltip as RTooltip,
} from "recharts";

/* ------------------------------------------------------------------ *
 *  SC2006 — Neighbourhood Comparison App
 *  Interactive UI mockup (Lab 1 deliverable, high-fidelity)
 *  Screens map to user-facing use cases:
 *    UC-3 Select Neighbourhoods · UC-1 Set Preferences · UC-2 Clarify
 *    UC-4 Ranking & Recommendation · UC-9 Visual Results · UC-5 Explain
 * ------------------------------------------------------------------ */

const FACTORS = [
  { key: "transport", label: "Public transport", color: "#3E6DA6" },
  { key: "greenery",   label: "Greenery",         color: "#3E9B57" },
  { key: "healthcare", label: "Healthcare",       color: "#C1566A" },
  { key: "amenities",  label: "Amenities",        color: "#D69B36" },
  { key: "housing",    label: "Housing",          color: "#7B6BB2" },
];

// Mock category scores (0–10). null = data unavailable (FR 1.3.3.1).
// x,y are 0–100 positions on the stylised map (west→east, north→south).
const AREAS = {
  "Clementi":    { transport: 8.2, greenery: 7.0, healthcare: 6.5, amenities: 8.0, housing: 7.6, density: "mid",  x: 34, y: 63 },
  "Tampines":    { transport: 8.0, greenery: 7.5, healthcare: 8.2, amenities: 9.0, housing: 7.2, density: "high", x: 83, y: 54 },
  "Queenstown":  { transport: 9.0, greenery: 6.9, healthcare: null, amenities: 8.5, housing: 5.8, density: "high", x: 46, y: 71 },
  "Jurong West": { transport: 7.4, greenery: 7.8, healthcare: 7.0, amenities: 8.2, housing: 8.1, density: "mid",  x: 17, y: 58 },
  "Woodlands":   { transport: 6.8, greenery: 8.4, healthcare: 6.9, amenities: 7.6, housing: 8.6, density: "mid",  x: 41, y: 17 },
  "Bishan":      { transport: 8.6, greenery: 8.0, healthcare: 7.4, amenities: 8.3, housing: 6.4, density: "mid",  x: 52, y: 47 },
  "Ang Mo Kio":  { transport: 8.3, greenery: 7.6, healthcare: 7.8, amenities: 8.4, housing: 6.9, density: "high", x: 56, y: 40 },
  "Bedok":       { transport: 7.9, greenery: 7.2, healthcare: 7.6, amenities: 8.6, housing: 7.4, density: "high", x: 78, y: 66 },
  "Punggol":     { transport: 7.0, greenery: 8.2, healthcare: 6.6, amenities: 7.9, housing: 8.3, density: "mid",  x: 72, y: 27 },
};
const ALL_NAMES = Object.keys(AREAS);
const DEFAULT_WEIGHT = 5;
const MAX_SELECT = 4; // stands in for the [TBD] upper bound (FR 1.1.2.1)

/* palette + type as CSS vars so custom colours render without a Tailwind compiler */
const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
:root{
  --ink:#16231F; --paper:#F4F6F4; --surface:#FFFFFF; --surface2:#EEF2EF;
  --line:#D9E0DC; --muted:#5D6B66; --brand:#0E7C6B; --brand-d:#0A5C50;
  --brand-tint:#E3F0EC; --gold:#C9731F; --gold-bg:#FBEEDF; --gold-line:#EAC79B;
}
*{box-sizing:border-box}
.nc-root{font-family:'IBM Plex Sans',system-ui,sans-serif;color:var(--ink);
  background:var(--paper);min-height:100vh;line-height:1.5;-webkit-font-smoothing:antialiased}
.nc-serif{font-family:'Fraunces',Georgia,serif}
.nc-wrap{max-width:1080px;margin:0 auto;padding:0 24px 72px}

/* top bar + stepper */
.nc-top{position:sticky;top:0;z-index:30;background:rgba(244,246,244,.88);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.nc-topin{max-width:1080px;margin:0 auto;padding:14px 24px;display:flex;
  align-items:center;justify-content:space-between;gap:16px}
.nc-brand{display:flex;align-items:center;gap:10px;font-weight:600}
.nc-logo{width:26px;height:26px;border-radius:8px;background:var(--brand);
  display:grid;place-items:center;color:#fff;font-family:'Fraunces',serif;font-weight:600}
.nc-step{display:flex;align-items:center;gap:6px}
.nc-dot{display:flex;align-items:center;gap:8px;padding:5px 12px 5px 8px;border-radius:999px;
  border:1px solid transparent;color:var(--muted);font-size:13.5px;font-weight:500;cursor:pointer}
.nc-dot .n{width:20px;height:20px;border-radius:999px;background:var(--surface2);
  display:grid;place-items:center;font-size:12px;font-weight:600;color:var(--muted)}
.nc-dot.on{background:var(--surface);border-color:var(--line);color:var(--ink)}
.nc-dot.on .n{background:var(--brand);color:#fff}
.nc-dot.done .n{background:var(--brand-tint);color:var(--brand-d)}
.nc-sep{width:16px;height:1px;background:var(--line)}

/* generic */
.nc-h1{font-size:34px;font-weight:600;letter-spacing:-.01em;margin:34px 0 6px}
.nc-lead{color:var(--muted);font-size:16px;max-width:62ch;margin:0 0 26px}
.nc-card{background:var(--surface);border:1px solid var(--line);border-radius:16px}
.nc-btn{font:inherit;font-weight:600;border-radius:11px;padding:12px 20px;border:1px solid var(--brand);
  background:var(--brand);color:#fff;cursor:pointer;transition:background .15s}
.nc-btn:hover{background:var(--brand-d)}
.nc-btn:disabled{background:var(--surface2);border-color:var(--line);color:#9aa8a3;cursor:not-allowed}
.nc-btn.ghost{background:transparent;color:var(--ink);border-color:var(--line)}
.nc-btn.ghost:hover{background:var(--surface2)}
.nc-row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}

/* tag / annotation chips */
.nc-tag{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:600;
  padding:2px 8px;border-radius:6px;background:#EAF1FB;color:#2C5A93;border:1px solid #CFE0F4}
.nc-tag.gold{background:var(--gold-bg);color:var(--gold);border-color:var(--gold-line)}
.nc-tagrow{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}

/* select screen */
.nc-grid{display:grid;grid-template-columns:1fr 320px;gap:24px;align-items:start}
.nc-search{width:100%;padding:12px 14px;border:1px solid var(--line);border-radius:11px;
  font:inherit;background:var(--surface)}
.nc-search:focus{outline:2px solid var(--brand);outline-offset:1px;border-color:var(--brand)}
.nc-arealist{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}
.nc-area{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:13px 15px;
  border:1px solid var(--line);border-radius:12px;background:var(--surface);cursor:pointer;transition:.12s;text-align:left;font:inherit}
.nc-area:hover{border-color:var(--brand);background:var(--brand-tint)}
.nc-area.sel{border-color:var(--brand);background:var(--brand-tint);box-shadow:inset 0 0 0 1px var(--brand)}
.nc-area .name{font-weight:600}
.nc-area .sub{font-size:12.5px;color:var(--muted)}
.nc-check{width:20px;height:20px;border-radius:6px;border:1.5px solid var(--line);flex:none;
  display:grid;place-items:center;color:#fff}
.nc-area.sel .nc-check{background:var(--brand);border-color:var(--brand)}
.nc-tray{position:sticky;top:88px}
.nc-chip{display:inline-flex;align-items:center;gap:8px;padding:6px 8px 6px 12px;border-radius:999px;
  background:var(--brand-tint);border:1px solid #BFDDD5;color:var(--brand-d);font-weight:600;font-size:14px}
.nc-chip button{border:none;background:#fff;width:20px;height:20px;border-radius:999px;cursor:pointer;
  color:var(--muted);font-weight:700;line-height:1;display:grid;place-items:center}
.nc-empty{color:var(--muted);font-size:14px;padding:8px 0}
.nc-hint{font-size:13.5px;color:var(--muted);margin-top:12px}
.nc-warn{font-size:13.5px;color:#B4531E;margin-top:12px}

/* preferences */
.nc-fac{padding:18px 20px;border-bottom:1px solid var(--line)}
.nc-fac:last-child{border-bottom:none}
.nc-fachead{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
.nc-facname{display:flex;align-items:center;gap:10px;font-weight:600}
.nc-swatch{width:12px;height:12px;border-radius:4px;flex:none}
.nc-val{font-family:'Fraunces',serif;font-size:22px;font-weight:600;min-width:34px;text-align:right}
.nc-val.def{color:var(--muted);font-weight:500}
.nc-slider{-webkit-appearance:none;appearance:none;width:100%;height:6px;border-radius:999px;
  background:var(--surface2);outline:none}
.nc-slider::-webkit-slider-thumb{-webkit-appearance:none;width:22px;height:22px;border-radius:999px;
  background:#fff;border:2px solid var(--brand);cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,.18)}
.nc-slider::-moz-range-thumb{width:22px;height:22px;border-radius:999px;background:#fff;
  border:2px solid var(--brand);cursor:pointer}
.nc-scale{display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);margin-top:6px}
.nc-defnote{font-size:12.5px;color:var(--muted);margin-top:8px}

/* clarifying question (UC-2) */
.nc-clar{margin:0 0 22px;border:1px solid var(--gold-line);background:var(--gold-bg);border-radius:16px;
  padding:18px 20px;display:flex;gap:14px;align-items:flex-start}
.nc-clar .ic{width:34px;height:34px;border-radius:10px;background:#fff;border:1px solid var(--gold-line);
  display:grid;place-items:center;flex:none;color:var(--gold);font-family:'Fraunces',serif;font-weight:700}

/* results */
.nc-rec{overflow:hidden;border:1px solid var(--gold-line)}
.nc-rectop{background:linear-gradient(180deg,var(--gold-bg),#fff);padding:26px 28px;
  display:flex;gap:26px;align-items:center;flex-wrap:wrap}
.nc-recscore{font-family:'Fraunces',serif;font-size:76px;line-height:.9;font-weight:600;color:var(--gold)}
.nc-badge{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;font-weight:700;letter-spacing:.02em;
  color:var(--gold);background:#fff;border:1px solid var(--gold-line);border-radius:999px;padding:4px 12px}
.nc-recname{font-family:'Fraunces',serif;font-size:32px;font-weight:600;margin:8px 0 4px}
.nc-drivers{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.nc-driver{display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:600;
  background:var(--surface2);border-radius:999px;padding:5px 12px}

.nc-cols{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px}
.nc-panel{padding:20px 22px}
.nc-panelh{display:flex;align-items:center;justify-content:space-between;margin-bottom:4px}
.nc-panelh h3{font-size:17px;font-weight:600;margin:0}
.nc-panelsub{color:var(--muted);font-size:13px;margin:0 0 14px}

.nc-rank{display:flex;align-items:center;gap:14px;padding:13px 0;border-bottom:1px solid var(--line)}
.nc-rank:last-child{border-bottom:none}
.nc-rankn{font-family:'Fraunces',serif;font-size:20px;font-weight:600;width:34px;color:var(--muted)}
.nc-rank.top .nc-rankn{color:var(--gold)}
.nc-rankbar{flex:1}
.nc-rankbar .lab{display:flex;justify-content:space-between;font-size:14px;font-weight:600;margin-bottom:5px}
.nc-track{height:8px;border-radius:999px;background:var(--surface2);overflow:hidden}
.nc-fill{height:100%;border-radius:999px;background:var(--brand)}
.nc-rank.top .nc-fill{background:var(--gold)}
.nc-linkbtn{border:none;background:none;color:var(--brand-d);font:inherit;font-weight:600;
  font-size:13px;cursor:pointer;padding:0}
.nc-linkbtn:hover{text-decoration:underline}

/* map */
.nc-map{position:relative;border-radius:12px;overflow:hidden;background:#EAF0EE;
  border:1px solid var(--line);height:300px}
.nc-pin{position:absolute;transform:translate(-50%,-100%);display:flex;flex-direction:column;
  align-items:center;gap:2px}
.nc-pindot{width:16px;height:16px;border-radius:999px;border:2.5px solid #fff;
  box-shadow:0 1px 4px rgba(0,0,0,.3)}
.nc-pinlab{font-size:11px;font-weight:700;background:#fff;padding:1px 6px;border-radius:6px;
  border:1px solid var(--line);white-space:nowrap}
.nc-mapfail{height:300px;border-radius:12px;border:1px dashed var(--line);background:var(--surface2);
  display:grid;place-items:center;text-align:center;padding:24px;color:var(--muted)}

/* explanation modal (UC-5) */
.nc-scrim{position:fixed;inset:0;background:rgba(22,35,31,.42);z-index:50;display:grid;
  place-items:center;padding:24px}
.nc-modal{background:var(--surface);border-radius:18px;max-width:520px;width:100%;
  max-height:88vh;overflow:auto;box-shadow:0 24px 60px rgba(0,0,0,.28)}
.nc-modalh{padding:22px 24px 14px;border-bottom:1px solid var(--line);
  display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.nc-x{border:1px solid var(--line);background:#fff;width:32px;height:32px;border-radius:9px;
  cursor:pointer;font-size:16px;color:var(--muted)}
.nc-contrib{padding:14px 24px 4px}
.nc-cbar{margin-bottom:16px}
.nc-cbar .top{display:flex;justify-content:space-between;font-size:14px;margin-bottom:6px}
.nc-cbar .top b{font-weight:600}
.nc-cbar .trk{height:10px;border-radius:999px;background:var(--surface2);overflow:hidden}
.nc-cbar .amt{font-variant-numeric:tabular-nums;color:var(--muted);font-size:13px}
.nc-unavail{font-size:13px;color:#B4531E;background:#FBEDE4;border:1px solid #F0CDB6;
  border-radius:10px;padding:10px 12px;margin:2px 24px 18px}

/* demo controls */
.nc-demo{border:1px dashed var(--line);border-radius:14px;padding:14px 18px;margin:28px 0 0;
  background:var(--surface)}
.nc-demo h4{margin:0 0 4px;font-size:13px;font-weight:700;color:var(--muted)}
.nc-demo p{margin:0 0 12px;font-size:12.5px;color:var(--muted)}
.nc-toggle{display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:600;cursor:pointer;
  padding:7px 12px;border:1px solid var(--line);border-radius:999px;background:var(--surface2)}
.nc-toggle.on{background:var(--brand-tint);border-color:#BFDDD5;color:var(--brand-d)}

.nc-foot{margin-top:36px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:12.5px}
@media (max-width:820px){
  .nc-grid{grid-template-columns:1fr}.nc-cols{grid-template-columns:1fr}
  .nc-arealist{grid-template-columns:1fr}.nc-tray{position:static}
}
`;

const roundHalf = (n) => Math.round(n * 10) / 10;

function Tag({ children, gold }) {
  return <span className={"nc-tag" + (gold ? " gold" : "")}>{children}</span>;
}

export default function App() {
  const [step, setStep] = useState("select");           // select | prefs | results
  const [selected, setSelected] = useState(["Clementi", "Tampines", "Queenstown"]);
  const [weights, setWeights] = useState({});           // key -> 0..10 (absent = default)
  const [query, setQuery] = useState("");
  const [annot, setAnnot] = useState(true);             // requirement tags overlay
  const [explain, setExplain] = useState(null);         // neighbourhood name or null
  const [clarAnswered, setClarAnswered] = useState(false);

  // demo state toggles (for the lab demo — show alternate flows)
  const [listError, setListError] = useState(false);
  const [mapDown, setMapDown] = useState(false);

  const effWeight = (k) => (weights[k] === undefined ? DEFAULT_WEIGHT : weights[k]);

  const toggleArea = (name) => {
    setSelected((s) =>
      s.includes(name) ? s.filter((n) => n !== name)
      : s.length >= MAX_SELECT ? s : [...s, name]
    );
  };

  // overall score = weighted mean of AVAILABLE category scores (FR 1.3.3.1: skip nulls)
  const scoreOf = (name) => {
    const a = AREAS[name];
    let num = 0, den = 0, missing = [];
    FACTORS.forEach((f) => {
      const v = a[f.key];
      if (v === null) { missing.push(f.label); return; }
      const w = effWeight(f.key);
      num += v * w; den += w;
    });
    return { overall: den ? num / den : 0, missing };
  };

  const ranked = useMemo(() => {
    const rows = selected.map((n) => ({ name: n, ...scoreOf(n) }))
      .sort((a, b) => b.overall - a.overall);
    // joint ranking on equal displayed score (FR 1.3.5.1)
    let rank = 0, prevDisp = null;
    rows.forEach((r, i) => {
      const disp = roundHalf(r.overall);
      if (disp !== prevDisp) rank = i + 1;
      r.rank = rank; r.disp = disp; prevDisp = disp;
    });
    const joint = {};
    rows.forEach((r) => { joint[r.rank] = (joint[r.rank] || 0) + 1; });
    rows.forEach((r) => { r.joint = joint[r.rank] > 1; });
    return rows;
    // eslint-disable-next-line
  }, [selected, weights]);

  const top = ranked[0];
  const maxOverall = Math.max(...ranked.map((r) => r.overall), 1);

  // top contributing factors for the recommendation (weight × score)
  const drivers = useMemo(() => {
    if (!top) return [];
    const a = AREAS[top.name];
    return FACTORS.filter((f) => a[f.key] !== null)
      .map((f) => ({ ...f, contrib: a[f.key] * effWeight(f.key) }))
      .sort((x, y) => y.contrib - x.contrib).slice(0, 3);
    // eslint-disable-next-line
  }, [top, weights]);

  const radarData = FACTORS.map((f) => {
    const row = { factor: f.label.replace("Public ", "") };
    selected.forEach((n) => { row[n] = AREAS[n][f.key] ?? 0; });
    return row;
  });

  const hasDense = selected.some((n) => AREAS[n].density === "high");
  const showClar = step === "prefs" && hasDense && !clarAnswered;

  const filtered = ALL_NAMES.filter((n) => n.toLowerCase().includes(query.toLowerCase()));
  const canProceed = selected.length >= 2;

  const seriesColors = ["#0E7C6B", "#C9731F", "#7B6BB2", "#3E6DA6"];

  return (
    <div className="nc-root">
      <style>{CSS}</style>

      {/* ---------- top bar ---------- */}
      <div className="nc-top">
        <div className="nc-topin">
          <div className="nc-brand">
            <span className="nc-logo">N</span>
            <span>NeighbourFit <span style={{ color: "var(--muted)", fontWeight: 400 }}>· SG</span></span>
          </div>
          <div className="nc-step">
            {[["select", "Select"], ["prefs", "Preferences"], ["results", "Results"]].map(([k, l], i) => {
              const order = ["select", "prefs", "results"];
              const done = order.indexOf(step) > i;
              const unlocked = k === "select" || (k === "prefs" && canProceed) || (k === "results" && canProceed);
              return (
                <React.Fragment key={k}>
                  {i > 0 && <span className="nc-sep" />}
                  <button
                    className={"nc-dot" + (step === k ? " on" : done ? " done" : "")}
                    onClick={() => unlocked && setStep(k)}
                    style={{ opacity: unlocked ? 1 : 0.5, cursor: unlocked ? "pointer" : "not-allowed" }}
                  >
                    <span className="n">{done ? "✓" : i + 1}</span>{l}
                  </button>
                </React.Fragment>
              );
            })}
          </div>
          <button className={"nc-toggle" + (annot ? " on" : "")} onClick={() => setAnnot(!annot)}>
            <span style={{ fontSize: 12 }}>◎</span> Requirement tags
          </button>
        </div>
      </div>

      <div className="nc-wrap">
        {/* ================= SELECT (UC-3) ================= */}
        {step === "select" && (
          <>
            <h1 className="nc-h1 nc-serif">Which neighbourhoods are you weighing up?</h1>
            <p className="nc-lead">
              Pick between two and {MAX_SELECT} planning areas to compare. You can change the set any time.
            </p>
            {annot && (
              <div className="nc-tagrow" style={{ margin: "-14px 0 20px" }}>
                <Tag>UC-3 Select Neighbourhoods</Tag>
                <Tag>FR 1.1.1 · list from URA Planning Areas</Tag>
                <Tag>FR 1.1.2.1 · 2 to [TBD] areas</Tag>
              </div>
            )}

            {listError ? (
              <div className="nc-card" style={{ padding: 40, textAlign: "center" }}>
                <div style={{ fontSize: 22, marginBottom: 6 }} className="nc-serif">Couldn’t load the list</div>
                <p style={{ color: "var(--muted)", maxWidth: "44ch", margin: "0 auto 18px" }}>
                  The neighbourhood list didn’t load. Check your connection and try again.
                </p>
                <button className="nc-btn" onClick={() => setListError(false)}>Try again</button>
                {annot && <div className="nc-tagrow" style={{ justifyContent: "center", marginTop: 16 }}>
                  <Tag>UC-3 · E1 list fails to load → retry</Tag></div>}
              </div>
            ) : (
              <div className="nc-grid">
                <div>
                  <input
                    className="nc-search" placeholder="Search planning areas…"
                    value={query} onChange={(e) => setQuery(e.target.value)}
                  />
                  <div className="nc-arealist">
                    {filtered.map((n) => {
                      const sel = selected.includes(n);
                      const full = !sel && selected.length >= MAX_SELECT;
                      return (
                        <button key={n} className={"nc-area" + (sel ? " sel" : "")}
                          onClick={() => toggleArea(n)} disabled={full}
                          style={full ? { opacity: 0.45, cursor: "not-allowed" } : {}}>
                          <span>
                            <div className="name">{n}</div>
                            <div className="sub">URA Planning Area</div>
                          </span>
                          <span className="nc-check">{sel ? "✓" : ""}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="nc-tray">
                  <div className="nc-card" style={{ padding: 18 }}>
                    <div style={{ fontWeight: 600, marginBottom: 12 }}>
                      Selected <span style={{ color: "var(--muted)", fontWeight: 400 }}>({selected.length}/{MAX_SELECT})</span>
                    </div>
                    {selected.length === 0
                      ? <div className="nc-empty">Nothing selected yet. Pick at least two to compare.</div>
                      : <div className="nc-row">
                          {selected.map((n) => (
                            <span key={n} className="nc-chip">{n}
                              <button onClick={() => toggleArea(n)} aria-label={"Remove " + n}>×</button>
                            </span>
                          ))}
                        </div>}
                    {!canProceed
                      ? <div className="nc-warn">Select one more — a comparison needs at least two areas.</div>
                      : <div className="nc-hint">Ready to compare {selected.length} areas.</div>}
                    <button className="nc-btn" style={{ width: "100%", marginTop: 16 }}
                      disabled={!canProceed} onClick={() => setStep("prefs")}>
                      Set preferences
                    </button>
                  </div>
                  {annot && <div className="nc-tagrow"><Tag>UC-3 · A2 blocks &lt; 2 selected</Tag></div>}
                </div>
              </div>
            )}
          </>
        )}

        {/* ================= PREFERENCES (UC-1 / UC-2) ================= */}
        {step === "prefs" && (
          <>
            <h1 className="nc-h1 nc-serif">How much does each factor matter to you?</h1>
            <p className="nc-lead">
              Slide each factor from 0 (not important) to 10 (essential). Anything you leave untouched
              uses a default weight of {DEFAULT_WEIGHT}.
            </p>
            {annot && (
              <div className="nc-tagrow" style={{ margin: "-14px 0 20px" }}>
                <Tag>UC-1 Set Category Preferences</Tag>
                <Tag>FR 1.2.1 · five factors</Tag>
                <Tag>FR 1.2.2–1.2.6 · scale 0–10</Tag>
                <Tag>FR 1.2.7 · default weight</Tag>
              </div>
            )}

            {showClar && (
              <div className="nc-clar">
                <span className="ic">?</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, marginBottom: 3 }}>One quick question</div>
                  <p style={{ margin: "0 0 12px", color: "var(--ink)" }}>
                    {selected.find((n) => AREAS[n].density === "high")} is fairly dense.
                    Would higher population density bother you?
                  </p>
                  <div className="nc-row">
                    <button className="nc-btn ghost" onClick={() => setClarAnswered(true)}>Yes, I’d prefer quieter</button>
                    <button className="nc-btn ghost" onClick={() => setClarAnswered(true)}>No, that’s fine</button>
                    <button className="nc-linkbtn" onClick={() => setClarAnswered(true)}>Skip</button>
                  </div>
                  {annot && <div className="nc-tagrow"><Tag gold>UC-2 «extend» · FR 1.5</Tag>
                    <Tag gold>skip → default [TBD] (FR 1.5.2.1)</Tag></div>}
                </div>
              </div>
            )}

            <div className="nc-card">
              {FACTORS.map((f) => {
                const set = weights[f.key] !== undefined;
                return (
                  <div className="nc-fac" key={f.key}>
                    <div className="nc-fachead">
                      <span className="nc-facname">
                        <span className="nc-swatch" style={{ background: f.color }} />{f.label}
                      </span>
                      <span className={"nc-val" + (set ? "" : " def")}>{effWeight(f.key)}</span>
                    </div>
                    <input className="nc-slider" type="range" min="0" max="10" step="1"
                      value={effWeight(f.key)}
                      onChange={(e) => setWeights({ ...weights, [f.key]: Number(e.target.value) })} />
                    <div className="nc-scale"><span>Not important</span><span>Essential</span></div>
                    {!set && <div className="nc-defnote">Using default weight of {DEFAULT_WEIGHT} — move the slider to set your own.</div>}
                  </div>
                );
              })}
            </div>

            <div className="nc-row" style={{ marginTop: 22, justifyContent: "space-between" }}>
              <button className="nc-btn ghost" onClick={() => setStep("select")}>← Back</button>
              <button className="nc-btn" onClick={() => setStep("results")}>See results</button>
            </div>
          </>
        )}

        {/* ================= RESULTS (UC-4 + UC-9) ================= */}
        {step === "results" && top && (
          <>
            <h1 className="nc-h1 nc-serif">Here’s how they compare</h1>
            <p className="nc-lead">Ranked by how well each area fits the preferences you set.</p>
            {annot && (
              <div className="nc-tagrow" style={{ margin: "-14px 0 20px" }}>
                <Tag gold>UC-4 View Ranking &amp; Recommendation</Tag>
                <Tag>UC-9 «include» Visual Results</Tag>
                <Tag>UC-6 «include» Compute Scores</Tag>
              </div>
            )}

            {/* recommendation hero */}
            <div className="nc-card nc-rec">
              <div className="nc-rectop">
                <div>
                  <span className="nc-badge">★ Best fit for you</span>
                  <div className="nc-recname">{top.name}</div>
                  <div style={{ color: "var(--muted)", fontSize: 14 }}>Highest overall score across your {selected.length} areas</div>
                  <div className="nc-drivers">
                    <span style={{ fontSize: 13, color: "var(--muted)", alignSelf: "center" }}>Driven by</span>
                    {drivers.map((d) => (
                      <span key={d.key} className="nc-driver">
                        <span className="nc-swatch" style={{ background: d.color }} />{d.label}
                      </span>
                    ))}
                  </div>
                </div>
                <div style={{ marginLeft: "auto", textAlign: "center" }}>
                  <div className="nc-recscore">{top.disp}</div>
                  <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 2 }}>out of 10</div>
                </div>
              </div>
              {annot && <div style={{ padding: "0 24px 16px" }}><div className="nc-tagrow">
                <Tag gold>FR 1.4.2.1 · top contributing factors</Tag></div></div>}
            </div>

            <div className="nc-cols">
              {/* ranking */}
              <div className="nc-card nc-panel">
                <div className="nc-panelh"><h3>Overall ranking</h3></div>
                <p className="nc-panelsub">Weighted score for each area · tap a name for the breakdown.</p>
                {ranked.map((r) => (
                  <div className={"nc-rank" + (r.rank === 1 ? " top" : "")} key={r.name}>
                    <span className="nc-rankn">{r.joint ? "=" : ""}{r.rank}</span>
                    <div className="nc-rankbar">
                      <div className="lab">
                        <button className="nc-linkbtn" style={{ fontSize: 14 }} onClick={() => setExplain(r.name)}>{r.name}</button>
                        <span className="nc-serif" style={{ fontSize: 16 }}>{r.disp}</span>
                      </div>
                      <div className="nc-track"><div className="nc-fill" style={{ width: (r.overall / maxOverall * 100) + "%" }} /></div>
                      {r.missing.length > 0 && (
                        <div style={{ fontSize: 12, color: "#B4531E", marginTop: 5 }}>
                          {r.missing.join(", ")} data unavailable — left out of the score
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                {annot && <div className="nc-tagrow" style={{ marginTop: 14 }}>
                  <Tag>FR 1.3.5 rank</Tag><Tag>FR 1.3.3.1 unavailable ≠ zero</Tag>
                  <Tag>FR 1.3.5.1 joint rank</Tag></div>}
              </div>

              {/* radar */}
              <div className="nc-card nc-panel">
                <div className="nc-panelh"><h3>Factor profiles</h3></div>
                <p className="nc-panelsub">Category scores (0–10) per factor, before your weights.</p>
                <div style={{ height: 260 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart data={radarData} outerRadius="72%">
                      <PolarGrid stroke="#D9E0DC" />
                      <PolarAngleAxis dataKey="factor" tick={{ fontSize: 11, fill: "#5D6B66" }} />
                      {selected.map((n, i) => (
                        <Radar key={n} name={n} dataKey={n}
                          stroke={seriesColors[i]} fill={seriesColors[i]} fillOpacity={0.12} strokeWidth={2} />
                      ))}
                      <RTooltip />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
                <div className="nc-row" style={{ justifyContent: "center", gap: 16 }}>
                  {selected.map((n, i) => (
                    <span key={n} style={{ fontSize: 12.5, fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
                      <span className="nc-swatch" style={{ background: seriesColors[i], borderRadius: 3 }} />{n}
                    </span>
                  ))}
                </div>
                {annot && <div className="nc-tagrow" style={{ marginTop: 12 }}><Tag>FR 1.6.1–1.6.3 · charts</Tag></div>}
              </div>
            </div>

            {/* map */}
            <div className="nc-card nc-panel" style={{ marginTop: 20 }}>
              <div className="nc-panelh"><h3>On the map</h3></div>
              <p className="nc-panelsub">Where your selected areas sit across Singapore.</p>
              {mapDown ? (
                <div className="nc-mapfail">
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 600, color: "var(--ink)", marginBottom: 4 }}>Map is unavailable right now</div>
                    Scores and charts above are still up to date. The map will return when the service is back.
                    {annot && <div className="nc-tagrow" style={{ justifyContent: "center", marginTop: 12 }}>
                      <Tag>UC-9 · A1 map service unreachable</Tag></div>}
                  </div>
                </div>
              ) : (
                <div className="nc-map">
                  {/* stylised SG landmass */}
                  <svg viewBox="0 0 100 62" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
                    <path d="M8,30 C10,20 20,12 34,12 C46,12 52,10 64,13 C78,16 92,20 94,32 C95,42 86,50 72,52 C58,54 40,55 26,52 C14,49 6,40 8,30 Z"
                      fill="#DCE8E2" stroke="#BFD3CA" strokeWidth="0.6" />
                  </svg>
                  {selected.map((n, i) => (
                    <div key={n} className="nc-pin" style={{ left: AREAS[n].x + "%", top: AREAS[n].y + "%" }}>
                      <span className="nc-pinlab">{n}</span>
                      <span className="nc-pindot" style={{ background: seriesColors[i] }} />
                    </div>
                  ))}
                </div>
              )}
              {annot && !mapDown && <div className="nc-tagrow" style={{ marginTop: 12 }}>
                <Tag>FR 1.6.4 · locations on map</Tag><Tag>UC-9 · Map/Geocoding Service</Tag></div>}
            </div>

            <div className="nc-row" style={{ marginTop: 22, justifyContent: "space-between" }}>
              <button className="nc-btn ghost" onClick={() => setStep("prefs")}>← Adjust preferences</button>
              <button className="nc-btn ghost" onClick={() => setStep("select")}>Change areas</button>
            </div>
          </>
        )}

        {/* ---------- demo controls (for the lab demo) ---------- */}
        <div className="nc-demo">
          <h4>Demo controls</h4>
          <p>Toggle the alternate flows the use cases describe — for showing graders the edge cases, not part of the everyday UI.</p>
          <div className="nc-row">
            <button className={"nc-toggle" + (listError ? " on" : "")} onClick={() => { setListError(!listError); setStep("select"); }}>
              List load error (UC-3 · E1)
            </button>
            <button className={"nc-toggle" + (showClar ? " on" : "")} onClick={() => { setClarAnswered(false); setStep("prefs"); }}>
              Clarifying question (UC-2)
            </button>
            <button className={"nc-toggle" + (mapDown ? " on" : "")} onClick={() => { setMapDown(!mapDown); setStep("results"); }}>
              Map unavailable (UC-9 · A1)
            </button>
          </div>
          <p style={{ margin: "12px 0 0" }}>
            Note: <b>Queenstown</b> is seeded with missing healthcare data, so the results screen also
            shows the “unavailable ≠ zero” behaviour (FR 1.3.3.1) without any toggle.
          </p>
        </div>

        <div className="nc-foot">
          SC2006 Software Engineering · Lab 1 UI mockup · Neighbourhood Comparison App · Team 5.
          Screens are illustrative; values are placeholder data.
        </div>
      </div>

      {/* ---------- explanation modal (UC-5) ---------- */}
      {explain && (() => {
        const a = AREAS[explain];
        const rows = FACTORS.map((f) => ({
          ...f, score: a[f.key],
          contrib: a[f.key] === null ? null : a[f.key] * effWeight(f.key),
        }));
        const avail = rows.filter((r) => r.contrib !== null).sort((x, y) => y.contrib - x.contrib);
        const maxC = Math.max(...avail.map((r) => r.contrib), 1);
        const missing = rows.filter((r) => r.contrib === null);
        return (
          <div className="nc-scrim" onClick={() => setExplain(null)}>
            <div className="nc-modal" onClick={(e) => e.stopPropagation()}>
              <div className="nc-modalh">
                <div>
                  <div className="nc-serif" style={{ fontSize: 24, fontWeight: 600 }}>{explain}</div>
                  <div style={{ color: "var(--muted)", fontSize: 13.5, marginTop: 2 }}>
                    Why it scored {roundHalf(scoreOf(explain).overall)} — factors ordered by contribution.
                  </div>
                </div>
                <button className="nc-x" onClick={() => setExplain(null)}>×</button>
              </div>
              <div className="nc-contrib">
                {avail.map((r) => (
                  <div className="nc-cbar" key={r.key}>
                    <div className="top">
                      <b><span className="nc-swatch" style={{ background: r.color, display: "inline-block", marginRight: 8 }} />{r.label}</b>
                      <span className="amt">score {r.score} × weight {effWeight(r.key)}</span>
                    </div>
                    <div className="trk"><div style={{ height: "100%", width: (r.contrib / maxC * 100) + "%", background: r.color, borderRadius: 999 }} /></div>
                  </div>
                ))}
              </div>
              {missing.map((r) => (
                <div className="nc-unavail" key={r.key}>
                  {r.label} data isn’t available for {explain}, so it was left out of the score rather than counted as zero.
                </div>
              ))}
              {annot && <div style={{ padding: "0 24px 20px" }}><div className="nc-tagrow">
                <Tag gold>UC-5 «extend» View Score Explanation</Tag>
                <Tag>Transparency NFR</Tag></div></div>}
            </div>
          </div>
        );
      })()}
    </div>
  );
}
