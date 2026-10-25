// Thin wrapper around fetch for the TripAtlas API. Authentication is the session cookie set by /api/auth/login.
import { currentAccount } from '$lib/deviceCache/client';
import { ACCOUNT_HEADER } from '$lib/deviceCache/shared';

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

/** Human-readable message of anything thrown (no "Error: " prefix). */
export function errorText(e: unknown): string {
	return e instanceof Error ? e.message : String(e);
}

// Called when the server says the session is gone (expired, signed out elsewhere) — the root layout sends the
// user to the sign-in page instead of leaving a page full of errors.
let unauthorized: (() => void) | null = null;
export function onUnauthorized(handler: () => void) {
	unauthorized = handler;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	const init: RequestInit = { method, credentials: 'same-origin', headers: {} };
	const who = currentAccount();
	if (who) (init.headers as Record<string, string>)[ACCOUNT_HEADER] = String(who);
	if (body instanceof FormData) init.body = body;
	else if (body instanceof Blob) {
		(init.headers as Record<string, string>)['Content-Type'] = body.type;
		init.body = body;
	}
	else if (body !== undefined) {
		(init.headers as Record<string, string>)['Content-Type'] = 'application/json';
		init.body = JSON.stringify(body);
	}
	const res = await fetch(path, init);
	if (res.status === 204) return undefined as T;
	const data = await res.json().catch(() => null);
	if (res.status === 401 && !path.startsWith('/api/auth/') && !path.startsWith('/api/setup/')) unauthorized?.();
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

export function thumbUrl(assetId: string, size: 'thumbnail' | 'medium' | 'preview' | 'fullsize' = 'thumbnail'): string {
	// `u` only picks this account's storage on the device (lib/deviceCache); the server checks access as always
	const who = currentAccount();
	return `/api/photos/${assetId}/thumbnail?size=${size}${who ? `&u=${who}` : ''}`;
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
