// Base map styles. OpenFreeMap is free, needs no key and does not track users (https://openfreemap.org).
// Self-hosters can point these at their own tile server.
export const MAP_STYLES = [
	{ id: 'liberty', url: 'https://tiles.openfreemap.org/styles/liberty', label: 'style_streets' },
	{ id: 'positron', url: 'https://tiles.openfreemap.org/styles/positron', label: 'style_light' },
	{ id: 'dark', url: 'https://tiles.openfreemap.org/styles/dark', label: 'style_dark' }
] as const;

export type MapStyleId = (typeof MAP_STYLES)[number]['id'];

const KEY = 'tripatlas.mapStyle';

export function preferredStyle(): MapStyleId {
	try {
		const saved = localStorage.getItem(KEY);
		if (saved && MAP_STYLES.some((s) => s.id === saved)) return saved as MapStyleId;
	} catch {
		/* storage unavailable (private mode) */
	}
	return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'liberty';
}

export function rememberStyle(id: MapStyleId) {
	try {
		localStorage.setItem(KEY, id);
	} catch {
		/* ignore */
	}
}

export function styleUrl(id: MapStyleId): string {
	return MAP_STYLES.find((s) => s.id === id)!.url;
}
