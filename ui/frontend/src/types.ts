export type MediaKind = "image" | "video" | "audio";

export type Reference = {
  id: string;
  url: string;
  media_type: string;
  kind: MediaKind;
  filename?: string;
  expires_at: number;
  real_human?: boolean;
};

export type ParameterSpec = {
  values?: (string | number)[];
  min?: number;
  max?: number;
  default?: string | number | boolean;
};

export type ReferenceSlot = {
  role: string;
  types: string[];
  min: number;
  max: number;
  max_bytes?: number;
  formats?: string[];
  min_seconds?: number;
  max_seconds?: number;
  total_max_seconds?: number;
};

export type GroupLimit = {
  roles: string[];
  types: string[];
  max: number;
  if?: { has?: string[]; lacks?: string[] };
};

export type TaskSpec = {
  references?: ReferenceSlot[];
  parameters?: Record<string, ParameterSpec>;
  limits?: GroupLimit[];
  prompt_required?: boolean;
};

export type Constraint = {
  if: Record<string, (string | number)[]>;
  then: Record<string, (string | number)[]>;
  message: string;
};

// v1 fields stay for Seedance models; v2 fields (SPEC section 13) describe
// every provider. Everything is optional so old and new proxies both work.
export type ModelCapabilities = {
  resolutions?: string[];
  ratios?: string[];
  durations?: number[];
  defaults?: { resolution: string; ratio: string; duration: number };
  reference_limits?: Record<MediaKind, number>;
  reference_audio_requires_visual?: boolean;
  output_formats?: string[];
  task_types?: string[];
  supports_frames?: boolean;
  supports_last_frame_role?: boolean;
  adaptive_ratio_for_frames?: boolean;
  reference_media_seconds?: { min: number; max: number; total: number };
  schema_version?: number;
  provider?: string;
  backend?: string | null;
  family?: string;
  prompt?: { max_chars?: number | null; required?: boolean };
  outputs?: { max: number; types: string[] };
  parameters?: Record<string, ParameterSpec>;
  tasks?: Record<string, TaskSpec>;
  constraints?: Constraint[];
  continuation?: string;
  features?: Record<string, boolean>;
  provider_options?: string[];
};

export type StudioConfig = {
  models: { id: string; label: string; capabilities: ModelCapabilities; prompt_guide?: string | null }[];
  job_ttl_seconds: number;
};

export type ProviderVideo = {
  id: string;
  status: "queued" | "in_progress" | "completed" | "failed";
  provider_status?: string;
  progress?: number;
  last_frame_available?: boolean;
  error?: { message?: string; code?: string };
};

export type JobReference = {
  url?: string;
  media_type?: string;
  role?: string;
  real_human?: boolean;
};

export type JobUiReference = {
  filename?: string;
  kind?: MediaKind;
  role?: string;
  real_human?: boolean;
};

export type JobRequest = {
  model?: string;
  ui_mode?: string;
  prompt?: string;
  duration?: number;
  resolution?: string;
  ratio?: string;
  output_format?: string;
  omni_reference_task_type?: string;
  generate_audio?: boolean;
  watermark?: boolean;
  return_last_frame?: boolean;
  priority?: number;
  reference_urls?: JobReference[];
  ui_references?: JobUiReference[];
  input_reference_task_id?: string;
  [key: string]: unknown;
};

export type Job = {
  id: string;
  status: string;
  prompt: string;
  model: string;
  mode: string;
  created_at: number;
  updated_at: number;
  terminal_at?: number;
  expires_at?: number;
  request: JobRequest;
  provider: ProviderVideo;
};
