// A photo or video was deleted (in Immich, from the viewer): every list that shows it drops it — the map's stacks,
// an open trip, the diary, the viewer itself. One event instead of callbacks through every component.
const EVENT = 'tripatlas:photo-deleted';

export function announceDeleted(id: string) {
	window.dispatchEvent(new CustomEvent(EVENT, { detail: id }));
}

/** Call in a component: `fn` runs for every deleted photo while the component lives. */
export function onPhotoDeleted(fn: (id: string) => void) {
	$effect(() => {
		const handler = (e: Event) => fn((e as CustomEvent<string>).detail);
		window.addEventListener(EVENT, handler);
		return () => window.removeEventListener(EVENT, handler);
	});
}
