// Where a tracker is (live) or was (replay): a pictogram in the tracker's colour — a car, or a person for trackers
// carried by someone — or the tracker's own picture when one is set. Deliberately not a plain coloured dot: a red dot
// already means "on the road right now" elsewhere in the UI.
import type { Tracker } from '$lib/types';

const CAR =
	'<path d="M5 11l1.6-4.2A2 2 0 0 1 8.5 5.5h7a2 2 0 0 1 1.9 1.3L19 11h.5a1.5 1.5 0 0 1 1.5 1.5V17a1 1 0 0 1-1 1h-1v1.5a1 1 0 0 1-1 1h-1a1 1 0 0 1-1-1V18H8v1.5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V18H4a1 1 0 0 1-1-1v-4.5A1.5 1.5 0 0 1 4.5 11z" class="body"/>' +
	'<path d="M7.3 11l1.1-3.3h7.2l1.1 3.3z" class="glass"/><circle cx="6.6" cy="14.4" r="1.3" class="glass"/><circle cx="17.4" cy="14.4" r="1.3" class="glass"/>';
const PERSON =
	'<circle cx="12" cy="6.5" r="3.5" class="body"/><path d="M5 21v-3.5A5.5 5.5 0 0 1 10.5 12h3a5.5 5.5 0 0 1 5.5 5.5V21z" class="body"/>';

export function vehicleMarker(opts: { color: string; kind?: Tracker['kind']; avatarUrl?: string; title?: string; live?: boolean }) {
	const el = document.createElement('div');
	el.style.setProperty('--c', opts.color);
	if (opts.title) el.title = opts.title;
	if (opts.avatarUrl) {
		el.className = 'vehicle-marker' + (opts.live ? ' live' : '');
		el.style.backgroundImage = `url(${opts.avatarUrl})`;
	} else {
		el.className = 'vehicle-icon' + (opts.live ? ' live' : '');
		el.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${opts.kind === 'person' ? PERSON : CAR}</svg>`;
	}
	return el;
}
