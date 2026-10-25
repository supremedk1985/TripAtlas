/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />
// Makes TripAtlas installable, lets the app shell open without network, and keeps map tiles, photos and trip data on
// this device up to the size chosen in the settings (see lib/deviceCache/shared.ts for how accounts are kept apart).
import { build, files, version } from '$service-worker';
import {
	ACCOUNT_HEADER,
	allEntries,
	bucketOf,
	cacheName,
	CONFIG_CACHE,
	deleteEntries,
	putEntries,
	readConfig,
	SHARED_BUCKET,
	type DeviceCacheConfig,
	type Entry
} from '$lib/deviceCache/shared';

const sw = self as unknown as ServiceWorkerGlobalScope;
const CACHE = `tripatlas-${version}`;
const ASSETS = [...build, ...files.filter((f) => !f.endsWith('.geojson'))];
const TILE_HOST = 'tiles.openfreemap.org';
const SHELL = '/__shell';

sw.addEventListener('install', (event) => {
	event.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
});

sw.addEventListener('activate', (event) => {
	const keep = (k: string) => k === CACHE || k === CONFIG_CACHE || k.startsWith('tripatlas-store-');
	event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => !keep(k)).map((k) => caches.delete(k)))));
});

sw.addEventListener('fetch', (event) => {
	const req = event.request;
	if (req.method !== 'GET') return;
	const url = new URL(req.url);

	if (url.hostname === TILE_HOST) {
		// tiles, fonts and sprites sit under versioned paths and never change; styles and the tile index do
		const fixed = /\/\d+\/\d+\/\d+\.pbf$|\/fonts\/|\/sprites\//.test(url.pathname);
		event.respondWith(stored(req, SHARED_BUCKET, req.url, fixed ? 'cache-first' : 'network-first'));
		return;
	}
	if (url.origin !== sw.location.origin) return;

	if (url.pathname.startsWith('/api/')) {
		const thumb = url.pathname.match(/^\/api\/photos\/[0-9a-f-]{36}\/thumbnail$/);
		const account = thumb ? url.searchParams.get('u') : req.headers.get(ACCOUNT_HEADER);
		if (!account || !/^\d+$/.test(account) || skipApi(url.pathname)) return;
		const bucket = bucketOf(account);
		// full resolution (zooming in) is several MB per photo: not kept on the device
		if (thumb && url.searchParams.get('size') === 'fullsize') return;
		if (thumb) event.respondWith(photo(req, url, bucket));
		else event.respondWith(stored(req, bucket, req.url, 'network-first'));
		return;
	}
	if (ASSETS.includes(url.pathname)) {
		event.respondWith(caches.match(url.pathname).then((r) => r ?? fetch(req)));
		return;
	}
	// Pages: network first; every page is the same app shell, so the last one fetched opens any page offline.
	if (req.mode === 'navigate') {
		event.respondWith(
			fetch(req)
				.then(async (res) => {
					if (res.ok) await (await caches.open(CACHE)).put(SHELL, res.clone());
					return res;
				})
				.catch(async () => (await caches.match(SHELL)) ?? Response.error())
		);
	}
});

/** Videos are too big, the admin pages need the live state. */
const skipApi = (path: string) =>
	path.endsWith('/video') ||
	path.startsWith('/api/admin') ||
	path.startsWith('/api/settings') ||
	(path.startsWith('/api/setup') && path !== '/api/setup/status');

sw.addEventListener('message', (event) => {
	const msg = event.data as { type: string; bucket?: string };
	const reply = (v: unknown) => event.ports[0]?.postMessage(v);
	if (msg?.type === 'config') event.waitUntil((async () => ((config = null), await evict(), reply(true)))());
	if (msg?.type === 'clear') event.waitUntil(clear(msg.bucket).then(() => reply(true)));
});

// --- storing ---------------------------------------------------------------------------------------------------

let config: DeviceCacheConfig | null = null;
const limitBytes = async () => ((config ??= await readConfig()).limitMb || 0) * 1024 * 1024;

/** A photo: the same id is the same picture forever. Offline, a large preview falls back to a smaller size. */
async function photo(req: Request, url: URL, bucket: string): Promise<Response> {
	try {
		return await stored(req, bucket, req.url, 'cache-first');
	} catch (err) {
		for (const size of ['medium', 'thumbnail']) {
			const alt = new URL(url);
			alt.searchParams.set('size', size);
			const hit = await (await caches.open(cacheName(bucket))).match(alt.href);
			if (hit) return hit;
		}
		throw err;
	}
}

async function stored(req: Request, bucket: string, key: string, how: 'cache-first' | 'network-first'): Promise<Response> {
	const limit = await limitBytes();
	if (!limit) return fetch(req);
	const cache = await caches.open(cacheName(bucket));
	if (how === 'cache-first') {
		const hit = await cache.match(key);
		if (hit) {
			touch(bucket, key);
			return hit;
		}
	}
	try {
		const res = await fetch(req);
		if (res.status === 200 && res.type !== 'opaque') await keep(cache, bucket, key, res.clone(), limit);
		return res;
	} catch (err) {
		// offline: whatever is stored, also for network-first entries
		const hit = await cache.match(key);
		if (hit) {
			touch(bucket, key);
			return hit;
		}
		throw err;
	}
}

// The index lives in IndexedDB; in memory it is a map, written back in batches.
let index: Promise<Map<string, Entry>> | null = null;
let total = 0;
const dirty = new Map<string, Entry>();
let flushTimer: ReturnType<typeof setTimeout> | null = null;

const id = (bucket: string, url: string) => `${bucket} ${url}`;

function loadIndex() {
	index ??= allEntries()
		.catch(() => [])
		.then((list) => {
			total = 0;
			const m = new Map<string, Entry>();
			for (const e of list) {
				m.set(e.url, e);
				total += e.bytes;
			}
			return m;
		});
	return index;
}

function scheduleFlush() {
	flushTimer ??= setTimeout(() => {
		flushTimer = null;
		const list = [...dirty.values()];
		dirty.clear();
		putEntries(list).catch(() => {});
	}, 2000);
}

async function touch(bucket: string, url: string) {
	const e = (await loadIndex()).get(id(bucket, url));
	if (!e) return;
	e.used = Date.now();
	dirty.set(e.url, e);
	scheduleFlush();
}

async function keep(cache: Cache, bucket: string, url: string, res: Response, limit: number) {
	const body = await res.blob();
	if (body.size > limit / 20) return; // one file never pushes out a twentieth of everything
	await cache.put(url, new Response(body, { status: res.status, statusText: res.statusText, headers: res.headers }));
	const m = await loadIndex();
	const key = id(bucket, url);
	total += body.size - (m.get(key)?.bytes ?? 0);
	const e: Entry = { url: key, bucket, bytes: body.size, used: Date.now() };
	m.set(key, e);
	dirty.set(key, e);
	scheduleFlush();
	if (total > limit) await evict();
}

let evicting: Promise<void> | null = null;

/** Removes the entries used longest ago until everything fits into 90 % of the limit (all of it when off). */
function evict(): Promise<void> {
	evicting ??= (async () => {
		const limit = await limitBytes();
		const m = await loadIndex();
		if (total <= limit) return;
		const target = limit * 0.9;
		const gone: Entry[] = [];
		for (const e of [...m.values()].sort((a, b) => a.used - b.used)) {
			if (total <= target) break;
			gone.push(e);
			total -= e.bytes;
			m.delete(e.url);
			dirty.delete(e.url);
		}
		await drop(gone);
	})().finally(() => (evicting = null));
	return evicting;
}

async function drop(gone: Entry[]) {
	const byBucket = new Map<string, Entry[]>();
	for (const e of gone) byBucket.set(e.bucket, [...(byBucket.get(e.bucket) ?? []), e]);
	for (const [bucket, list] of byBucket) {
		const cache = await caches.open(cacheName(bucket));
		await Promise.all(list.map((e) => cache.delete(e.url.slice(bucket.length + 1))));
	}
	await deleteEntries(gone.map((e) => e.url)).catch(() => {});
}

/** One bucket (an account that was forgotten on this device) or everything. */
async function clear(bucket?: string) {
	const m = await loadIndex();
	const gone = [...m.values()].filter((e) => !bucket || e.bucket === bucket);
	for (const e of gone) {
		m.delete(e.url);
		dirty.delete(e.url);
		total -= e.bytes;
	}
	await deleteEntries(gone.map((e) => e.url)).catch(() => {});
	if (bucket) await caches.delete(cacheName(bucket));
	else for (const k of await caches.keys()) if (k.startsWith('tripatlas-store-')) await caches.delete(k);
}
