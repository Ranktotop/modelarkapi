// Reads a model's capability document (SPEC section 13). v2 documents decide
// everything; v1-only documents from older proxies keep the previous rules.
import type { MediaKind, ModelCapabilities } from "./types";

export const MODE_TASKS: Record<string, string> = {
  text: "text_to_video",
  first_frame: "image_to_video",
  first_last: "first_last_frame",
  multimodal: "reference_to_video",
  edit: "edit",
  extend: "extend",
  stitch: "stitch",
};

const PROVIDER_LABELS: Record<string, string> = {
  modelark: "BytePlus ModelArk",
  google: "Google",
  kling: "Kling",
};

const V1_PARAMETERS: Record<string, keyof ModelCapabilities> = {
  seconds: "durations",
  resolution: "resolutions",
  aspect_ratio: "ratios",
  output_format: "output_formats",
};

const V1_DEFAULTS: Record<string, "duration" | "resolution" | "ratio"> = {
  seconds: "duration",
  resolution: "resolution",
  aspect_ratio: "ratio",
};

// The studio keeps "automatic duration" as -1, the v2 document says "auto".
function toUi(value: string | number): string | number {
  return value === "auto" ? -1 : value;
}

export function providerOf(caps: ModelCapabilities | undefined): string {
  return caps?.provider ?? "modelark";
}

export function modeUnavailable(caps: ModelCapabilities | undefined, mode: string): string | null {
  if (!caps) return null;
  if (caps.tasks) {
    return caps.tasks[MODE_TASKS[mode] ?? mode] ? null : "Dieses Modell unterstützt diesen Workflow nicht.";
  }
  const allowed = caps.reference_limits ?? { image: 0, video: 0, audio: 0 };
  if (mode === "first_last" && !caps.supports_last_frame_role) return "Dieses Modell unterstützt kein Endframe.";
  if (mode === "multimodal" && !allowed.image && !allowed.video && !allowed.audio) return "Dieses Modell unterstützt keine Referenzen.";
  if ((mode === "edit" || mode === "extend" || mode === "stitch") && !allowed.video) return "Dieses Modell unterstützt keine Videoreferenzen.";
  return null;
}

function parameterSpec(caps: ModelCapabilities, task: string, name: string) {
  return caps.tasks?.[task]?.parameters?.[name] ?? caps.parameters?.[name];
}

export function parameterValues(caps: ModelCapabilities | undefined, task: string, name: string): (string | number)[] {
  if (!caps) return [];
  if (caps.parameters) return (parameterSpec(caps, task, name)?.values ?? []).map(toUi);
  const v1 = V1_PARAMETERS[name];
  return v1 ? [...((caps[v1] as (string | number)[] | undefined) ?? [])] : [];
}

export function parameterDefault(caps: ModelCapabilities | undefined, task: string, name: string): string | number | undefined {
  if (!caps) return undefined;
  if (caps.parameters) {
    const value = parameterSpec(caps, task, name)?.default;
    return typeof value === "boolean" || value === undefined ? undefined : toUi(value);
  }
  const key = V1_DEFAULTS[name];
  return key ? caps.defaults?.[key] : undefined;
}

export function lockedValue(
  caps: ModelCapabilities | undefined,
  task: string,
  name: string,
): { value: string | number; message: string } | null {
  if (!caps) return null;
  if (caps.constraints) {
    for (const constraint of caps.constraints) {
      const conditions = Object.keys(constraint.if);
      const applies = conditions.length > 0
        && conditions.every(key => key === "task")
        && constraint.if.task.includes(task);
      const values = constraint.then[name];
      if (applies && values?.length === 1) return { value: toUi(values[0]), message: constraint.message };
    }
    return null;
  }
  const taskTypes = caps.task_types ?? [];
  const frameTask = task === "image_to_video" || task === "first_last_frame";
  if (name === "aspect_ratio" && ((frameTask && caps.adaptive_ratio_for_frames) || ((task === "edit" || task === "extend") && taskTypes.includes(task)))) {
    return { value: "adaptive", message: "Das Seitenverhältnis folgt dem Eingabematerial." };
  }
  if (name === "seconds" && task === "edit" && taskTypes.includes("edit")) {
    return { value: -1, message: "Die Dauer folgt dem bearbeiteten Video." };
  }
  return null;
}

export function referenceLimit(caps: ModelCapabilities | undefined, task: string, kind: MediaKind): number {
  if (!caps) return 0;
  if (!caps.tasks) return caps.reference_limits?.[kind] ?? 0;
  const spec = caps.tasks[task];
  if (!spec) return 0;
  let limit = (spec.references ?? [])
    .filter(slot => slot.types.includes(kind))
    .reduce((total, slot) => total + slot.max, 0);
  for (const group of spec.limits ?? []) {
    if (!group.if && group.types.length === 1 && group.types[0] === kind) limit = Math.min(limit, group.max);
  }
  return limit;
}

export function feature(caps: ModelCapabilities | undefined, name: string): boolean {
  if (!caps) return false;
  if (name === "generate_audio") return caps.parameters ? "generate_audio" in caps.parameters : true;
  if (!caps.features) return true;
  return Boolean(caps.features[name]);
}

export function groupModels<T extends { capabilities: ModelCapabilities }>(models: T[]): { provider: string; label: string; models: T[] }[] {
  const order = Object.keys(PROVIDER_LABELS);
  const groups = new Map<string, T[]>();
  for (const model of models) {
    const provider = providerOf(model.capabilities);
    groups.set(provider, [...(groups.get(provider) ?? []), model]);
  }
  return [...groups.entries()]
    .sort(([left], [right]) => (order.indexOf(left) + 1 || 99) - (order.indexOf(right) + 1 || 99))
    .map(([provider, items]) => ({ provider, label: PROVIDER_LABELS[provider] ?? provider, models: items }));
}

// How a finished job is continued: Seedance reuses the last frame, Veo
// extends the video itself. v1 documents only know the last-frame way.
export function continuationOf(caps: ModelCapabilities | undefined): string {
  if (!caps) return "none";
  return caps.continuation ?? "last_frame";
}

export function extendsVideos(caps: ModelCapabilities | undefined): boolean {
  const continuation = continuationOf(caps);
  return continuation === "video_extension" || continuation === "multi_turn";
}

export function rolesFor(caps: ModelCapabilities | undefined, task: string, kind: string): string[] {
  const slots = caps?.tasks?.[task]?.references ?? [];
  return slots.filter(slot => slot.types.includes(kind)).map(slot => slot.role);
}

export function promptRequired(caps: ModelCapabilities | undefined, task: string): boolean {
  const spec = caps?.tasks?.[task];
  if (spec?.prompt_required !== undefined) return spec.prompt_required;
  return caps?.prompt?.required ?? true;
}

export function parameterRange(caps: ModelCapabilities | undefined, task: string, name: string): { min: number; max: number } | null {
  if (!caps?.parameters) return null;
  const spec = parameterSpec(caps, task, name);
  return spec && spec.min !== undefined && spec.max !== undefined ? { min: spec.min, max: spec.max } : null;
}

export function hasParameter(caps: ModelCapabilities | undefined, task: string, name: string): boolean {
  if (!caps) return false;
  if (!caps.parameters) return name in V1_PARAMETERS;
  return Boolean(parameterSpec(caps, task, name));
}

// v2 documents list only what the model can do; v1 documents keep every
// mode visible so the previous "disabled with reason" behaviour stays.
export function availableModes<T extends { id: string }>(caps: ModelCapabilities | undefined, modes: readonly T[]): T[] {
  if (!caps?.tasks) return [...modes];
  return modes.filter(mode => Boolean(caps.tasks?.[MODE_TASKS[mode.id] ?? mode.id]));
}

export type ResultOutput = { index: number; variants?: string[] };

export function resultVariants(outputs: ResultOutput[] | undefined): { output: number; variant: string }[] {
  if (!outputs?.length) return [{ output: 0, variant: "video" }];
  return outputs.flatMap(output => (output.variants ?? ["video"]).map(variant => ({ output: output.index, variant })));
}
