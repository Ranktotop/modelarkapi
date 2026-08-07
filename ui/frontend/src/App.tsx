import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { JSX } from "react";
import { api } from "./api";
import { loginBackground, logoWhite } from "./assets";
import type { AssetReference, Job, MediaKind, Reference, StudioConfig } from "./types";

const MODES = [
  { id: "text", label: "Text", hint: "Nur aus einer Beschreibung" },
  { id: "first_frame", label: "Startbild", hint: "Ein Bild als exakter Anfang" },
  { id: "first_last", label: "Start + Ende", hint: "Zwei feste Schlüsselbilder" },
  { id: "multimodal", label: "Referenzen", hint: "Bilder, Videos und Audio kombinieren" },
  { id: "edit", label: "Bearbeiten", hint: "Inhalt oder Stil eines Videos ändern" },
  { id: "extend", label: "Verlängern", hint: "Eine Szene weiterführen" },
  { id: "stitch", label: "Verbinden", hint: "Mehrere Clips zusammenführen" },
] as const;

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

function Icon({ name }: { name: "spark" | "upload" | "trash" | "download" | "play" | "lock" | "logout" | "plus" }) {
  const paths: Record<string, JSX.Element> = {
    spark: <><path d="m12 2 1.6 5.4L19 9l-5.4 1.6L12 16l-1.6-5.4L5 9l5.4-1.6L12 2Z"/><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z"/></>,
    upload: <><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/></>,
    trash: <><path d="M4 7h16"/><path d="m9 7 1-3h4l1 3"/><path d="m6 7 1 14h10l1-14"/></>,
    download: <><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></>,
    play: <path d="m8 5 11 7-11 7V5Z"/>,
    lock: <><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></>,
    logout: <><path d="M10 5H5v14h5"/><path d="m14 8 4 4-4 4"/><path d="M18 12H9"/></>,
    plus: <><path d="M12 5v14"/><path d="M5 12h14"/></>,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
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
  const [assets, setAssets] = useState<AssetReference[]>([]);
  const [assetId, setAssetId] = useState("");
  const [assetType, setAssetType] = useState<MediaKind>("image");
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
    ...assets.map(item => item.type),
    ...(continuationTaskId ? ["image" as MediaKind] : []),
  ], [references, assets, continuationTaskId]);

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

  function addAsset() {
    const id = assetId.trim().replace(/^asset:\/\//, "");
    if (!id.startsWith("asset-")) return setError("Asset-IDs müssen mit asset- beginnen.");
    setAssets(current => [...current, { id, type: assetType }]);
    setAssetId("");
    if (mode === "text") setMode("multimodal");
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
      ...(includeReferences && assets.length ? { reference_assets: assets.map(item => ({ id: item.id, type: item.type, role: roleFor(item.type) })) } : {}),
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
    setAssets([]);
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
        <div className="section-heading"><div><p className="eyebrow">NEW GENERATION</p><h1>Bring deine Szene in Bewegung.</h1></div><label className="model-picker"><span>Modell</span><select value={model} onChange={event => selectModel(event.target.value)} disabled={!config.models.length}><option value="">{config.models.length ? "Modell auswählen …" : "Keine Modelle verfügbar"}</option>{config.models.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label></div>

        <div className="field-group"><label>Workflow</label><div className="mode-grid">{MODES.map(item => <button key={item.id} className={`mode-card ${mode === item.id ? "active" : ""}`} onClick={() => { setMode(item.id); if (item.id !== "first_frame") setContinuationTaskId(null); }}><strong>{item.label}</strong><span>{item.hint}</span></button>)}</div></div>

        {mode !== "text" && <div className="field-group">
          <div className="label-row"><label>Referenzen</label><span>{allKinds.length} hinzugefügt</span></div>
          <div className="dropzone" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); uploadFiles(e.dataTransfer.files); }} onClick={() => fileInput.current?.click()}>
            <input ref={fileInput} hidden multiple type="file" accept="image/png,image/jpeg,image/gif,image/webp,video/mp4,video/quicktime,audio/mpeg,audio/wav" onChange={e => e.target.files && uploadFiles(e.target.files)} />
            <div className="drop-icon"><Icon name="upload" /></div><div><strong>{uploading ? "Dateien werden vorbereitet …" : "Bilder, Videos oder Audio ablegen"}</strong><span>PNG, JPG, WEBP, GIF · MP4, MOV · MP3, WAV</span></div>
          </div>
          {continuationTaskId && <div className="continuation-card"><div className="media-symbol image"><Icon name="play" /></div><div><strong>Letztes Frame aus vorherigem Job</strong><span>{continuationTaskId}</span></div><button onClick={() => setContinuationTaskId(null)}><Icon name="trash" /></button></div>}
          {(references.length > 0 || assets.length > 0) && <div className="reference-list">
            {references.map((item, index) => <div className="reference-card" key={item.id}><div className={`media-symbol ${item.kind}`}>{item.kind === "video" ? "▶" : item.kind === "audio" ? "♫" : index + 1}</div><div><strong>{item.filename || `${kindLabel[item.kind]} ${index + 1}`}</strong><span>{kindLabel[item.kind]} · temporärer Upload</span><label className="biometric-toggle"><input type="checkbox" checked={Boolean(item.real_human)} onChange={() => toggleRealHuman(item.id)}/><span>Reale Person · automatisch verifizieren</span></label></div><button onClick={() => removeReference(item)}><Icon name="trash" /></button></div>)}
            {assets.map((item, index) => <div className="reference-card asset" key={`${item.id}-${index}`}><div className={`media-symbol ${item.type}`}>A</div><div><strong>{item.id}</strong><span>{kindLabel[item.type]} · verifiziertes Asset</span></div><button onClick={() => setAssets(current => current.filter((_, itemIndex) => itemIndex !== index))}><Icon name="trash" /></button></div>)}
          </div>}
          <div className="asset-adder"><input value={assetId} onChange={e => setAssetId(e.target.value)} placeholder="Real-Human Asset-ID (asset-…)"/><select value={assetType} onChange={e => setAssetType(e.target.value as MediaKind)}><option value="image">Bild</option><option value="video">Video</option><option value="audio">Audio</option></select><button onClick={addAsset}><Icon name="plus" /> Asset</button></div>
        </div>}

        <div className="field-group"><div className="label-row"><label htmlFor="prompt">Prompt</label><span>{prompt.length} Zeichen</span></div><textarea id="prompt" value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Beschreibe Motiv, Handlung, Kamera, Licht und gewünschten Ton …" rows={6}/><p className="prompt-tip"><Icon name="spark" /> Dialog am besten in Anführungszeichen setzen, damit Seedance Sprache und Lippenbewegung synchronisiert.</p></div>

        <div className="settings-grid">
          <label><span>Dauer</span><select value={duration} onChange={e => setDuration(Number(e.target.value))} disabled={!capabilities}>{(capabilities?.durations || []).map(value => <option key={value} value={value}>{value === -1 ? "Automatisch" : `${value} Sekunden`}</option>)}</select></label>
          <label><span>Auflösung</span><select value={resolution} onChange={e => setResolution(e.target.value)} disabled={!capabilities}>{(capabilities?.resolutions || []).map(value => <option key={value}>{value}</option>)}</select></label>
          <label><span>Format</span><select value={ratio} onChange={e => setRatio(e.target.value)} disabled={!capabilities}>{(capabilities?.ratios || []).map(value => <option key={value}>{value}</option>)}</select></label>
          <label><span>Priorität</span><select value={priority} onChange={e => setPriority(Number(e.target.value))}>{Array.from({ length: 10 }, (_, value) => <option key={value} value={value}>{value}{value === 0 ? " · Standard" : ""}</option>)}</select></label>
        </div>
        <div className="toggle-row"><Toggle label="Synchrones Audio" checked={generateAudio} onChange={setGenerateAudio}/><Toggle label="AI-Wasserzeichen" checked={watermark} onChange={setWatermark}/><Toggle label="Letztes Frame behalten" checked={returnLastFrame} onChange={setReturnLastFrame}/></div>
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

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <button className={`toggle ${checked ? "on" : ""}`} onClick={() => onChange(!checked)}><i><b /></i><span>{label}</span></button>;
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
