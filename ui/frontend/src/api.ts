export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if ((options.method || "GET").toUpperCase() !== "GET") {
    headers.set("X-UI-Request", "1");
  }
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body?.error?.message || body?.detail || body?.error || `HTTP ${response.status}`;
    throw new Error(String(message));
  }
  return body as T;
}
