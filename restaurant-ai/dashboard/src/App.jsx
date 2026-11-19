// Replace the generated src/App.jsx with this file.  Needs:  npm install recharts
import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";

const API = "http://localhost:8000";
const COLORS = { OCCUPIED: "#d9e4f5", VACANT: "#fff2cc", CLEANING: "#e2efda", READY: "#c6e0b4", UNCERTAIN: "#f8cbad" };
const LABELS = { OCCUPIED: "Occupied", VACANT: "Vacant (Needs Cleaning)", CLEANING: "Cleaning", READY: "Ready", UNCERTAIN: "Uncertain" };
const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.round(s % 60)).padStart(2, "0")}`;
const clock = (t) => new Date(t * 1000).toLocaleTimeString();

function useApi(auth) {
  return async (path, opt = {}) => {
    const r = await fetch(API + path, { ...opt, headers: { "Content-Type": "application/json", Authorization: "Bearer " + auth.token, ...(opt.headers || {}) } });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    return r.json();
  };
}

function Login({ onLogin }) {
  const [u, setU] = useState("staff"), [p, setP] = useState(""), [err, setErr] = useState("");
  const go = async () => {
    const r = await fetch(API + "/api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: u, password: p }) });
    if (r.ok) onLogin(await r.json()); else setErr("Wrong username or password");
  };
  return (
    <div style={{ maxWidth: 320, margin: "80px auto", fontFamily: "Georgia, serif" }}>
      <h2>Restaurant Dashboard</h2>
      <input placeholder="username" value={u} onChange={(e) => setU(e.target.value)} style={{ width: "100%", marginBottom: 8 }} />
      <input placeholder="password" type="password" value={p} onChange={(e) => setP(e.target.value)} style={{ width: "100%", marginBottom: 8 }} />
      <button onClick={go}>Log in</button> <span style={{ color: "red" }}>{err}</span>
    </div>
  );
}

function Tables({ api }) {
  const [tables, setTables] = useState([]), [msg, setMsg] = useState("");
  useEffect(() => { const load = () => api("/api/tables").then(setTables).catch((e) => setMsg(e.message)); load(); const i = setInterval(load, 2000); return () => clearInterval(i); }, []);
  const act = (id, what, body) => api(`/api/tables/${id}/${what}`, { method: "POST", body: body ? JSON.stringify(body) : undefined }).then(() => setMsg("")).catch((e) => setMsg(e.message));
  return (
    <div>
      <p style={{ color: "#a00" }}>{msg}</p>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {tables.map((t) => (
          <div key={t.id} style={{ background: COLORS[t.state], border: "1px solid #1f3864", padding: 14, width: 250 }}>
            <h3 style={{ margin: 0 }}>Table {t.id}</h3>
            <p style={{ fontWeight: "bold" }}>{LABELS[t.state]}</p>
            {t.state === "OCCUPIED" && <p>Dining time: {mmss(t.dining_seconds)}</p>}
            {(t.state === "VACANT" || t.state === "CLEANING") && <p>Turnover timer: {mmss(t.turnover_seconds)}</p>}
            {t.uncertain && <p style={{ color: "#a00" }}>Warning: system is not sure. Please check the table.</p>}
            {t.state === "VACANT" && <button onClick={() => act(t.id, "cleaning")}>Mark Cleaning</button>}
            {t.state === "CLEANING" && <button onClick={() => act(t.id, "ready")}>Confirm Ready</button>}
            {t.state === "UNCERTAIN" && ["READY", "VACANT", "OCCUPIED"].map((s) => <button key={s} onClick={() => act(t.id, "set", { state: s })} style={{ marginRight: 4 }}>Set {LABELS[s].split(" ")[0]}</button>)}
          </div>
        ))}
      </div>
    </div>
  );
}

function History({ api }) {
  const [rows, setRows] = useState([]);
  useEffect(() => { api("/api/sessions").then(setRows); }, []);
  return (
    <table border="1" cellPadding="6" style={{ borderCollapse: "collapse" }}>
      <thead><tr><th>Table</th><th>Start</th><th>End</th><th>Duration</th></tr></thead>
      <tbody>{rows.map((s, i) => <tr key={i}><td>{s.table_id}</td><td>{clock(s.start)}</td><td>{clock(s.end)}</td><td>{mmss(s.duration)}</td></tr>)}</tbody>
    </table>
  );
}

function Analytics({ api }) {
  const [a, setA] = useState(null);
  useEffect(() => { api("/api/analytics").then(setA); }, []);
  if (!a) return <p>Loading...</p>;
  const util = Object.entries(a.utilisation).map(([k, v]) => ({ table: k, percent: Math.round(v * 100) }));
  const hours = Object.entries(a.sessions_per_hour).map(([k, v]) => ({ hour: k.slice(11), sessions: v }));
  const tv = a.turnover, show = (x) => (x == null ? "n/a" : mmss(x));
  return (
    <div>
      <p>Sessions: <b>{a.session_count}</b> | Average dining time: <b>{show(a.avg_dining_seconds)}</b> | Uncertain share: <b>{Math.round(a.uncertain_share * 100)}%</b></p>
      <p>Turnover: vacant to cleaning <b>{show(tv.vacant_to_cleaning)}</b>, cleaning to ready <b>{show(tv.cleaning_to_ready)}</b>, ready to next seating <b>{show(tv.ready_to_next_seating)}</b></p>
      <h4>Table utilisation (%)</h4>
      <ResponsiveContainer width="100%" height={220}><BarChart data={util}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="table" /><YAxis domain={[0, 100]} /><Tooltip /><Bar dataKey="percent" fill="#1f3864" /></BarChart></ResponsiveContainer>
      <h4>Sessions per hour</h4>
      <ResponsiveContainer width="100%" height={220}><BarChart data={hours}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="hour" /><YAxis allowDecimals={false} /><Tooltip /><Bar dataKey="sessions" fill="#8fa3c4" /></BarChart></ResponsiveContainer>
    </div>
  );
}

function Settings({ api }) {
  const [s, setS] = useState(null), [msg, setMsg] = useState("");
  useEffect(() => { api("/api/settings").then(setS).catch((e) => setMsg(e.message)); }, []);
  if (!s) return <p>{msg || "Loading..."}</p>;
  const save = () => api("/api/settings", { method: "PUT", body: JSON.stringify(s) }).then(() => setMsg("Saved")).catch((e) => setMsg(e.message));
  const purge = () => api("/api/admin/purge", { method: "POST" }).then((r) => setMsg(`Deleted ${r.deleted_sessions} sessions and ${r.deleted_events} events`));
  return (
    <div>
      <p>Camera name: <input value={s.camera_name} onChange={(e) => setS({ ...s, camera_name: e.target.value })} /></p>
      <p>Keep records for (days): <input type="number" min="1" value={s.retention_days} onChange={(e) => setS({ ...s, retention_days: +e.target.value })} /></p>
      <button onClick={save}>Save</button> <button onClick={purge}>Delete records older than this</button>
      <p>{msg}</p>
      <p style={{ color: "#555" }}>Privacy: only status data is stored. No video frames and no faces.</p>
    </div>
  );
}

export default function App() {
  const [auth, setAuth] = useState(null), [tab, setTab] = useState("Tables");
  if (!auth) return <Login onLogin={setAuth} />;
  const api = useApi(auth);
  const tabs = ["Tables", "History", "Analytics", ...(auth.role === "manager" ? ["Settings"] : [])];
  const View = { Tables, History, Analytics, Settings }[tab];
  return (
    <div style={{ fontFamily: "Georgia, serif", padding: 20 }}>
      <h2 style={{ color: "#1f3864" }}>AI Restaurant Intelligence System</h2>
      <p>Logged in as <b>{auth.name}</b> ({auth.role}) <button onClick={() => setAuth(null)}>Log out</button></p>
      <div style={{ marginBottom: 12 }}>{tabs.map((t) => <button key={t} onClick={() => setTab(t)} style={{ marginRight: 6, fontWeight: t === tab ? "bold" : "normal" }}>{t}</button>)}</div>
      <View key={tab} api={api} />
    </div>
  );
}
