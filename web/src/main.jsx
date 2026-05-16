import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  Gauge,
  KeyRound,
  Radio,
  Shield,
  Timer,
  Trash2,
  Trophy,
} from 'lucide-react';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin);
const WS_BASE = API_BASE.replace(/^http/, 'ws');

function formatMs(value) {
  if (!value && value !== 0) return '-';
  const minutes = Math.floor(value / 60000);
  const seconds = Math.floor((value % 60000) / 1000);
  const ms = value % 1000;
  return `${minutes}:${String(seconds).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
}

function fmt(value, suffix = '') {
  if (value === null || value === undefined || value === '') return '-';
  return `${value}${suffix}`;
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed with ${response.status}`);
  }
  return response.json();
}

function App() {
  const [view, setView] = useState('public');
  const [publicRaceId, setPublicRaceId] = useState(localStorage.getItem('publicRace') || '');

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">TRC GT7</div>
          <h1>Live Timing Control</h1>
        </div>
        <nav className="nav">
          <button className={view === 'public' ? 'active' : ''} onClick={() => setView('public')}>
            <Trophy size={18} /> Public
          </button>
          <button className={view === 'team' ? 'active' : ''} onClick={() => setView('team')}>
            <Gauge size={18} /> Engineer
          </button>
          <button className={view === 'control' ? 'active' : ''} onClick={() => setView('control')}>
            <Shield size={18} /> Race Control
          </button>
        </nav>
      </header>

      {view === 'public' && <PublicTiming raceId={publicRaceId} setRaceId={setPublicRaceId} />}
      {view === 'team' && <TeamEngineer />}
      {view === 'control' && <RaceControl />}
    </main>
  );
}

function PublicTiming({ raceId, setRaceId }) {
  const [races, setRaces] = useState([]);
  const [standings, setStandings] = useState([]);
  const [trackMap, setTrackMap] = useState(null);
  const [viewerCount, setViewerCount] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [classFilter, setClassFilter] = useState('all');

  useEffect(() => {
    let alive = true;
    api('/api/public/races')
      .then((data) => {
        if (!alive) return;
        setRaces(data);
        const raceExists = data.some((race) => race.race_id === raceId);
        if (!raceId && data.length) {
          setRaceId(data[0].race_id);
          localStorage.setItem('publicRace', data[0].race_id);
        } else if (raceId && !raceExists) {
          setRaceId(data[0]?.race_id || '');
          if (data[0]) localStorage.setItem('publicRace', data[0].race_id);
          else localStorage.removeItem('publicRace');
        }
      })
      .catch((err) => alive && setError(err.message));
    return () => {
      alive = false;
    };
  }, [raceId, setRaceId]);

  useEffect(() => {
    if (!raceId) {
      setStandings([]);
      setTrackMap(null);
      setStatus('idle');
      return undefined;
    }
    let alive = true;
    setStatus('connecting');
    setError('');
    api(`/api/public/races/${raceId}/standings`)
      .then((data) => alive && setStandings(data))
      .catch((err) => alive && setError(err.message));
    api(`/api/public/races/${raceId}/trackmap`)
      .then((data) => alive && setTrackMap(data))
      .catch(() => alive && setTrackMap(null));

    const socket = new WebSocket(`${WS_BASE}/ws/races/${raceId}/public`);
    socket.onopen = () => alive && setStatus('live');
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'standings') {
        setStandings(data.standings);
        setViewerCount(data.viewer_count);
        api(`/api/public/races/${raceId}/trackmap`)
          .then((mapData) => alive && setTrackMap(mapData))
          .catch(() => alive && setTrackMap(null));
      }
    };
    socket.onerror = () => alive && setStatus('reconnecting');
    socket.onclose = () => alive && setStatus('offline');
    return () => {
      alive = false;
      socket.close();
    };
  }, [raceId]);

  const classes = useMemo(() => ['all', ...new Set(standings.map((row) => row.class))], [standings]);
  const visibleRows = classFilter === 'all' ? standings : standings.filter((row) => row.class === classFilter);

  return (
    <section className="workspace">
      <div className="toolbar">
        <label>
          Race Code
          <select value={raceId} onChange={(event) => { setRaceId(event.target.value); localStorage.setItem('publicRace', event.target.value); }}>
            <option value="">Select race</option>
            {races.map((race) => <option key={race.race_id} value={race.race_id}>{race.race_id} - {race.name}</option>)}
          </select>
        </label>
        <label>
          Class
          <select value={classFilter} onChange={(event) => setClassFilter(event.target.value)}>
            {classes.map((item) => (
              <option key={item} value={item}>{item === 'all' ? 'All classes' : item}</option>
            ))}
          </select>
        </label>
        <LiveBadge status={status} />
        <div className="viewerBadge"><Radio size={16} /> {viewerCount ?? '-'} viewers</div>
      </div>
      {error && <p className="notice error">{error}</p>}
      {!races.length && <p className="notice">No races created yet.</p>}
      <TrackMap trackMap={trackMap} />
      <StandingsTable rows={visibleRows} />
    </section>
  );
}

function TrackMap({ trackMap, focusEntryId }) {
  if (!trackMap) return null;
  const width = 1000;
  const height = 560;
  const points = trackMap.points || [];
  const polyline = points.map((point) => `${point.x * width},${height - point.y * height}`).join(' ');
  const visibleCars = focusEntryId ? (trackMap.cars || []).filter((car) => car.entry_id === focusEntryId) : (trackMap.cars || []);

  return (
    <section className="trackMapPanel">
      <div className="trackMapHeader">
        <div>
          <h2>Trackmap</h2>
          <p>
            {trackMap.status === 'active'
              ? `Reference: ${trackMap.source_entry_id} lap ${trackMap.source_lap}`
              : 'Calibrating from the first completed valid lap.'}
          </p>
        </div>
        <StatusPill value={trackMap.status} />
      </div>
      {trackMap.status !== 'active' ? (
        <div className="trackMapEmpty">
          Trackmap starts after the first completed lap.
          {!!trackMap.calibration?.length && (
            <span>{trackMap.calibration.map((item) => `${item.entry_id}: ${item.points} pts`).join(' | ')}</span>
          )}
        </div>
      ) : (
        <svg className="trackMap" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Live trackmap">
          <polyline className="trackLineShadow" points={polyline} />
          <polyline className="trackLine" points={polyline} />
          {visibleCars.map((car) => {
            const x = car.x * width;
            const y = height - car.y * height;
            return (
              <g key={car.entry_id} className={`carMarker ${car.connection_status}`}>
                <circle cx={x} cy={y} r="13" />
                <text x={x} y={y + 4} textAnchor="middle">#{car.car_number}</text>
              </g>
            );
          })}
        </svg>
      )}
    </section>
  );
}

function StandingsTable({ rows }) {
  return (
    <div className="tableFrame">
      <table>
        <thead>
          <tr>
            <th>Pos</th>
            <th>Nr</th>
            <th>Class</th>
            <th>Team</th>
            <th>Driver</th>
            <th>Car</th>
            <th>Laps</th>
            <th>Gap</th>
            <th>Int</th>
            <th>Last</th>
            <th>Best</th>
            <th>Pit</th>
            <th>Penalty</th>
            <th>Status</th>
            <th>Conn</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.entry_id}>
              <td className="pos">P{row.position}</td>
              <td>#{row.car_number}</td>
              <td>{row.class}</td>
              <td className="team">{row.team_name}</td>
              <td>{fmt(row.current_driver)}</td>
              <td>{row.car_model}</td>
              <td>{row.laps}</td>
              <td>{fmt(row.gap_to_leader)}</td>
              <td>{fmt(row.gap_to_ahead)}</td>
              <td>{formatMs(row.last_lap_ms)}</td>
              <td>{formatMs(row.best_lap_ms)}</td>
              <td>{row.pit_stops}</td>
              <td>{row.penalty_seconds ? `+${row.penalty_seconds}s` : '-'}</td>
              <td><StatusPill value={row.status} /></td>
              <td><StatusPill value={row.connection_status} /></td>
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan="15" className="empty">No standings yet.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function TeamEngineer() {
  const [raceCode, setRaceCode] = useState(localStorage.getItem('teamRace') || '');
  const [entryId, setEntryId] = useState(localStorage.getItem('teamEntry') || '');
  const [teamCode, setTeamCode] = useState('');
  const [token, setToken] = useState(localStorage.getItem('teamToken') || '');
  const [state, setState] = useState(null);
  const [error, setError] = useState('');

  async function login(event) {
    event.preventDefault();
    setError('');
    try {
      const data = await api('/api/team/login', {
        method: 'POST',
        body: JSON.stringify({ race_code: raceCode, entry_id: entryId, team_code: teamCode }),
      });
      localStorage.setItem('teamToken', data.session_token);
      localStorage.setItem('teamRace', raceCode);
      localStorage.setItem('teamEntry', entryId);
      setToken(data.session_token);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    if (!token) return undefined;
    let alive = true;
    api('/api/team/me', { token })
      .then((data) => alive && setState(data))
      .catch((err) => alive && setError(err.message));
    const socket = new WebSocket(`${WS_BASE}/ws/races/${raceCode}/team?token=${encodeURIComponent(token)}`);
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'team_state') setState(data.state);
    };
    return () => {
      alive = false;
      socket.close();
    };
  }, [token, raceCode]);

  if (!token) {
    return (
      <section className="workspace narrow">
        <h2>Team Engineer Login</h2>
        <form className="formGrid" onSubmit={login}>
          <label>Race Code<input value={raceCode} onChange={(e) => setRaceCode(e.target.value.toUpperCase())} /></label>
          <label>Entry ID<input value={entryId} onChange={(e) => setEntryId(e.target.value)} /></label>
          <label>Team Code<input value={teamCode} onChange={(e) => setTeamCode(e.target.value)} /></label>
          <button type="submit"><KeyRound size={18} /> Login</button>
        </form>
        {error && <p className="notice error">{error}</p>}
      </section>
    );
  }

  return (
    <section className="workspace">
      <div className="toolbar">
        <button onClick={() => { localStorage.removeItem('teamToken'); setToken(''); setState(null); }}>Logout</button>
        <LiveBadge status={state?.connection_status || 'waiting'} />
      </div>
      {error && <p className="notice error">{error}</p>}
      {state ? <EngineerPanel state={state} /> : <p className="notice">Waiting for telemetry.</p>}
    </section>
  );
}

function formatTelemetryLabel(key) {
  return key
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace('Rpm', 'RPM')
    .replace('Gt7', 'GT7')
    .replace('Mps', 'm/s')
    .replace('Kmh', 'km/h');
}

function formatTelemetryValue(value) {
  if (Array.isArray(value)) return value.map((item) => (typeof item === 'number' ? Number(item.toFixed(3)) : item)).join(', ');
  if (typeof value === 'number') return Number(value.toFixed(3));
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  return fmt(value);
}

function EngineerPanel({ state }) {
  const entry = state.entry;
  const standing = state.standing || {};
  return (
    <div>
      <div className="headlineBand">
        <div>
          <div className="eyebrow">Car #{entry.car_number}</div>
          <h2>{entry.team_name}</h2>
          <p>{entry.car_model} - {entry.class} - {fmt(standing.current_driver)}</p>
        </div>
        <div className="rankBox">P{fmt(standing.position)}</div>
      </div>

      <div className="metricGrid">
        <Metric label="Gap Ahead" value={fmt(standing.gap_to_ahead)} />
        <Metric label="Current Lap" value={fmt(standing.laps)} />
        <Metric label="Last Lap" value={formatMs(standing.last_lap_ms)} />
        <Metric label="Best Lap" value={formatMs(standing.best_lap_ms)} />
        <Metric label="Fuel" value={fmt(state.fuel_liters, ' L')} />
        <Metric label="Fuel / Lap" value={fmt(state.fuel_per_lap, ' L')} />
        <Metric label="Laps Remaining" value={fmt(state.estimated_laps_remaining)} />
        <Metric label="Speed" value={fmt(state.speed_kmh, ' km/h')} />
        <Metric label="Gear" value={fmt(state.gear)} />
        <Metric label="RPM" value={fmt(state.rpm)} />
        <Metric label="Throttle" value={fmt(state.throttle, '%')} />
        <Metric label="Brake" value={fmt(state.brake, '%')} />
        <Metric label="Tyre Compound" value={fmt(state.tire_compound)} />
        <Metric label="Tyre FL" value={fmt(state.tire_temp_fl, ' C')} />
        <Metric label="Tyre FR" value={fmt(state.tire_temp_fr, ' C')} />
        <Metric label="Tyre RL" value={fmt(state.tire_temp_rl, ' C')} />
        <Metric label="Tyre RR" value={fmt(state.tire_temp_rr, ' C')} />
        <Metric label="Stint" value={fmt(state.current_stint_laps, ' laps')} />
        <Metric label="Pit Stops" value={fmt(standing.pit_stops)} />
        <Metric label="Connection" value={fmt(state.connection_status)} />
      </div>

      <TrackMap trackMap={state.trackmap} focusEntryId={entry.entry_id} />

      {state.gt7_telemetry && (
        <>
          <h2>GT7 Telemetry</h2>
          <div className="telemetryGrid">
            {Object.entries(state.gt7_telemetry).map(([key, value]) => (
              <Metric key={key} label={formatTelemetryLabel(key)} value={formatTelemetryValue(value)} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function RaceControl() {
  const [password, setPassword] = useState('');
  const [token, setToken] = useState(localStorage.getItem('raceControlToken') || '');
  const [races, setRaces] = useState([]);
  const [selectedRace, setSelectedRace] = useState(localStorage.getItem('selectedRace') || '');
  const [raceDetail, setRaceDetail] = useState(null);
  const [standings, setStandings] = useState([]);
  const [collectors, setCollectors] = useState([]);
  const [privateStates, setPrivateStates] = useState([]);
  const [log, setLog] = useState([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function login(event) {
    event.preventDefault();
    setError('');
    try {
      const data = await api('/api/race-control/login', {
        method: 'POST',
        body: JSON.stringify({ password }),
      });
      localStorage.setItem('raceControlToken', data.race_control_token);
      setToken(data.race_control_token);
    } catch (err) {
      setError(err.message);
    }
  }

  async function refresh(nextSelectedRace = selectedRace) {
    if (!token) return;
    try {
      setError('');
      const raceList = await api('/api/race-control/races', { token });
      setRaces(raceList);
      if (nextSelectedRace && raceList.some((race) => race.race_id === nextSelectedRace)) {
        const [detail, publicRows, collectorRows, privateRows, logRows] = await Promise.all([
          api(`/api/race-control/races/${nextSelectedRace}`, { token }),
          api(`/api/public/races/${nextSelectedRace}/standings`),
          api(`/api/race-control/races/${nextSelectedRace}/collectors`, { token }),
          api(`/api/race-control/races/${nextSelectedRace}/private`, { token }),
          api(`/api/race-control/races/${nextSelectedRace}/log`, { token }),
        ]);
        setRaceDetail(detail);
        setStandings(publicRows);
        setCollectors(collectorRows);
        setPrivateStates(privateRows);
        setLog(logRows);
      } else {
        setRaceDetail(null);
        setStandings([]);
        setCollectors([]);
        setPrivateStates([]);
        setLog([]);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    refresh();
  }, [token, selectedRace]);

  useEffect(() => {
    if (!token || !selectedRace) return undefined;
    const socket = new WebSocket(`${WS_BASE}/ws/races/${selectedRace}/race-control?token=${encodeURIComponent(token)}`);
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'race_control') {
        setStandings(data.standings);
        setCollectors(data.collectors);
        setPrivateStates(data.private_states);
      }
    };
    return () => socket.close();
  }, [token, selectedRace]);

  if (!token) {
    return (
      <section className="workspace narrow">
        <h2>Race Control</h2>
        <form className="formGrid" onSubmit={login}>
          <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="admin" /></label>
          <button type="submit"><Shield size={18} /> Login</button>
        </form>
        {error && <p className="notice error">{error}</p>}
      </section>
    );
  }

  return (
    <section className="workspace">
      <div className="toolbar">
        <label>
          Race
          <select value={selectedRace} onChange={(e) => { setSelectedRace(e.target.value); localStorage.setItem('selectedRace', e.target.value); }}>
            <option value="">Select race</option>
            {races.map((race) => <option key={race.race_id} value={race.race_id}>{race.race_id} - {race.name}</option>)}
          </select>
        </label>
        <button onClick={() => refresh()}><Activity size={18} /> Refresh</button>
        <button className="secondary" onClick={() => { localStorage.removeItem('raceControlToken'); setToken(''); }}>Logout</button>
      </div>
      {message && <p className="notice good">{message}</p>}
      {error && <p className="notice error">{error}</p>}

      <div className="controlGrid">
        <RaceForm token={token} onDone={(race) => {
          setSelectedRace(race.race_id);
          localStorage.setItem('selectedRace', race.race_id);
          setMessage(`Race created: ${race.race_id}`);
          refresh(race.race_id);
        }} />
        <EntryForm token={token} raceId={selectedRace} onDone={(entry) => { setMessage(`Entry created. Team code for ${entry.entry_id}: ${entry.team_code}`); refresh(); }} />
      </div>

      {raceDetail && (
        <div className="headlineBand compact">
          <div>
            <div className="eyebrow">{raceDetail.race.race_id}</div>
            <h2>{raceDetail.race.name}</h2>
            <p>{raceDetail.race.event_type} - {raceDetail.race.duration_minutes} min - {raceDetail.race.status}</p>
          </div>
          <RaceStatusButtons token={token} raceId={selectedRace} onDone={refresh} />
        </div>
      )}

      <h2>Entries</h2>
      <EntryManagement entries={raceDetail?.entries || []} token={token} onDone={refresh} onMessage={setMessage} />

      <h2>Standings</h2>
      <StandingsTable rows={standings} />

      <h2>Collectors</h2>
      <CollectorTable rows={collectors} />

      <h2>Private Telemetry</h2>
      <PrivateTelemetryTable rows={privateStates} />

      <h2>Race Log</h2>
      <div className="logList">
        {log.map((item) => <div key={item.id}><span>{item.created_at}</span>{item.message}</div>)}
        {!log.length && <p className="empty">No log entries yet.</p>}
      </div>
    </section>
  );
}

function EntryManagement({ entries, token, onDone, onMessage }) {
  if (!entries.length) {
    return <p className="notice">No entries created yet.</p>;
  }

  return (
    <div className="entryList">
      {entries.map((entry) => (
        <EntryRow key={entry.entry_id} entry={entry} token={token} onDone={onDone} onMessage={onMessage} />
      ))}
    </div>
  );
}

function EntryRow({ entry, token, onDone, onMessage }) {
  const [penalty, setPenalty] = useState(entry.penalty_seconds || 0);
  const [status, setStatus] = useState(entry.manual_status || entry.status || 'active');

  async function applyPenalty() {
    await api(`/api/race-control/entries/${entry.entry_id}/penalty`, {
      token,
      method: 'POST',
      body: JSON.stringify({ seconds: Number(penalty), reason: 'Race Control' }),
    });
    onMessage(`Penalty updated for ${entry.entry_id}: +${Number(penalty)}s`);
    onDone();
  }

  async function applyStatus(nextStatus = status) {
    await api(`/api/race-control/entries/${entry.entry_id}/status`, {
      token,
      method: 'POST',
      body: JSON.stringify({ status: nextStatus }),
    });
    onMessage(`Status updated for ${entry.entry_id}: ${nextStatus}`);
    onDone();
  }

  async function deleteEntry() {
    const ok = window.confirm(`Delete #${entry.car_number} ${entry.team_name}? This also removes telemetry sessions for this entry.`);
    if (!ok) return;
    await api(`/api/race-control/entries/${entry.entry_id}`, { token, method: 'DELETE' });
    onMessage(`Entry deleted: ${entry.entry_id}`);
    onDone();
  }

  return (
    <div className="entryRow">
      <div className="entryMain">
        <strong>#{entry.car_number} {entry.team_name}</strong>
        <span>{entry.car_model} - {entry.class}</span>
        <span>{entry.drivers.map((driver) => driver.display_name).join(', ')}</span>
      </div>
      <label>
        Penalty
        <input type="number" min="0" value={penalty} onChange={(e) => setPenalty(e.target.value)} />
      </label>
      <button onClick={applyPenalty}>Set Penalty</button>
      <label>
        Status
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="on_track">On Track</option>
          <option value="in_pit">In Pit</option>
          <option value="stopped">Stopped</option>
          <option value="dnf">DNF</option>
          <option value="retired">Retired</option>
        </select>
      </label>
      <button className="secondary" onClick={() => applyStatus()}>Set Status</button>
      <button className="danger" title="Delete entry" onClick={deleteEntry}><Trash2 size={18} /></button>
    </div>
  );
}

function RaceForm({ token, onDone }) {
  const [form, setForm] = useState({
    race_id: 'TRC8H',
    name: 'TRC 8H Nurburgring',
    track_id: 'nurburgring_24h',
    duration_minutes: 480,
    event_type: 'team',
    drivers_per_team: 2,
    classes: 'GT3 Pro, GT3 Am',
  });

  async function submit(event) {
    event.preventDefault();
    const data = await api('/api/race-control/races', {
      token,
      method: 'POST',
      body: JSON.stringify({ ...form, duration_minutes: Number(form.duration_minutes), drivers_per_team: Number(form.drivers_per_team), classes: form.classes.split(',').map((x) => x.trim()).filter(Boolean) }),
    });
    onDone(data);
  }

  return (
    <form className="panel formGrid" onSubmit={submit}>
      <h2>Create Race</h2>
      <label>Race Code<input value={form.race_id} onChange={(e) => setForm({ ...form, race_id: e.target.value.toUpperCase() })} /></label>
      <label>Name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
      <label>Track<input value={form.track_id} onChange={(e) => setForm({ ...form, track_id: e.target.value })} /></label>
      <label>Duration<input type="number" value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })} /></label>
      <label>Event Type<select value={form.event_type} onChange={(e) => setForm({ ...form, event_type: e.target.value })}><option value="solo">Solo</option><option value="team">Team</option></select></label>
      <label>Drivers / Team<input type="number" value={form.drivers_per_team} onChange={(e) => setForm({ ...form, drivers_per_team: e.target.value })} /></label>
      <label>Classes<input value={form.classes} onChange={(e) => setForm({ ...form, classes: e.target.value })} /></label>
      <button type="submit">Create Race</button>
    </form>
  );
}

function EntryForm({ token, raceId, onDone }) {
  const [form, setForm] = useState({
    car_number: 23,
    team_name: 'HERKA Racing',
    car_model: 'BMW M4 GT3',
    car_class: 'GT3 Pro',
    drivers: 'florian:Florian, veronika:Veronika',
    team_code: '',
  });

  async function submit(event) {
    event.preventDefault();
    const drivers = form.drivers.split(',').map((part) => {
      const [driver_id, display_name] = part.split(':').map((x) => x.trim());
      return { driver_id: driver_id || display_name, display_name: display_name || driver_id };
    });
    const body = {
      car_number: Number(form.car_number),
      team_name: form.team_name,
      car_model: form.car_model,
      class: form.car_class,
      drivers,
      ...(form.team_code ? { team_code: form.team_code } : {}),
    };
    const data = await api(`/api/race-control/races/${raceId}/entries`, { token, method: 'POST', body: JSON.stringify(body) });
    onDone(data);
  }

  return (
    <form className="panel formGrid" onSubmit={submit}>
      <h2>Create Entry</h2>
      <label>Car Number<input type="number" value={form.car_number} onChange={(e) => setForm({ ...form, car_number: e.target.value })} /></label>
      <label>Team Name<input value={form.team_name} onChange={(e) => setForm({ ...form, team_name: e.target.value })} /></label>
      <label>Car Model<input value={form.car_model} onChange={(e) => setForm({ ...form, car_model: e.target.value })} /></label>
      <label>Class<input value={form.car_class} onChange={(e) => setForm({ ...form, car_class: e.target.value })} /></label>
      <label>Drivers<input value={form.drivers} onChange={(e) => setForm({ ...form, drivers: e.target.value })} /></label>
      <label>Team Code<input value={form.team_code} onChange={(e) => setForm({ ...form, team_code: e.target.value })} placeholder="empty = auto" /></label>
      <button type="submit" disabled={!raceId}>Create Entry</button>
    </form>
  );
}

function RaceStatusButtons({ token, raceId, onDone }) {
  async function setStatus(status) {
    await api(`/api/race-control/races/${raceId}/status`, { token, method: 'PATCH', body: JSON.stringify({ status }) });
    onDone();
  }
  return (
    <div className="buttonRow">
      <button onClick={() => setStatus('running')}><Timer size={18} /> Start</button>
      <button onClick={() => setStatus('finished')} className="secondary">Stop</button>
    </div>
  );
}

function CollectorTable({ rows }) {
  return (
    <div className="tableFrame">
      <table>
        <thead><tr><th>Car</th><th>Team</th><th>Driver</th><th>Status</th><th>Version</th><th>Last Seen</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.collector_id}>
              <td>#{row.car_number}</td>
              <td>{row.team_name}</td>
              <td>{row.driver_id}</td>
              <td><StatusPill value={row.status} /></td>
              <td>{row.version}</td>
              <td>{row.last_seen}</td>
            </tr>
          ))}
          {!rows.length && <tr><td colSpan="6" className="empty">No collectors connected.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function PrivateTelemetryTable({ rows }) {
  return (
    <div className="tableFrame">
      <table>
        <thead><tr><th>Car</th><th>Fuel</th><th>Fuel/Lap</th><th>Remain</th><th>Speed</th><th>Gear</th><th>RPM</th><th>Throttle</th><th>Brake</th><th>Tyres</th><th>Temps</th><th>Conn</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.entry.entry_id}>
              <td>#{row.entry.car_number} {row.entry.team_name}</td>
              <td>{fmt(row.fuel_liters, ' L')}</td>
              <td>{fmt(row.fuel_per_lap, ' L')}</td>
              <td>{fmt(row.estimated_laps_remaining)}</td>
              <td>{fmt(row.speed_kmh, ' km/h')}</td>
              <td>{fmt(row.gear)}</td>
              <td>{fmt(row.rpm)}</td>
              <td>{fmt(row.throttle, '%')}</td>
              <td>{fmt(row.brake, '%')}</td>
              <td>{fmt(row.tire_compound)}</td>
              <td>{formatTyres(row)}</td>
              <td><StatusPill value={row.connection_status} /></td>
            </tr>
          ))}
          {!rows.length && <tr><td colSpan="12" className="empty">No private telemetry yet.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function formatTyres(row) {
  const values = [row.tire_temp_fl, row.tire_temp_fr, row.tire_temp_rl, row.tire_temp_rr];
  if (values.every((value) => value === null || value === undefined || value === '')) return '-';
  return `FL ${fmt(row.tire_temp_fl, ' C')} / FR ${fmt(row.tire_temp_fr, ' C')} / RL ${fmt(row.tire_temp_rl, ' C')} / RR ${fmt(row.tire_temp_rr, ' C')}`;
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function LiveBadge({ status }) {
  return <div className={`liveBadge ${status}`}><Radio size={16} /> {status}</div>;
}

function StatusPill({ value }) {
  return <span className={`pill ${String(value || '').toLowerCase().replaceAll('_', '-')}`}>{fmt(value)}</span>;
}

createRoot(document.getElementById('root')).render(<App />);
