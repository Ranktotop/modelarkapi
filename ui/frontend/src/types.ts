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
};

export type StudioConfig = {
  models: { id: string; label: string; capabilities: ModelCapabilities }[];
  job_ttl_seconds: number;
  reference_limits: Record<MediaKind, number>;
};

export type ProviderVideo = {
  id: string;
  status: "queued" | "in_progress" | "completed" | "failed";
  provider_status?: string;
  progress?: number;
  last_frame_available?: boolean;
  error?: { message?: string; code?: string };
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
  request: Record<string, unknown>;
  provider: ProviderVideo;
};
