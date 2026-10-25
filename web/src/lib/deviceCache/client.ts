// The page's side of the storage on this device (see shared.ts): which account is signed in, the size limit, and
// saving a whole trip ahead of a journey without network.
import {
	ACCOUNT_HEADER,
	bucketOf,
	readConfig,
	SHARED_BUCKET,
	usage,
	writeConfig
} from './shared';

export { LIMITS_MB, SHARED_BUCKET } from './shared';

const LAST = 'tripatlas.account';
let account: number | null = (() => {
	try {
		const v = Number(localStorage.getItem(LAST));
		return Number.isInteger(v) && v > 0 ? v : null;
	} catch {
		return null;
	}
})();

/** The account whose bucket requests go to. Kept across reloads so trip data opens offline too. */
export const currentAccount = () => account;

export function setAccount(id: number | null) {
	account = id;
	try {
		if (id) localStorage.setItem(LAST, String(id));
		else localStorage.removeItem(LAST);
	} catch {
		// storage blocked: only the offline start is lost
	}
}

const supported = () => typeof caches !== 'undefined' && 'serviceWorker' in navigator;

async function tell(msg: object) {
	const reg = await navigator.serviceWorker?.ready;
	if (!reg?.active) return;
	await new Promise((resolve) => {
		const ch = new MessageChannel();
		ch.port1.onmessage = () => resolve(true);
		reg.active!.postMessage(msg, [ch.port2]);
		setTimeout(resolve, 5000);
	});
}

export async function getLimitMb() {
	return supported() ? (await readConfig()).limitMb : 0;
}

export async function setLimitMb(limitMb: number) {
	await writeConfig({ limitMb });
	// keep the browser from clearing it when space gets short
	if (limitMb) await navigator.storage?.persist?.().catch(() => false);
	await tell({ type: 'config' });
}

export async function storageUsage() {
	if (!supported()) return { total: 0, mine: 0, tiles: 0 };
	const u = await usage();
	return { total: u.total, mine: account ? (u.buckets[bucketOf(account)] ?? 0) : 0, tiles: u.buckets[SHARED_BUCKET] ?? 0 };
}

export const clearStorage = () => tell({ type: 'clear' });
/** An account removed from this device takes its photos and trip data with it. */
export const clearAccountStorage = (id: number) => tell({ type: 'clear', bucket: bucketOf(id) });

// --- a whole trip, before going somewhere without network ---

const lon2x = (lon: number, z: number) => Math.floor(((lon + 180) / 360) * 2 ** z);
const lat2y = (lat: number, z: number) => {
	const r = (Math.max(-85, Math.min(85, lat)) * Math.PI) / 180;
	return Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * 2 ** z);
};

/** Tile addresses for the area, from coarse to fine, as long as the number stays reasonable. */
async function tileUrls(styleUrl: string, bounds: [number, number, number, number], max = 2500): Promise<string[]> {
	const style = await (await fetch(styleUrl)).json();
	const out: string[] = [];
	for (const src of Object.values(style.sources ?? {}) as { type: string; url?: string; tiles?: string[] }[]) {
		if (src.type !== 'vector') continue;
		const tj = src.tiles ? src : await (await fetch(src.url!)).json();
		const template: string = tj.tiles[0];
		const [w, s, e, n] = bounds;
		for (let z = 0; z <= (tj.maxzoom ?? 14); z++) {
			const [x0, x1, y0, y1] = [lon2x(w, z), lon2x(e, z), lat2y(n, z), lat2y(s, z)];
			const count = (x1 - x0 + 1) * (y1 - y0 + 1);
			if (out.length + count > max) break;
			for (let x = x0; x <= x1; x++)
				for (let y = y0; y <= y1; y++) out.push(template.replace('{z}', String(z)).replace('{x}', String(x)).replace('{y}', String(y)));
		}
	}
	return out;
}

/** Fetches through the service worker, which keeps everything. Reports progress 0…1. */
export async function saveOffline(
	opts: { styleUrl: string; bounds: [number, number, number, number]; photoUrls: string[]; apiUrls: string[] },
	progress: (done: number, total: number) => void
): Promise<{ failed: number }> {
	const urls = [...opts.apiUrls, ...opts.photoUrls, ...(await tileUrls(opts.styleUrl, opts.bounds))];
	let done = 0;
	let failed = 0;
	const queue = [...urls];
	const headers: Record<string, string> = account ? { [ACCOUNT_HEADER]: String(account) } : {};
	async function worker() {
		for (let u = queue.shift(); u; u = queue.shift()) {
			try {
				const r = await fetch(u, { credentials: 'same-origin', headers: u.startsWith('/api/') ? headers : {} });
				if (!r.ok) failed++;
				await r.arrayBuffer();
			} catch {
				failed++;
			}
			progress(++done, urls.length);
		}
	}
	await Promise.all(Array.from({ length: 6 }, worker));
	return { failed };
}
