// What the page and the service worker both need to know about the storage on this device.
//
// Map tiles are the same for everyone and go into one shared bucket. Photos and trip data belong to an account and go
// into a bucket of their own per account ("u<id>"), so switching accounts on a shared phone keeps every account's
// storage and never shows one account what another one has seen. All buckets together stay below one limit; when it
// is reached the entries used longest ago go first.
//
// The page names the account in each request: image URLs carry `u=<id>` and API calls the header below. The server
// ignores both — it checks access as always; they only pick the bucket on this device.

export const CONFIG_CACHE = 'tripatlas-device-config';
export const CONFIG_URL = '/__device-cache/config';
export const SHARED_BUCKET = 'tiles';
export const ACCOUNT_HEADER = 'X-TripAtlas-Account';
export const LIMITS_MB = [0, 512, 1024, 2048, 5120];
export const DEFAULT_LIMIT_MB = 1024;

export const bucketOf = (account: number | string) => `u${account}`;
export const cacheName = (bucket: string) => `tripatlas-store-${bucket}`;

export interface DeviceCacheConfig {
	limitMb: number;
}

export async function readConfig(): Promise<DeviceCacheConfig> {
	try {
		const r = await (await caches.open(CONFIG_CACHE)).match(CONFIG_URL);
		if (r) {
			const c = await r.json();
			if (typeof c?.limitMb === 'number') return c;
		}
	} catch {
		// storage blocked: fall back to the default
	}
	return { limitMb: DEFAULT_LIMIT_MB };
}

export async function writeConfig(c: DeviceCacheConfig) {
	await (await caches.open(CONFIG_CACHE)).put(CONFIG_URL, new Response(JSON.stringify(c), { headers: { 'Content-Type': 'application/json' } }));
}

// --- the index: url → bucket, size and when it was last used (Cache Storage itself knows neither) ---

export interface Entry {
	url: string;
	bucket: string;
	bytes: number;
	used: number;
}

const DB = 'tripatlas-device-cache';
const STORE = 'entries';

function openDb(): Promise<IDBDatabase> {
	return new Promise((resolve, reject) => {
		const req = indexedDB.open(DB, 1);
		req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'url' });
		req.onsuccess = () => resolve(req.result);
		req.onerror = () => reject(req.error);
	});
}

async function tx<T>(mode: IDBTransactionMode, run: (s: IDBObjectStore) => IDBRequest<T> | void): Promise<T | undefined> {
	const db = await openDb();
	try {
		return await new Promise((resolve, reject) => {
			const t = db.transaction(STORE, mode);
			const req = run(t.objectStore(STORE));
			t.oncomplete = () => resolve(req ? req.result : undefined);
			t.onerror = () => reject(t.error);
			t.onabort = () => reject(t.error);
		});
	} finally {
		db.close();
	}
}

export const allEntries = async () => (await tx<Entry[]>('readonly', (s) => s.getAll())) ?? [];
export const putEntries = (list: Entry[]) => tx('readwrite', (s) => void list.forEach((e) => s.put(e)));
export const deleteEntries = (urls: string[]) => tx('readwrite', (s) => void urls.forEach((u) => s.delete(u)));

/** Bytes per bucket, for the settings page. */
export async function usage(): Promise<{ total: number; buckets: Record<string, number> }> {
	const buckets: Record<string, number> = {};
	let total = 0;
	for (const e of await allEntries().catch(() => [])) {
		buckets[e.bucket] = (buckets[e.bucket] ?? 0) + e.bytes;
		total += e.bytes;
	}
	return { total, buckets };
}
