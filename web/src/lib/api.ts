// Thin wrapper around fetch for the TripAtlas API. Authentication is the session cookie set by /api/auth/login.

export class ApiError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

function errorMessage(data: unknown, fallback: string): string {
	const detail = (data as { detail?: unknown } | null)?.detail;
	if (typeof detail === 'string') return detail;
	// FastAPI validation errors: [{loc, msg}, ...]
	if (Array.isArray(detail)) return detail.map((d) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`).join('; ');
	return fallback;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	const init: RequestInit = { method, credentials: 'same-origin', headers: {} };
	if (body instanceof FormData) init.body = body;
	else if (body !== undefined) {
		(init.headers as Record<string, string>)['Content-Type'] = 'application/json';
		init.body = JSON.stringify(body);
	}
	const res = await fetch(path, init);
	if (res.status === 204) return undefined as T;
	const data = await res.json().catch(() => null);
	if (!res.ok) throw new ApiError(res.status, errorMessage(data, res.statusText));
	return data as T;
}

export const api = {
	get: <T>(path: string) => request<T>('GET', path),
	post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
	put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body ?? {}),
	patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body ?? {}),
	del: <T>(path: string) => request<T>('DELETE', path)
};

export function thumbUrl(assetId: string, size: 'thumbnail' | 'preview' = 'thumbnail'): string {
	return `/api/photos/${assetId}/thumbnail?size=${size}`;
}

export function videoUrl(assetId: string): string {
	return `/api/photos/${assetId}/video`;
}

/** All photo ids of a pin on the "where I've been" map (for the viewer), the given cover first if present. */
export async function pinPhotos(pin: { lat: number; lon: number; kind: string; name: string | null }, cover?: string) {
	const r = await api.get<{ ids: string[] }>(
		`/api/visited/photos?${query({ lat: pin.lat, lon: pin.lon, city: pin.kind === 'photos' ? pin.name : null })}`
	);
	const ids = r.ids.length ? r.ids : cover ? [cover] : [];
	return { ids, index: Math.max(0, cover ? ids.indexOf(cover) : 0) };
}

export function query(params: Record<string, string | number | null | undefined>): string {
	const q = new URLSearchParams();
	for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined) q.set(k, String(v));
	return q.toString();
}
