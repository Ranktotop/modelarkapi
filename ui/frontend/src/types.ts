export type MediaKind = "image" | "video" | "audio";

export type Reference = {
  id: string;
  url: string;
  media_type: string;
  kind: MediaKind;
  filename?: string;
  expires_at: number;
};

export type AssetReference = {
  id: string;
  type: MediaKind;
};

export type StudioConfig = {
  model: string;
  job_ttl_seconds: number;
  resolutions: string[];
  ratios: string[];
  durations: number[];
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
