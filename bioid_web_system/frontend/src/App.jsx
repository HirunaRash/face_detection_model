import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  UserPlus, Activity, Scan, ShieldCheck, Clock,
  User, Briefcase, AlertCircle, CheckCircle2, Camera, RefreshCw
} from 'lucide-react';

const BASE_API = "http://127.0.0.1:8000";

// ─────────────────────────────────────────────────────────────────────────────
// LiveStream — fully self-contained, each mount = fresh HTTP connection
// The `endpoint` prop determines which backend stream is used.
// React unmounts/remounts this when the parent tab switches because the
// parent renders it only inside the correct tab block — so the browser
// automatically drops the old connection and opens a new one.
// ─────────────────────────────────────────────────────────────────────────────
function LiveStream({ endpoint, label }) {
  const [alive, setAlive] = useState(true);
  // ts in the key forces a fresh <img> element (and new HTTP request) on retry
  const [ts, setTs]       = useState(() => Date.now());
  const retry = useCallback(() => { setAlive(true); setTs(Date.now()); }, []);

  return (
    <div className="relative bg-gray-900/60 rounded-2xl overflow-hidden border border-gray-800/80 shadow-2xl">
      {/* status badge */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2
                      bg-black/70 border border-emerald-500/30 text-emerald-400
                      text-xs font-semibold px-3 py-1.5 rounded-full">
        <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
        {label}
      </div>
      {/* refresh button */}
      <button onClick={retry}
        className="absolute top-4 right-4 z-10 bg-black/60 border border-gray-700
                   text-gray-400 hover:text-white p-1.5 rounded-lg transition-colors"
        title="Refresh stream">
        <RefreshCw size={14} />
      </button>

      {alive ? (
        // key={ts} forces React to destroy + recreate the <img> element on retry,
        // opening a brand-new MJPEG connection to the server.
        <img
          key={ts}
          src={`${BASE_API}${endpoint}?t=${ts}`}
          alt="camera feed"
          className="w-full aspect-[4/3] object-cover bg-gray-950"
          onError={() => { setAlive(false); setTimeout(retry, 2500); }}
        />
      ) : (
        <div className="w-full aspect-[4/3] bg-gray-950 flex flex-col items-center
                        justify-center gap-3 text-gray-500">
          <Camera size={32} className="text-gray-700" />
          <p className="text-sm">Reconnecting camera...</p>
          <button onClick={retry} className="text-xs text-emerald-400 hover:underline">
            Retry now
          </button>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// App
// ─────────────────────────────────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab]             = useState('register');
  const [name,  setName]                      = useState('');
  const [title, setTitle]                     = useState('');
  const [alert, setAlert]                     = useState({ type: '', message: '' });
  const [registering, setRegistering]         = useState(false);
  const [captureProgress, setCaptureProgress] = useState(0);
  const [captureTarget,   setCaptureTarget]   = useState(100);
  const [logs, setLogs]                       = useState([]);

  const sseRef      = useRef(null);
  const progressRef = useRef(null);

  // ── SSE: attendance (only open when on tracking tab) ─────────────────────
  useEffect(() => {
    if (activeTab !== 'tracking') {
      sseRef.current?.close(); sseRef.current = null; return;
    }
    if (sseRef.current) return;
    const es = new EventSource(`${BASE_API}/api/attendance/events`);
    sseRef.current = es;
    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        setLogs(prev => [{
          id: Date.now() + Math.random(),
          name:  d.name,
          title: d.title || 'Staff Member',
          time:  d.time,
        }, ...prev]);
      } catch (_) {}
    };
    es.onerror = () => console.warn('[SSE] Attendance stream error.');
    return () => { es.close(); sseRef.current = null; };
  }, [activeTab]);

  // ── SSE: registration capture progress ───────────────────────────────────
  const listenProgress = useCallback(() => {
    progressRef.current?.close();
    const es = new EventSource(`${BASE_API}/api/registration/progress`);
    progressRef.current = es;
    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        setCaptureProgress(d.captured || 0);
        setCaptureTarget(d.target || 100);
        if (d.done || d.error) { es.close(); progressRef.current = null; }
      } catch (_) {}
    };
  }, []);

  // ── Register submit ───────────────────────────────────────────────────────
  const handleRegister = async (e) => {
    e.preventDefault();
    if (!name.trim() || !title.trim()) return;
    setRegistering(true); setCaptureProgress(0);
    setAlert({ type: '', message: '' });
    listenProgress();
    try {
      const res  = await fetch(`${BASE_API}/api/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), title: title.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Registration failed.');
      setAlert({
        type: 'success',
        message: `✓ ${name.trim()} registered with ${data.images_saved} face images! Switch to Live Terminal to test.`,
      });
      setName(''); setTitle('');
    } catch (err) {
      setAlert({ type: 'error', message: err.message });
    } finally {
      setRegistering(false); progressRef.current?.close();
    }
  };

  const pct = Math.min(100, captureTarget > 0
    ? Math.round((captureProgress / captureTarget) * 100) : 0);

  return (
    <div className="min-h-screen bg-[#0b0f19] text-gray-100 flex flex-col font-sans">

      {/* NAV */}
      <nav className="sticky top-0 z-50 bg-gray-900/70 backdrop-blur-xl border-b
                      border-gray-800/80 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-emerald-500 flex items-center
                          justify-center shadow-lg shadow-emerald-500/20">
            <Scan size={20} className="text-black animate-pulse" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-white">BioID Core System</h1>
            <p className="text-xs text-gray-400">Enterprise Live Attendance</p>
          </div>
        </div>
        <div className="flex gap-2 bg-gray-950 p-1 rounded-xl border border-gray-800/60">
          {[
            { id: 'register', label: 'Employee Registration',   icon: <UserPlus size={15}/> },
            { id: 'tracking', label: 'Live Attendance Terminal', icon: <Activity size={15}/> },
          ].map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium
                          transition-all duration-200 ${activeTab === tab.id
                ? 'bg-emerald-500 text-black font-semibold shadow-md'
                : 'text-gray-400 hover:text-white'}`}>
              {tab.icon}{tab.label}
            </button>
          ))}
        </div>
      </nav>

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 flex flex-col justify-center">

        {/* ══════════════════════════════ REGISTER TAB ══════════════════════ */}
        {activeTab === 'register' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            <div className="lg:col-span-7 flex flex-col gap-4">
              {/*
                LiveStream is rendered ONLY inside this tab block.
                When tab switches React unmounts this component entirely,
                which closes the browser's HTTP connection to /api/stream/register.
                When you come back a fresh instance mounts with a new timestamp URL.
              */}
              <LiveStream endpoint="/api/stream/register" label="REGISTRATION MONITOR FEED" />

              {registering && (
                <div className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-4">
                  <div className="flex justify-between text-xs text-gray-400 mb-2">
                    <span className="flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Capturing face samples...
                    </span>
                    <span className="font-mono text-emerald-400">
                      {captureProgress} / {captureTarget}
                    </span>
                  </div>
                  <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 rounded-full transition-all duration-200"
                         style={{ width: `${pct}%` }} />
                  </div>
                  <p className="text-xs text-gray-500 mt-2 text-center">
                    Keep your face centred in the camera frame
                  </p>
                </div>
              )}
            </div>

            <div className="lg:col-span-5 bg-gray-900/60 backdrop-blur-md rounded-2xl p-6
                            flex flex-col gap-6 border border-gray-800/80 shadow-2xl">
              <div>
                <h2 className="text-2xl font-bold text-white tracking-tight">Onboard New Employee</h2>
                <p className="text-sm text-gray-400 mt-1">
                  Fill in the details, then click{' '}
                  <span className="text-emerald-400 font-medium">Execute Profile Creation</span>.
                  The system captures <strong className="text-white">100 face images</strong> automatically.
                </p>
              </div>

              <form onSubmit={handleRegister} className="flex flex-col gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider
                                    text-gray-400 mb-2 flex items-center gap-1.5">
                    <User size={13} className="text-emerald-400" /> Full Legal Name
                  </label>
                  <input type="text" value={name} onChange={e => setName(e.target.value)}
                    required disabled={registering} placeholder="e.g., Hiruna Malshan"
                    className="w-full bg-gray-950 border border-gray-800 rounded-xl px-4 py-3
                               text-sm text-white focus:outline-none focus:border-emerald-500
                               transition-colors placeholder-gray-600 disabled:opacity-50" />
                </div>
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider
                                    text-gray-400 mb-2 flex items-center gap-1.5">
                    <Briefcase size={13} className="text-emerald-400" /> Corporate Designation
                  </label>
                  <input type="text" value={title} onChange={e => setTitle(e.target.value)}
                    required disabled={registering} placeholder="e.g., Lead AI Engineer"
                    className="w-full bg-gray-950 border border-gray-800 rounded-xl px-4 py-3
                               text-sm text-white focus:outline-none focus:border-emerald-500
                               transition-colors placeholder-gray-600 disabled:opacity-50" />
                </div>

                <button type="submit" disabled={registering}
                  className={`w-full font-semibold text-sm py-3.5 px-4 rounded-xl
                              transition-all duration-200 mt-2 flex items-center justify-center
                              gap-2 shadow-lg ${registering
                    ? 'bg-gray-800 text-gray-400 cursor-not-allowed'
                    : 'bg-emerald-500 text-black hover:bg-emerald-400 shadow-emerald-500/10'}`}>
                  {registering ? (
                    <><div className="h-4 w-4 border-2 border-gray-400 border-t-transparent
                                      rounded-full animate-spin" />
                      Capturing faces... {pct}%</>
                  ) : (
                    <><Camera size={16} /> Execute Profile Creation</>
                  )}
                </button>
              </form>

              {alert.type && (
                <div className={`rounded-xl p-4 text-sm font-medium flex items-start gap-3 border ${
                  alert.type === 'success'
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                    : 'bg-red-500/10 border-red-500/20 text-red-400'}`}>
                  {alert.type === 'success'
                    ? <CheckCircle2 size={18} className="shrink-0 mt-0.5" />
                    : <AlertCircle  size={18} className="shrink-0 mt-0.5" />}
                  <span>{alert.message}</span>
                </div>
              )}

              <div className="text-xs text-gray-500 border-t border-gray-800 pt-4 space-y-1">
                <p className="font-semibold text-gray-400 mb-1">How it works</p>
                <p>① Enter name &amp; title → click the button.</p>
                <p>② System captures 100 face photos from the camera.</p>
                <p>③ Photos are uploaded to Supabase Storage.</p>
                <p>④ Switch to Live Terminal — you'll be recognised instantly.</p>
              </div>
            </div>
          </div>
        )}

        {/* ══════════════════════════════ TRACKING TAB ══════════════════════ */}
        {activeTab === 'tracking' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            <div className="lg:col-span-7 flex flex-col gap-2">
              {/*
                Same pattern: rendered ONLY inside this tab block.
                Switching to this tab mounts a fresh LiveStream that opens a
                new connection to /api/stream/live — no stuck frame ever.
              */}
              <LiveStream endpoint="/api/stream/live" label="TERMINAL RECOGNITION ACTIVE" />
              <p className="text-xs text-gray-500 text-center mt-1">
                Registered employees are identified automatically.
                Attendance is logged once every 5 minutes per person.
              </p>
            </div>

            {/* Log panel */}
            <div className="lg:col-span-5 flex flex-col bg-gray-900/60 backdrop-blur-md
                            rounded-2xl border border-gray-800/80 shadow-2xl h-[520px]">
              <div className="p-5 flex items-center justify-between border-b
                              border-gray-800/60 shrink-0">
                <div>
                  <h2 className="text-xl font-bold text-white tracking-tight">Real-Time Access Log</h2>
                  <p className="text-xs text-gray-400 mt-0.5">Updates instantly when a face is recognised.</p>
                </div>
                <div className="flex items-center gap-2">
                  {logs.length > 0 && (
                    <button onClick={() => setLogs([])}
                      className="text-xs text-gray-500 hover:text-red-400 transition-colors
                                 px-2 py-1 rounded-lg border border-gray-800 hover:border-red-900">
                      Clear
                    </button>
                  )}
                  <span className="px-2.5 py-1 text-[10px] uppercase font-bold tracking-widest
                                   text-emerald-400 bg-emerald-500/10 rounded-md border
                                   border-emerald-500/20 flex items-center gap-1">
                    <ShieldCheck size={11} /> Live
                  </span>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3 scrollbar-none">
                {logs.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center
                                  gap-3 text-gray-500 text-sm">
                    <Clock size={28} className="text-gray-700 animate-pulse" />
                    <p>Waiting for face recognition...</p>
                    <p className="text-xs text-gray-600 text-center px-4">
                      Stand in front of the camera. Registered employees will appear here automatically.
                    </p>
                  </div>
                ) : (
                  logs.map(log => (
                    <div key={log.id}
                      className="flex items-center justify-between p-3.5 bg-gray-950/50
                                 border border-gray-800/60 rounded-xl hover:border-emerald-500/20
                                 transition-all duration-300">
                      <div className="flex items-center gap-3">
                        <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border
                                        border-emerald-500/20 flex items-center justify-center
                                        font-bold text-emerald-400 text-sm uppercase shrink-0">
                          {log.name.charAt(0)}
                        </div>
                        <div>
                          <h4 className="text-sm font-semibold text-white">{log.name}</h4>
                          <p className="text-[11px] text-gray-400">{log.title}</p>
                        </div>
                      </div>
                      <span className="text-xs font-mono font-medium text-emerald-400
                                       bg-emerald-950/80 border border-emerald-900/60
                                       px-2.5 py-1 rounded-md shadow-inner shrink-0">
                        {log.time}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}