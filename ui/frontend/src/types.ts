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

export type ModelCapabilities = {
  resolutions: string[];
  ratios: string[];
  durations: number[];
  defaults: { resolution: string; ratio: string; duration: number };
  reference_limits: Record<MediaKind, number>;
  reference_audio_requires_visual: boolean;
  output_formats: string[];
  task_types: string[];
  supports_frames: boolean;
  supports_last_frame_role: boolean;
  adaptive_ratio_for_frames: boolean;
  reference_media_seconds?: { min: number; max: number; total: number };
};

export type StudioConfig = {
  models: { id: string; label: string; capabilities: ModelCapabilities }[];
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
