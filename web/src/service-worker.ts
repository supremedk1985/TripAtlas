/// <reference types="@sveltejs/kit" />
/// <reference no-default-lib="true"/>
/// <reference lib="esnext" />
/// <reference lib="webworker" />
// Makes TripAtlas installable and lets the app shell open without network.
// API responses (positions, photos) are deliberately NOT cached: they are private and must reflect access rights.
import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;
const CACHE = `tripatlas-${version}`;
const ASSETS = [...build, ...files.filter((f) => !f.endsWith('.geojson'))];

sw.addEventListener('install', (event) => {
	event.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
	);
});

sw.addEventListener('fetch', (event) => {
	const url = new URL(event.request.url);
	if (event.request.method !== 'GET' || url.origin !== sw.location.origin || url.pathname.startsWith('/api/')) return;
	if (ASSETS.includes(url.pathname)) {
		event.respondWith(caches.match(url.pathname).then((r) => r ?? fetch(event.request)));
		return;
	}
	// Pages: network first, the cached shell when offline.
	if (event.request.mode === 'navigate') {
		event.respondWith(fetch(event.request).catch(async () => (await caches.match('/')) ?? Response.error()));
	}
});
