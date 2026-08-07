import { FormEvent, useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { JSX } from "react";
import { api } from "./api";
import { loginBackground, logoWhite } from "./assets";
import type { Job, MediaKind, Reference, StudioConfig } from "./types";

const MODES = [
  { id: "text", label: "Text", hint: "Nur aus einer Beschreibung", tooltip: "Erzeugt ein Video ausschließlich aus deinem Prompt. Es werden keine Referenzdateien an Seedance gesendet." },
  { id: "first_frame", label: "Startbild", hint: "Ein Bild als exakter Anfang", tooltip: "Verwendet genau ein Bild als erstes Frame. Seedance animiert die Szene von diesem festen Ausgangspunkt aus." },
  { id: "first_last", label: "Start + Ende", hint: "Zwei feste Schlüsselbilder", tooltip: "Verwendet das erste Bild als Start- und das zweite als Endframe. Seedance erzeugt den Übergang zwischen beiden Bildern." },
  { id: "multimodal", label: "Referenzen", hint: "Bilder, Videos und Audio kombinieren", tooltip: "Kombiniert Bild-, Video- und Audioreferenzen. Nenne sie im Prompt möglichst eindeutig, zum Beispiel „Bild 1“ oder „Video 1“." },
  { id: "edit", label: "Bearbeiten", hint: "Inhalt oder Stil eines Videos ändern", tooltip: "Bearbeitet ein hochgeladenes Referenzvideo anhand deines Prompts. Mindestens ein Video ist erforderlich." },
  { id: "extend", label: "Verlängern", hint: "Eine Szene weiterführen", tooltip: "Führt ein Referenzvideo zeitlich weiter. Beschreibe im Prompt, wie Handlung und Kamerabewegung fortgesetzt werden sollen." },
  { id: "stitch", label: "Verbinden", hint: "Mehrere Clips zusammenführen", tooltip: "Verbindet mindestens zwei Referenzvideos zu einer neuen Sequenz. Der Prompt beschreibt Reihenfolge und Übergänge." },
] as const;

const TOOLTIPS = {
  model: "Bestimmt die Seedance-Modellvariante. Mit dem Modell ändern sich die verfügbaren Auflösungen, Seitenverhältnisse und Videolängen.",
  workflow: "Legt fest, wie Seedance deinen Prompt und die hochgeladenen Medien interpretiert. Der gewählte Workflow bestimmt außerdem, welche Referenzen erforderlich sind.",
  references: "Referenzen geben Seedance Motive, Stil, Bewegung oder Ton vor. Je nach Workflow gelten unterschiedliche Anzahlen und Medientypen.",
  upload: "Lade Bilder, Videos oder Audio hoch, die Seedance als Eingabe verwenden soll. Die Dateien werden temporär bereitgestellt und später automatisch gelöscht.",
  realHuman: "Aktivieren, wenn auf dieser Referenz eine reale Person erkennbar ist. Die Datei wird dann vor der Generierung automatisch als Real-Human-Asset registriert und verifiziert.",
  prompt: "Beschreibe Motiv, Handlung, Kameraführung, Licht, Stil und Ton möglichst konkret. Verweise bei mehreren Medien auf „Bild 1“, „Video 1“ oder „Audio 1“.",
  duration: "Legt die Länge des erzeugten Videos fest. „Automatisch“ überlässt Seedance die Wahl innerhalb der Grenzen des ausgewählten Modells.",
  resolution: "Bestimmt die Bildauflösung des fertigen Videos. Höhere Auflösungen können mehr Verarbeitungszeit und Kosten verursachen.",
  ratio: "Bestimmt das Seitenverhältnis. 16:9 eignet sich meist für Querformat, 9:16 für Hochformat und „adaptive“ orientiert sich an Prompt oder Referenz.",
  priority: "Steuert die Reihenfolge innerhalb deiner ModelArk-Warteschlange. Höhere Werte werden gegenüber niedrigeren priorisiert; 0 ist der Standard.",
  audio: "Lässt Seedance synchrones Mono-Audio passend zur Szene erzeugen, einschließlich Geräuschen, Sprache oder Musik, wenn der Prompt dies beschreibt.",
  watermark: "Kennzeichnet die Ausgabe mit dem vom Anbieter vorgesehenen AI-Wasserzeichen.",
  lastFrame: "Fordert zusätzlich das letzte Videoframe als PNG an. Damit kannst du das Ergebnis später nahtlos über „Fortsetzen“ weiterführen.",
} as const;

const kindLabel: Record<MediaKind, string> = {
  image: "Bild",
  video: "Video",
  audio: "Audio",
};

const SOCIAL_LINKS = [
  { label: "Website", href: "https://marcmeese.de", short: "WWW" },
  { label: "TikTok", href: "https://link.marcmeese.de/tiktok", short: "TT" },
  { label: "Instagram", href: "https://link.marcmeese.de/instagram", short: "IG" },
  { label: "YouTube", href: "https://link.marcmeese.de/youtube", short: "YT" },
  { label: "Facebook", href: "https://link.marcmeese.de/facebook", short: "FB" },
  { label: "LinkedIn", href: "https://link.marcmeese.de/linkedin", short: "IN" },
] as const;

function Icon({ name }: { name: "spark" | "upload" | "trash" | "download" | "play" | "lock" | "logout" }) {
  const paths: Record<string, JSX.Element> = {
    spark: <><path d="m12 2 1.6 5.4L19 9l-5.4 1.6L12 16l-1.6-5.4L5 9l5.4-1.6L12 2Z"/><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z"/></>,
    upload: <><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/></>,
    trash: <><path d="M4 7h16"/><path d="m9 7 1-3h4l1 3"/><path d="m6 7 1 14h10l1-14"/></>,
    download: <><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></>,
    play: <path d="m8 5 11 7-11 7V5Z"/>,
    lock: <><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></>,
    logout: <><path d="M10 5H5v14h5"/><path d="m14 8 4 4-4 4"/><path d="M18 12H9"/></>,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

function Tooltip({ text }: { text: string }) {
  const id = useId();
  return <span
    className="tooltip"
    tabIndex={0}
    aria-label="Erklärung anzeigen"
    aria-describedby={id}
    onClick={event => event.preventDefault()}
  >
    <span className="tooltip-icon" aria-hidden="true">?</span>
    <span className="tooltip-bubble" id={id} role="tooltip">{text}</span>
  </span>;
}

function SettingLabel({ children, tooltip, htmlFor }: { children: string; tooltip: string; htmlFor?: string }) {
  return <label className="setting-label" htmlFor={htmlFor}>{children}<Tooltip text={tooltip} /></label>;
}

function Login({ onSuccess }: { onSuccess: () => Promise<void> }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/api/login", { method: "POST", body: JSON.stringify({ username, password }) });
      await onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anmeldung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return <main className="login-shell">
    <img className="login-background" src={loginBackground} alt="" />
    <div className="login-overlay" />
    <form className="login-card" onSubmit={submit}>
      <div className="login-accent" />
      <div className="login-brand">
        <img src={logoWhite} alt="Marc Meese" />
        <span />
        <h1>Seedance Studio</h1>
        <p>Melde dich an, um fortzufahren</p>
      </div>
      <div className="login-field"><label htmlFor="username">Benutzername</label><input id="username" autoFocus autoComplete="username" required value={username} onChange={e => setUsername(e.target.value)} /></div>
      <div className="login-field"><label htmlFor="password">Passwort</label><input id="password" autoComplete="current-password" required type="password" value={password} onChange={e => setPassword(e.target.value)} /></div>
      {error && <div className="error-message">{error}</div>}
      <button className="primary-button" disabled={busy}>{busy ? "Anmeldung …" : "Anmelden"}</button>
    </form>
  </main>;
}

function App() {
  const [session, setSession] = useState<{ authenticated: boolean; required: boolean } | null>(null);
  const [config, setConfig] = useState<StudioConfig | null>(null);
  const [initializationError, setInitializationError] = useState("");

  const initialize = useCallback(async () => {
    setInitializationError("");
    try {
      const current = await api<{ authenticated: boolean; required: boolean }>("/api/session");
      setSession(current);
      if (current.authenticated) {
        setConfig(await api<StudioConfig>("/api/config"));
      } else {
        setConfig(null);
      }
    } catch (error) {
      setInitializationError(error instanceof Error ? error.message : "Initialisierung fehlgeschlagen");
    }
  }, []);

  useEffect(() => { void initialize(); }, [initialize]);
  useEffect(() => {
    if (!session?.authenticated || config || !initializationError) return;
    const timer = window.setInterval(() => { void initialize(); }, 60_000);
    return () => window.clearInterval(timer);
  }, [config, initializationError, initialize, session?.authenticated]);
  if (initializationError && (!session || session.authenticated)) {
    return <main className="boot"><div className="boot-error"><h1>ModelArk ist nicht bereit</h1><p>{initializationError}</p><button className="primary-button" onClick={() => void initialize()}>Status neu laden</button></div></main>;
  }
  if (!session) return <div className="boot"><div className="spinner" /></div>;
  if (!session.authenticated) return <Login onSuccess={initialize} />;
  if (!config) return <div className="boot"><div className="spinner" /></div>;
  return <Studio config={config} onLogout={() => setSession({ authenticated: false, required: true })} />;
}

function Studio({ config, onLogout }: { config: StudioConfig; onLogout: () => void }) {
  const [mode, setMode] = useState("text");
  const [model, setModel] = useState("");
  const [prompt, setPrompt] = useState("");
  const [references, setReferences] = useState<Reference[]>([]);
  const [duration, setDuration] = useState(5);
  const [resolution, setResolution] = useState("720p");
  const [ratio, setRatio] = useState("adaptive");
  const [generateAudio, setGenerateAudio] = useState(true);
  const [watermark, setWatermark] = useState(false);
  const [returnLastFrame, setReturnLastFrame] = useState(true);
  const [priority, setPriority] = useState(0);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [continuationTaskId, setContinuationTaskId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const selected = jobs.find(job => job.id === selectedId) || jobs[0];
  const selectedModel = config.models.find(option => option.id === model);
  const capabilities = selectedModel?.capabilities;
  const allKinds = useMemo(() => [
    ...references.map(item => item.kind),
    ...(continuationTaskId ? ["image" as MediaKind] : []),
  ], [references, continuationTaskId]);

  const loadJobs = useCallback(async () => {
    const response = await api<{ data: Job[] }>("/api/videos");
    setJobs(response.data);
    if (!selectedId && response.data[0]) setSelectedId(response.data[0].id);
  }, [selectedId]);

  useEffect(() => {
    loadJobs().catch(() => undefined);
    const timer = window.setInterval(() => loadJobs().catch(() => undefined), 5000);
    return () => window.clearInterval(timer);
  }, [loadJobs]);

  async function uploadFiles(files: FileList | File[]) {
    if (!files.length) return;
    setUploading(true);
    setError("");
    const form = new FormData();
    Array.from(files).forEach(file => form.append("files", file));
    try {
      const response = await api<{ data: Reference[] }>("/api/references", { method: "POST", body: form });
      setReferences(current => [...current, ...response.data]);
      if (mode === "text") setMode("multimodal");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload fehlgeschlagen");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function removeReference(reference: Reference) {
    setReferences(current => current.filter(item => item.id !== reference.id));
    await api(`/api/references/${encodeURIComponent(reference.id)}`, { method: "DELETE" }).catch(() => undefined);
  }

  function toggleRealHuman(referenceId: string) {
    setReferences(current => current.map(item =>
      item.id === referenceId ? { ...item, real_human: !item.real_human } : item
    ));
  }

  function selectModel(modelId: string) {
    setModel(modelId);
    const next = config.models.find(option => option.id === modelId);
    if (!next) return;
    setDuration(next.capabilities.defaults.duration);
    setResolution(next.capabilities.defaults.resolution);
    setRatio(next.capabilities.defaults.ratio);
  }

  function validationError(): string | null {
    if (!model) return "Bitte wähle ein Modell aus.";
    if (!prompt.trim()) return "Bitte beschreibe das gewünschte Video.";
    const count = (kind: MediaKind) => allKinds.filter(value => value === kind).length;
    for (const kind of ["image", "video", "audio"] as MediaKind[]) {
      if (count(kind) > config.reference_limits[kind]) return `Zu viele ${kindLabel[kind]}-Referenzen.`;
    }
    if (mode === "first_frame" && (count("image") !== 1 || allKinds.length !== 1)) return "Der Startbild-Modus benötigt genau ein Bild.";
    if (mode === "first_last" && (count("image") !== 2 || allKinds.length !== 2)) return "Start + Ende benötigt genau zwei Bilder.";
    if (mode === "multimodal" && allKinds.length === 0) return "Füge mindestens eine Referenz hinzu.";
    if ((mode === "edit" || mode === "extend") && count("video") < 1) return "Dieser Modus benötigt mindestens ein Referenzvideo.";
    if (mode === "stitch" && count("video") < 2) return "Zum Verbinden werden mindestens zwei Videos benötigt.";
    if (count("audio") && !count("image") && !count("video")) return "Audio benötigt mindestens ein Bild oder Video.";
    return null;
  }

  function buildPayload() {
    let imageIndex = continuationTaskId ? 1 : 0;
    const roleFor = (kind: MediaKind) => {
      if (mode === "first_frame") return "first_frame";
      if (mode === "first_last" && kind === "image") return imageIndex++ === 0 ? "first_frame" : "last_frame";
      return `reference_${kind}`;
    };
    const includeReferences = mode !== "text";
    return {
      model,
      ui_mode: mode,
      prompt: prompt.trim(),
      duration,
      resolution,
      ratio,
      generate_audio: generateAudio,
      watermark,
      return_last_frame: returnLastFrame,
      priority,
      ...(includeReferences && references.length ? { reference_urls: references.map(item => ({ url: item.url, media_type: item.kind, role: roleFor(item.kind), real_human: Boolean(item.real_human) })) } : {}),
      ...(includeReferences && continuationTaskId ? { input_reference_task_id: continuationTaskId } : {}),
    };
  }

  function requestConfirmation() {
    const invalid = validationError();
    if (invalid) return setError(invalid);
    setError("");
    setConfirming(true);
  }

  async function generate() {
    setConfirming(false);
    setCreating(true);
    try {
      const job = await api<Job>("/api/videos", { method: "POST", body: JSON.stringify(buildPayload()) });
      setJobs(current => [job, ...current.filter(item => item.id !== job.id)]);
      setSelectedId(job.id);
      setPrompt("");
      setContinuationTaskId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generierung fehlgeschlagen");
    } finally {
      setCreating(false);
    }
  }

  async function deleteJob(job: Job) {
    await api(`/api/videos/${encodeURIComponent(job.id)}`, { method: "DELETE" }).catch(() => undefined);
    setJobs(current => current.filter(item => item.id !== job.id));
    if (selectedId === job.id) setSelectedId(null);
  }

  function continueFrom(job: Job) {
    setMode("first_frame");
    setReferences([]);
    setContinuationTaskId(job.id);
    setPrompt("Continue the scene seamlessly from the previous final frame. ");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function logout() {
    await api("/api/session", { method: "DELETE" });
    onLogout();
  }

  return <div className="studio-shell">
    <header className="topbar">
      <div className="brand"><a className="brand-logo" href="https://marcmeese.de" target="_blank" rel="noreferrer" aria-label="Marc Meese Website"><img src={logoWhite} alt="Marc Meese" /></a><div><strong>Seedance Studio</strong><span>ModelArk · Private workspace</span></div></div>
      <div className="topbar-actions"><span className="retention-pill"><i /> Alles wird nach 24 h gelöscht</span><button className="icon-button" onClick={logout} title="Abmelden"><Icon name="logout" /></button></div>
    </header>

    <main className="studio-grid">
      <section className="composer panel">
        <div className="section-heading"><div><p className="eyebrow">NEW GENERATION</p><h1>Bring deine Szene in Bewegung.</h1></div><label className="model-picker"><span className="setting-label">Modell<Tooltip text={TOOLTIPS.model} /></span><select value={model} onChange={event => selectModel(event.target.value)} disabled={!config.models.length}><option value="">{config.models.length ? "Modell auswählen …" : "Keine Modelle verfügbar"}</option>{config.models.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label></div>

        <div className="field-group"><SettingLabel tooltip={TOOLTIPS.workflow}>Workflow</SettingLabel><div className="mode-grid">{MODES.map(item => <button key={item.id} className={`mode-card ${mode === item.id ? "active" : ""}`} data-tooltip={item.tooltip} aria-label={`${item.label}: ${item.tooltip}`} onClick={() => { setMode(item.id); if (item.id !== "first_frame") setContinuationTaskId(null); }}><strong>{item.label}<i className="mode-info" aria-hidden="true">?</i></strong><span>{item.hint}</span></button>)}</div></div>

        {mode !== "text" && <div className="field-group">
          <div className="label-row"><SettingLabel tooltip={TOOLTIPS.references}>Referenzen</SettingLabel><span>{allKinds.length} hinzugefügt</span></div>
          <div className="dropzone" title={TOOLTIPS.upload} role="button" tabIndex={0} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.current?.click(); } }} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); uploadFiles(e.dataTransfer.files); }} onClick={() => fileInput.current?.click()}>
            <input ref={fileInput} hidden multiple type="file" accept="image/png,image/jpeg,image/gif,image/webp,video/mp4,video/quicktime,audio/mpeg,audio/wav" onChange={e => e.target.files && uploadFiles(e.target.files)} />
            <div className="drop-icon"><Icon name="upload" /></div><div><strong>{uploading ? "Dateien werden vorbereitet …" : "Bilder, Videos oder Audio ablegen"}</strong><span>PNG, JPG, WEBP, GIF · MP4, MOV · MP3, WAV</span></div>
          </div>
          {continuationTaskId && <div className="continuation-card"><div className="media-symbol image"><Icon name="play" /></div><div><strong>Letztes Frame aus vorherigem Job</strong><span>{continuationTaskId}</span></div><button onClick={() => setContinuationTaskId(null)}><Icon name="trash" /></button></div>}
          {references.length > 0 && <div className="reference-list">
            {references.map((item, index) => <div className="reference-card" key={item.id}><div className={`media-symbol ${item.kind}`}>{item.kind === "video" ? "▶" : item.kind === "audio" ? "♫" : index + 1}</div><div><strong>{item.filename || `${kindLabel[item.kind]} ${index + 1}`}</strong><span>{kindLabel[item.kind]} · temporärer Upload</span><div className="biometric-row"><label className="biometric-toggle"><input type="checkbox" checked={Boolean(item.real_human)} onChange={() => toggleRealHuman(item.id)}/><span>Reale Person · automatisch verifizieren</span></label><Tooltip text={TOOLTIPS.realHuman} /></div></div><button onClick={() => removeReference(item)} aria-label={`${item.filename || kindLabel[item.kind]} entfernen`} title="Referenz entfernen"><Icon name="trash" /></button></div>)}
          </div>}
        </div>}

        <div className="field-group"><div className="label-row"><SettingLabel htmlFor="prompt" tooltip={TOOLTIPS.prompt}>Prompt</SettingLabel><span>{prompt.length} Zeichen</span></div><textarea id="prompt" value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Beschreibe Motiv, Handlung, Kamera, Licht und gewünschten Ton …" rows={6}/><p className="prompt-tip"><Icon name="spark" /> Dialog am besten in Anführungszeichen setzen, damit Seedance Sprache und Lippenbewegung synchronisiert.</p></div>

        <div className="settings-grid">
          <label><span className="setting-label">Dauer<Tooltip text={TOOLTIPS.duration} /></span><select value={duration} onChange={e => setDuration(Number(e.target.value))} disabled={!capabilities}>{(capabilities?.durations || []).map(value => <option key={value} value={value}>{value === -1 ? "Automatisch" : `${value} Sekunden`}</option>)}</select></label>
          <label><span className="setting-label">Auflösung<Tooltip text={TOOLTIPS.resolution} /></span><select value={resolution} onChange={e => setResolution(e.target.value)} disabled={!capabilities}>{(capabilities?.resolutions || []).map(value => <option key={value}>{value}</option>)}</select></label>
          <label><span className="setting-label">Format<Tooltip text={TOOLTIPS.ratio} /></span><select value={ratio} onChange={e => setRatio(e.target.value)} disabled={!capabilities}>{(capabilities?.ratios || []).map(value => <option key={value}>{value}</option>)}</select></label>
          <label><span className="setting-label">Priorität<Tooltip text={TOOLTIPS.priority} /></span><select value={priority} onChange={e => setPriority(Number(e.target.value))}>{Array.from({ length: 10 }, (_, value) => <option key={value} value={value}>{value}{value === 0 ? " · Standard" : ""}</option>)}</select></label>
        </div>
        <div className="toggle-row"><Toggle label="Synchrones Audio" tooltip={TOOLTIPS.audio} checked={generateAudio} onChange={setGenerateAudio}/><Toggle label="AI-Wasserzeichen" tooltip={TOOLTIPS.watermark} checked={watermark} onChange={setWatermark}/><Toggle label="Letztes Frame behalten" tooltip={TOOLTIPS.lastFrame} checked={returnLastFrame} onChange={setReturnLastFrame}/></div>
        {error && <div className="error-message wide">{error}</div>}
        <div className="generate-bar"><div><span>Geplante Ausgabe</span><strong>{duration === -1 ? "Automatische Dauer" : `${duration}s`} · {resolution} · {ratio} · {generateAudio ? "mit Audio" : "stumm"}</strong></div><button className="generate-button" onClick={requestConfirmation} disabled={creating || uploading}><Icon name="spark" />{creating ? "Task wird erstellt …" : "Video generieren"}</button></div>
      </section>

      <aside className="results panel">
        <div className="results-header"><div><p className="eyebrow">OUTPUT</p><h2>Generierungen</h2></div><span>{jobs.length}</span></div>
        {selected ? <>
          <div className={`preview ${selected.provider.status}`}>
            {selected.provider.status === "completed" ? <video key={selected.id} controls playsInline src={`/api/videos/${encodeURIComponent(selected.id)}/content`} /> : <div className="preview-state"><div className={selected.provider.status === "failed" ? "failed-orb" : "render-orb"}><Icon name={selected.provider.status === "failed" ? "trash" : "spark"}/></div><strong>{statusTitle(selected.provider.status, selected.provider.provider_status)}</strong><span>{selected.provider.error?.message || (selected.provider.provider_status === "asset_processing" ? "BytePlus prüft und registriert deine Real-Human-Referenz." : "Seedance verarbeitet deine Szene.")}</span>{selected.provider.status !== "failed" && <div className="progress-track"><i style={{ width: `${selected.provider.progress || 18}%` }}/></div>}</div>}
          </div>
          <div className="selected-meta"><div><Status status={selected.provider.status}/><span>{new Date(selected.created_at * 1000).toLocaleString("de-DE")}</span></div><p>{selected.prompt}</p><code>{selected.id}</code></div>
          {selected.provider.status === "completed" && <div className="result-actions"><a className="action primary" href={`/api/videos/${encodeURIComponent(selected.id)}/content`} download><Icon name="download" /> MP4 laden</a>{selected.provider.last_frame_available && <><a className="action" href={`/api/videos/${encodeURIComponent(selected.id)}/last-frame`} download><Icon name="download" /> Frame</a><button className="action" onClick={() => continueFrom(selected)}><Icon name="play" /> Fortsetzen</button></>}</div>}
        </> : <div className="empty-state"><div className="empty-visual"><Icon name="play" /></div><strong>Noch kein Video</strong><span>Deine aktuelle Generierung erscheint hier.</span></div>}

        <div className="job-list"><div className="list-title"><span>Letzte 24 Stunden</span><small>automatisch bereinigt</small></div>{jobs.map(job => <button className={`job-row ${selected?.id === job.id ? "active" : ""}`} key={job.id} onClick={() => setSelectedId(job.id)}><div className="job-thumb"><Icon name="play" /></div><div className="job-copy"><strong>{job.prompt || "Ohne Prompt"}</strong><span>{MODES.find(item => item.id === job.mode)?.label || job.mode} · {new Date(job.created_at * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}</span></div><Status status={job.provider.status}/><span className="delete-job" onClick={event => { event.stopPropagation(); deleteJob(job); }}><Icon name="trash" /></span></button>)}</div>
      </aside>
    </main>

    <footer className="site-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <a className="footer-logo" href="https://marcmeese.de" target="_blank" rel="noreferrer"><img src={logoWhite} alt="Marc Meese" /></a>
          <div><strong>Folge mir</strong><span>Für weitere Tools &amp; Automationen rund um KI.</span></div>
        </div>
        <nav className="social-links" aria-label="Social Media">
          {SOCIAL_LINKS.map(link => <a key={link.href} href={link.href} target="_blank" rel="noreferrer"><b>{link.short}</b>{link.label}</a>)}
        </nav>
      </div>
    </footer>

    {confirming && <div className="modal-backdrop" onMouseDown={() => setConfirming(false)}><div className="confirm-modal" onMouseDown={event => event.stopPropagation()}><div className="brand-mark"><Icon name="spark" /></div><p className="eyebrow">READY TO GENERATE</p><h2>Task jetzt starten?</h2><p>Dieser Aufruf kann Kosten bei BytePlus verursachen. Das Ergebnis bleibt nur ungefähr 24 Stunden verfügbar.</p><div className="confirm-specs"><span>{MODES.find(item => item.id === mode)?.label}</span><span>{duration === -1 ? "Automatische Dauer" : `${duration} Sekunden`}</span><span>{resolution}</span><span>{ratio}</span><span>{allKinds.length} Referenzen</span></div><div className="modal-actions"><button className="action" onClick={() => setConfirming(false)}>Zurück</button><button className="generate-button" onClick={generate}><Icon name="spark" /> Kostenpflichtig starten</button></div></div></div>}
  </div>;
}

function Toggle({ label, tooltip, checked, onChange }: { label: string; tooltip: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <div className="toggle-with-tooltip"><button className={`toggle ${checked ? "on" : ""}`} onClick={() => onChange(!checked)} aria-pressed={checked}><i><b /></i><span>{label}</span></button><Tooltip text={tooltip} /></div>;
}

function Status({ status }: { status: string }) {
  const labels: Record<string, string> = { queued: "Wartet", in_progress: "Rendert", completed: "Fertig", failed: "Fehler" };
  return <span className={`status ${status}`}><i />{labels[status] || status}</span>;
}

function statusTitle(status: string, providerStatus?: string) {
  if (providerStatus === "asset_processing") return "Referenz wird verifiziert";
  if (status === "queued") return "In der Warteschlange";
  if (status === "failed") return "Generierung fehlgeschlagen";
  return "Video wird gerendert";
}

export default App;
