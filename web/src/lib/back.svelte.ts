// "Back" closes what is open on top — the photo viewer, a menu, a dialog, full screen — before it leaves the page.
// Android's back gesture (and the browser's back button) only walks the history, and an overlay is not a page. So
// every overlay adds a history entry while it is open (SvelteKit's shallow routing: same URL, `page.state.layers`).
// Going back removes that entry, and the overlay closes. Closing it from its own button removes the entry again, so
// no dead back step is left behind.
import { afterNavigate, goto, pushState } from '$app/navigation';
import { page } from '$app/state';

interface Layer {
	id: number;
	close: () => void;
	/** the page it was opened on — closing on another page means the page was left, not the overlay closed */
	url: string;
	/** closed by going back: the history entry is already gone */
	popped: boolean;
}

const stack: Layer[] = [];
let seq = 0;

/** Call in a component: while `isOpen()` is true, back closes it by calling `close()`. */
export function backLayer(isOpen: () => boolean, close: () => void) {
	let layer: Layer | null = null;
	$effect(() => {
		const open = isOpen();
		if (open && !layer) {
			layer = { id: ++seq, close, popped: false, url: location.pathname + location.search };
			stack.push(layer);
			pushState('', { ...page.state, layers: stack.map((l) => l.id) });
		} else if (!open && layer) {
			const l = layer;
			layer = null;
			drop(l);
		}
	});
	// unmounted while open: closed by its parent (photo viewer ✕) — or the page was left
	$effect(() => () => {
		if (layer) drop(layer);
	});
}

function drop(l: Layer) {
	if (l.popped) return;
	const i = stack.indexOf(l);
	if (i >= 0) stack.splice(i, 1);
	// closed from the page itself: take its history entry back out (only possible when it is the last one, and only
	// while still on the page it belongs to)
	const here = location.pathname + location.search === l.url;
	if (here && i === stack.length && (page.state as App.PageState).layers?.includes(l.id)) history.back();
}

/** Once, in the root layout: when going back removed layers from the history, close them (top first). */
export function watchBack() {
	$effect(() => {
		const ids = (page.state as App.PageState).layers ?? [];
		for (let i = stack.length - 1; i >= 0; i--) {
			const l = stack[i];
			if (ids.includes(l.id)) continue;
			stack.splice(i, 1);
			l.popped = true;
			l.close();
		}
	});
	afterNavigate((nav) => {
		const url = nav.to ? nav.to.url.pathname + nav.to.url.search : '';
		if (nav.type === 'popstate') {
			if ((nav.delta ?? -1) < 0) trail.splice(Math.max(0, trail.length + (nav.delta ?? -1)), -(nav.delta ?? -1));
			else trail.push(url);
			if (trail.at(-1) !== url) trail.splice(0, trail.length, url);
		} else if (nav.type === 'enter') trail.splice(0, trail.length, url);
		else if (nav.willUnload) return;
		else if ((nav as { replaceState?: boolean }).replaceState) trail[trail.length - 1] = url;
		else trail.push(url);
	});
}

// The pages visited in this tab, as far as we know — so a "back to the list" button can really go back.
const trail: string[] = [];

/** A "back to …" button: goes back in the history when that is where we came from, else opens `href`. */
export function backTo(href: string) {
	if (trail.length > 1 && trail.at(-2) === href) history.back();
	else goto(href);
}
