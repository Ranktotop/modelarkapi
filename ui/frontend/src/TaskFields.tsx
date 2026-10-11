// Task-specific inputs for the unified API (SPEC sections 6 and 8): shots,
// effects, speech, object selections, commerce texts and provider options.
import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent, ReactNode } from "react";
import { api } from "./api";
import { hasParameter } from "./capabilities";
import type { ModelCapabilities, Reference } from "./types";

export const TASK_MODES = [
  { id: "multi_shot", label: "Multi-Shot", hint: "Mehrere Einstellungen in einem Clip", tooltip: "Teilt das Video in bis zu sechs Einstellungen mit eigenem Prompt und eigener Dauer." },
  { id: "motion_control", label: "Bewegung", hint: "Figur bewegt sich wie im Video", tooltip: "Überträgt die Bewegung aus einem Video auf die Figur aus einem Bild oder Element." },
  { id: "lip_sync", label: "Lip Sync", hint: "Lippen an Ton anpassen", tooltip: "Passt die Lippenbewegung eines Videos an eine Audiodatei oder an gesprochenen Text an." },
  { id: "avatar", label: "Avatar", hint: "Sprechende Figur aus einem Bild", tooltip: "Erzeugt aus einem Bild und Ton oder Text einen sprechenden Avatar." },
  { id: "effect", label: "Effekt", hint: "Effekt-Vorlage anwenden", tooltip: "Wendet eine von über 200 Effekt-Vorlagen auf ein oder zwei Bilder an." },
  { id: "multi_element_edit", label: "Objekte", hint: "Objekte ergänzen, tauschen, entfernen", tooltip: "Markiert Objekte im Video per Klick und ergänzt, tauscht oder entfernt sie." },
  { id: "video_to_audio", label: "Vertonen", hint: "Ton für ein Video", tooltip: "Erzeugt Soundeffekte und Musik passend zu einem vorhandenen Video." },
  { id: "commerce_talking_agent", label: "Sprecher", hint: "Produktvideo mit Sprecher", tooltip: "Ein Avatar spricht dein Skript, optional mit Produktdaten." },
  { id: "commerce_goods_studio", label: "Produktfilm", hint: "Produktvideo aus Bildern", tooltip: "Erzeugt einen 15-, 30- oder 60-sekündigen Produktfilm aus Bildern und Titel." },
  { id: "commerce_apparel", label: "Kleidung", hint: "Outfit in ein Video übertragen", tooltip: "Überträgt Kleidungsstücke in ein Referenzvideo, optional mit Model und Musik." },
] as const;

export type Selection = { frame_index: number; points: { x: number; y: number }[] };

export type TaskExtras = {
  negativePrompt: string;
  n: number;
  shotMode: "customize" | "intelligence";
  shots: { prompt: string; seconds: number }[];
  effect: string;
  speechText: string;
  speechVoice: string;
  speechLanguage: string;
  editMode: "addition" | "swap" | "removal";
  selections: Selection[];
  fps: number;
  bgmPrompt: string;
  asmr: boolean;
  orientation: "image" | "video";
  keepSound: boolean;
  commerce: {
    title: string;
    description: string;
    price: string;
    sellingPoints: string;
    script: string;
    avatarId: string;
    productInfo: string;
    bgm: boolean;
    speechRate: string;
  };
};

export const EMPTY_EXTRAS: TaskExtras = {
  negativePrompt: "",
  n: 1,
  shotMode: "customize",
  shots: [{ prompt: "", seconds: 3 }, { prompt: "", seconds: 2 }],
  effect: "",
  speechText: "",
  speechVoice: "",
  speechLanguage: "en",
  editMode: "swap",
  selections: [],
  fps: 24,
  bgmPrompt: "",
  asmr: false,
  orientation: "image",
  keepSound: true,
  commerce: { title: "", description: "", price: "", sellingPoints: "", script: "", avatarId: "", productInfo: "", bgm: false, speechRate: "" },
};

const AVATARS = ["avatar_eva_female", "avatar_oliver_male", "avatar_elena_female", "avatar_adam_male", "avatar_anna_female", "avatar_rajput_male", "avatar_mia_female", "avatar_river_male", "avatar_marcus_male", "avatar_vivian_female", "avatar_lee_male", "avatar_toto_cartoon"];
const AGENT_VOICES = ["male_calm_informative", "female_clear_rational", "female_gentle_soothing", "female_bright_engaging", "male_crisp_persuasive", "female_intelligent_narrative", "male_clear_professional", "male_energetic_sporty", "female_warm_rich"];
const APPAREL_VOICES = ["energetic_sales_girl", "gentle_sales_woman", "crisp_sales_girl", "mature_sales_woman", "calm_sales_woman", "soft_sales_woman", "energetic_sales_boy", "enthusiastic_sales_man", "steady_sales_man", "calm_sales_man"];

/** Request fields for the chosen task (merged into the unified payload). */
export function taskPayload(task: string, extras: TaskExtras, caps: ModelCapabilities | undefined): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  if (extras.negativePrompt.trim() && hasParameter(caps, task, "negative_prompt")) payload.negative_prompt = extras.negativePrompt.trim();
  if (extras.n > 1) payload.n = extras.n;
  const speech = extras.speechText.trim() ? { text: extras.speechText.trim(), voice: extras.speechVoice, language: extras.speechLanguage } : null;
  const commerce = extras.commerce;
  switch (task) {
    case "multi_shot":
      payload.shot_mode = extras.shotMode;
      if (extras.shotMode === "customize") {
        payload.shots = extras.shots.filter(shot => shot.prompt.trim());
        payload.seconds = extras.shots.reduce((total, shot) => total + (shot.prompt.trim() ? shot.seconds : 0), 0);
      }
      break;
    case "effect":
      payload.effect = extras.effect;
      break;
    case "lip_sync":
    case "avatar":
      if (speech) payload.speech = speech;
      break;
    case "multi_element_edit":
      payload.edit_mode = extras.editMode;
      payload.selections = extras.selections;
      break;
    case "video_to_audio":
      payload.audio = { ...(extras.bgmPrompt.trim() ? { bgm_prompt: extras.bgmPrompt.trim() } : {}), asmr: extras.asmr };
      break;
    case "motion_control":
      payload.provider_options = { kling: { character_orientation: extras.orientation, keep_original_sound: extras.keepSound ? "yes" : "no" } };
      break;
    case "commerce_talking_agent":
      payload.commerce = {
        script: commerce.script,
        ...(commerce.avatarId ? { avatar_id: commerce.avatarId } : {}),
        ...(commerce.title ? { title: commerce.title } : {}),
        ...(commerce.price ? { price: commerce.price } : {}),
        ...(commerce.sellingPoints.trim() ? { selling_points: commerce.sellingPoints.split("\n").map(line => line.trim()).filter(Boolean) } : {}),
        ...(commerce.speechRate ? { speech_rate: Number(commerce.speechRate) } : {}),
        bgm: commerce.bgm,
      };
      if (!commerce.avatarId && extras.speechVoice) payload.speech = { voice: extras.speechVoice };
      break;
    case "commerce_goods_studio":
      payload.commerce = { title: commerce.title, ...(commerce.description ? { description: commerce.description } : {}) };
      break;
    case "commerce_apparel":
      payload.commerce = commerce.productInfo ? { product_info: commerce.productInfo } : {};
      if (extras.speechVoice) payload.speech = { voice: extras.speechVoice };
      break;
  }
  return payload;
}

/** A problem with the task inputs, or null. */
export function taskError(task: string, extras: TaskExtras): string | null {
  if (task === "multi_shot" && extras.shotMode === "customize" && !extras.shots.some(shot => shot.prompt.trim())) return "Beschreibe mindestens einen Shot.";
  if (task === "effect" && !extras.effect) return "Bitte wähle einen Effekt.";
  if (task === "multi_element_edit" && !extras.selections.length) return "Markiere das Objekt mit mindestens einem Klick im Video.";
  if ((task === "lip_sync" || task === "avatar") && extras.speechText.trim() && !extras.speechVoice.trim()) return "Für Sprechtext wird eine TTS-Stimme benötigt.";
  if (task === "commerce_talking_agent" && !extras.commerce.script.trim()) return "Das Sprecher-Skript fehlt.";
  if (task === "commerce_goods_studio" && !extras.commerce.title.trim()) return "Der Produkttitel fehlt.";
  return null;
}

type Effect = { id: string; name: string; images: number };

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="task-field"><span className="setting-label">{label}</span>{children}</label>;
}

function SelectionPicker({ video, extras, update }: { video?: Reference; extras: TaskExtras; update: (next: Partial<TaskExtras>) => void }) {
  const player = useRef<HTMLVideoElement>(null);
  if (!video) return <p className="task-hint">Lade zuerst das Video hoch, in dem du Objekte markieren möchtest.</p>;
  function mark(event: MouseEvent<HTMLVideoElement>) {
    const element = player.current;
    if (!element) return;
    element.pause();
    const box = element.getBoundingClientRect();
    const point = { x: Number(((event.clientX - box.left) / box.width).toFixed(3)), y: Number(((event.clientY - box.top) / box.height).toFixed(3)) };
    const frame = Math.round(element.currentTime * extras.fps);
    const existing = extras.selections.find(selection => selection.frame_index === frame);
    const selections = existing
      ? extras.selections.map(selection => selection === existing ? { ...selection, points: [...selection.points, point].slice(0, 10) } : selection)
      : [...extras.selections, { frame_index: frame, points: [point] }].slice(0, 10);
    update({ selections });
  }
  return <div className="selection-picker">
    <video ref={player} src={video.url} controls muted playsInline onClick={mark} />
    <p className="task-hint">Video anhalten und auf das Objekt klicken. Höchstens 10 Frames mit je 10 Punkten.</p>
    <div className="selection-list">{extras.selections.map(selection => <span key={selection.frame_index}>Frame {selection.frame_index}: {selection.points.length} Punkt(e)</span>)}{extras.selections.length > 0 && <button className="action" onClick={() => update({ selections: [] })}>Auswahl leeren</button>}</div>
    <Field label="Bildrate des Videos"><input type="number" min={1} max={120} value={extras.fps} onChange={event => update({ fps: Number(event.target.value) || 24 })} /></Field>
  </div>;
}

export function TaskFields({ task, caps, extras, onChange, references }: { task: string; caps: ModelCapabilities | undefined; extras: TaskExtras; onChange: (extras: TaskExtras) => void; references: Reference[] }) {
  const [effects, setEffects] = useState<Effect[]>([]);
  const [effectQuery, setEffectQuery] = useState("");
  const update = (next: Partial<TaskExtras>) => onChange({ ...extras, ...next });
  const updateCommerce = (next: Partial<TaskExtras["commerce"]>) => onChange({ ...extras, commerce: { ...extras.commerce, ...next } });
  useEffect(() => {
    if (task !== "effect" || effects.length) return;
    api<{ data: Effect[] }>("/api/kling/effects").then(response => setEffects(response.data)).catch(() => undefined);
  }, [task, effects.length]);
  const filteredEffects = useMemo(() => effects.filter(effect => effect.name.toLowerCase().includes(effectQuery.toLowerCase())).slice(0, 60), [effects, effectQuery]);
  const maxOutputs = caps?.outputs?.max ?? 1;
  const video = references.find(reference => reference.kind === "video");

  return <div className="task-fields">
    {hasParameter(caps, task, "negative_prompt") && <Field label="Negativ-Prompt"><input value={extras.negativePrompt} onChange={event => update({ negativePrompt: event.target.value })} placeholder="Was nicht vorkommen soll" /></Field>}
    {maxOutputs > 1 && <Field label="Varianten"><select value={extras.n} onChange={event => update({ n: Number(event.target.value) })}>{Array.from({ length: maxOutputs }, (_, index) => <option key={index} value={index + 1}>{index + 1}</option>)}</select></Field>}

    {task === "multi_shot" && <div className="task-group">
      <Field label="Shot-Modus"><select value={extras.shotMode} onChange={event => update({ shotMode: event.target.value as TaskExtras["shotMode"] })}><option value="customize">Eigene Shots</option><option value="intelligence">Automatisch aus dem Prompt</option></select></Field>
      {extras.shotMode === "customize" && <>
        {extras.shots.map((shot, index) => <div className="shot-row" key={index}>
          <input value={shot.prompt} placeholder={`Shot ${index + 1}`} onChange={event => update({ shots: extras.shots.map((item, i) => i === index ? { ...item, prompt: event.target.value } : item) })} />
          <input type="number" min={1} max={15} value={shot.seconds} onChange={event => update({ shots: extras.shots.map((item, i) => i === index ? { ...item, seconds: Number(event.target.value) || 1 } : item) })} />
          <button className="action" disabled={extras.shots.length <= 1} onClick={() => update({ shots: extras.shots.filter((_, i) => i !== index) })}>✕</button>
        </div>)}
        {extras.shots.length < 6 && <button className="action" onClick={() => update({ shots: [...extras.shots, { prompt: "", seconds: 2 }] })}>Shot hinzufügen</button>}
        <p className="task-hint">Gesamtdauer: {extras.shots.reduce((total, shot) => total + (shot.prompt.trim() ? shot.seconds : 0), 0)} s</p>
      </>}
    </div>}

    {task === "effect" && <div className="task-group">
      <Field label="Effekt suchen"><input value={effectQuery} onChange={event => setEffectQuery(event.target.value)} placeholder="z. B. hug, birthday, dance" /></Field>
      <div className="effect-grid">{filteredEffects.map(effect => <button key={effect.id} className={`effect-chip ${extras.effect === effect.id ? "active" : ""}`} onClick={() => update({ effect: effect.id })}>{effect.name}<small>{effect.images === 2 ? "2 Bilder" : "1 Bild"}</small></button>)}</div>
    </div>}

    {(task === "lip_sync" || task === "avatar") && <div className="task-group">
      <p className="task-hint">Lade eine Audiodatei hoch oder gib Sprechtext mit einer Kling-TTS-Stimme an (z. B. oversea_male1).</p>
      <Field label="Sprechtext"><textarea rows={3} value={extras.speechText} onChange={event => update({ speechText: event.target.value })} /></Field>
      <div className="task-row">
        <Field label="TTS-Stimme"><input value={extras.speechVoice} onChange={event => update({ speechVoice: event.target.value })} placeholder="oversea_male1" /></Field>
        <Field label="Sprache"><select value={extras.speechLanguage} onChange={event => update({ speechLanguage: event.target.value })}><option value="en">Englisch</option><option value="zh">Chinesisch</option></select></Field>
      </div>
    </div>}

    {task === "multi_element_edit" && <div className="task-group">
      <Field label="Bearbeitung"><select value={extras.editMode} onChange={event => update({ editMode: event.target.value as TaskExtras["editMode"] })}><option value="addition">Objekt hinzufügen (1–2 Bilder)</option><option value="swap">Objekt tauschen (1 Bild)</option><option value="removal">Objekt entfernen</option></select></Field>
      <SelectionPicker video={video} extras={extras} update={update} />
    </div>}

    {task === "video_to_audio" && <div className="task-group">
      <p className="task-hint">Der Prompt beschreibt die Soundeffekte.</p>
      <Field label="Musik"><input value={extras.bgmPrompt} onChange={event => update({ bgmPrompt: event.target.value })} placeholder="z. B. ruhiges Klavier" /></Field>
      <label className="task-check"><input type="checkbox" checked={extras.asmr} onChange={event => update({ asmr: event.target.checked })} /> ASMR-Modus</label>
    </div>}

    {task === "motion_control" && <div className="task-row">
      <Field label="Ausrichtung"><select value={extras.orientation} onChange={event => update({ orientation: event.target.value as TaskExtras["orientation"] })}><option value="image">Wie im Bild (Video bis 10 s)</option><option value="video">Wie im Video (bis 30 s)</option></select></Field>
      <label className="task-check"><input type="checkbox" checked={extras.keepSound} onChange={event => update({ keepSound: event.target.checked })} /> Originalton behalten</label>
    </div>}

    {task === "commerce_talking_agent" && <div className="task-group">
      <p className="task-hint">Markiere ein Bild als „Avatar“ oder wähle einen Preset-Avatar. Weitere Bilder gelten als Produktbilder.</p>
      <div className="task-row">
        <Field label="Preset-Avatar"><select value={extras.commerce.avatarId} onChange={event => updateCommerce({ avatarId: event.target.value })}><option value="">Eigenes Avatar-Bild</option>{AVATARS.map(id => <option key={id} value={id}>{id.replace("avatar_", "")}</option>)}</select></Field>
        {!extras.commerce.avatarId && <Field label="Stimme"><select value={extras.speechVoice} onChange={event => update({ speechVoice: event.target.value })}><option value="">Bitte wählen</option>{AGENT_VOICES.map(id => <option key={id} value={id}>{id}</option>)}</select></Field>}
      </div>
      <Field label="Skript"><textarea rows={4} value={extras.commerce.script} onChange={event => updateCommerce({ script: event.target.value })} /></Field>
      <div className="task-row">
        <Field label="Produkttitel"><input value={extras.commerce.title} onChange={event => updateCommerce({ title: event.target.value })} /></Field>
        <Field label="Preis"><input value={extras.commerce.price} onChange={event => updateCommerce({ price: event.target.value })} /></Field>
      </div>
      <Field label="Verkaufsargumente (eine pro Zeile)"><textarea rows={3} value={extras.commerce.sellingPoints} onChange={event => updateCommerce({ sellingPoints: event.target.value })} /></Field>
      <div className="task-row">
        <Field label="Sprechtempo (ohne Produktdaten)"><select value={extras.commerce.speechRate} onChange={event => updateCommerce({ speechRate: event.target.value })}><option value="">Standard</option><option value="0.8">0.8</option><option value="1.0">1.0</option><option value="1.2">1.2</option></select></Field>
        <label className="task-check"><input type="checkbox" checked={extras.commerce.bgm} onChange={event => updateCommerce({ bgm: event.target.checked })} /> Hintergrundmusik</label>
      </div>
    </div>}

    {task === "commerce_goods_studio" && <div className="task-group">
      <Field label="Produkttitel"><input value={extras.commerce.title} onChange={event => updateCommerce({ title: event.target.value })} /></Field>
      <Field label="Beschreibung"><textarea rows={3} value={extras.commerce.description} onChange={event => updateCommerce({ description: event.target.value })} /></Field>
    </div>}

    {task === "commerce_apparel" && <div className="task-group">
      <p className="task-hint">Das Video ist die Vorlage. Bilder gelten als Produkt, ein als „model“ markiertes Bild als Model, Audio als Hintergrundmusik.</p>
      <Field label="Produktinfo"><textarea rows={2} value={extras.commerce.productInfo} onChange={event => updateCommerce({ productInfo: event.target.value })} /></Field>
      <Field label="Sprecherstimme"><select value={extras.speechVoice} onChange={event => update({ speechVoice: event.target.value })}><option value="">Native Sprache des Modells</option>{APPAREL_VOICES.map(id => <option key={id} value={id}>{id}</option>)}</select></Field>
    </div>}
  </div>;
}
