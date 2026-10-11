// Kling elements and voices: pick them for a generation or create new ones
// from the current uploads (SPEC section 16.4, /v1/assets).
import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { rolesFor } from "./capabilities";
import type { ModelCapabilities, Reference } from "./types";

export type AssetRef = { asset_id: string; type: "element" | "voice"; name?: string };
type Asset = { id: string; type: "element" | "voice"; name?: string; status: string };

const TYPE_LABELS = { element: "Elements", voice: "Voices" } as const;

function AssetSection({ type, max, selected, onToggle, references }: {
  type: "element" | "voice";
  max: number;
  selected: AssetRef[];
  onToggle: (asset: Asset) => void;
  references: Reference[];
}) {
  const [scope, setScope] = useState<"custom" | "preset">("custom");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const response = await api<{ data: Asset[] }>(`/api/assets?type=${type}&scope=${scope}`);
      setAssets(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assets konnten nicht geladen werden");
    }
  }, [type, scope]);

  useEffect(() => { void load(); }, [load]);

  const images = references.filter(reference => reference.kind === "image");
  const sound = references.find(reference => reference.kind === "audio" || reference.kind === "video");
  const canCreate = type === "element" ? images.length >= 2 && name && description : Boolean(sound && name);

  async function create() {
    setBusy(true);
    setError("");
    try {
      const body = type === "element"
        ? {
          provider: "kling",
          type,
          name,
          description,
          references: images.map((image, index) => ({ type: "image", url: image.url, ...(index === 0 ? { role: "frontal" } : {}) })),
        }
        : { provider: "kling", type, name, references: [{ type: sound?.kind, url: sound?.url }] };
      await api("/api/assets", { method: "POST", body: JSON.stringify(body) });
      setName("");
      setDescription("");
      setScope("custom");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Asset konnte nicht angelegt werden");
    } finally {
      setBusy(false);
    }
  }

  return <div className="asset-section">
    <div className="label-row"><strong>{TYPE_LABELS[type]}</strong><span>{selected.length}/{max} gewählt</span></div>
    <div className="asset-tabs">
      <button className={`action ${scope === "custom" ? "primary" : ""}`} onClick={() => setScope("custom")}>Eigene</button>
      <button className={`action ${scope === "preset" ? "primary" : ""}`} onClick={() => setScope("preset")}>Kling-Vorlagen</button>
      <button className="action" onClick={() => void load()}>Aktualisieren</button>
    </div>
    {error && <div className="error-message">{error}</div>}
    <div className="asset-grid">
      {assets.map(asset => {
        const active = selected.some(item => item.asset_id === asset.id);
        const ready = asset.status === "ready";
        return <button key={asset.id} className={`effect-chip ${active ? "active" : ""}`} disabled={!ready || (!active && selected.length >= max)} onClick={() => onToggle(asset)} title={asset.id}>
          {asset.name || asset.id}<small>{ready ? (active ? "ausgewählt" : "bereit") : asset.status === "processing" ? "wird erstellt …" : "fehlgeschlagen"}</small>
        </button>;
      })}
      {!assets.length && !error && <p className="task-hint">Keine {TYPE_LABELS[type]} vorhanden.</p>}
    </div>
    <details className="asset-create">
      <summary>Neu anlegen</summary>
      <p className="task-hint">{type === "element"
        ? "Nutzt die hochgeladenen Bilder: das erste als Frontalansicht, die übrigen (1–3) als weitere Ansichten."
        : "Nutzt die erste hochgeladene Audio- oder Videodatei (5–30 s, eine saubere Stimme)."}</p>
      <input value={name} maxLength={20} onChange={event => setName(event.target.value)} placeholder="Name (höchstens 20 Zeichen)" />
      {type === "element" && <input value={description} maxLength={100} onChange={event => setDescription(event.target.value)} placeholder="Beschreibung (höchstens 100 Zeichen)" />}
      <button className="action" disabled={!canCreate || busy} onClick={() => void create()}>{busy ? "Wird angelegt …" : "Anlegen"}</button>
    </details>
  </div>;
}

export function AssetLibrary({ caps, task, selected, onChange, references }: {
  caps: ModelCapabilities | undefined;
  task: string;
  selected: AssetRef[];
  onChange: (assets: AssetRef[]) => void;
  references: Reference[];
}) {
  const types = (["element", "voice"] as const).filter(type => rolesFor(caps, task, type).length > 0);
  if (!types.length) return null;
  const maxFor = (type: string) => (caps?.tasks?.[task]?.references ?? [])
    .filter(slot => slot.types.includes(type))
    .reduce((total, slot) => total + slot.max, 0);

  function toggle(asset: Asset) {
    const exists = selected.some(item => item.asset_id === asset.id);
    onChange(exists
      ? selected.filter(item => item.asset_id !== asset.id)
      : [...selected, { asset_id: asset.id, type: asset.type, name: asset.name }]);
  }

  return <div className="asset-library">
    {types.map(type => <AssetSection
      key={type}
      type={type}
      max={maxFor(type)}
      selected={selected.filter(item => item.type === type)}
      onToggle={toggle}
      references={references}
    />)}
  </div>;
}
