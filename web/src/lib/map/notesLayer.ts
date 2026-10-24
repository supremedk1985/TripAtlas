// Sticky notes on the map ("our first campsite"): small yellow paper notes that stay where they were pinned, also when
// the photo stacks around them regroup while zooming.
import maplibregl from 'maplibre-gl';
import type { MapNote } from '$lib/types';

export class NotesLayer {
	private markers: maplibregl.Marker[] = [];
	private notes: MapNote[] = [];
	private visible = true;

	constructor(
		private map: maplibregl.Map,
		private onClick: (note: MapNote) => void
	) {}

	setNotes(notes: MapNote[]) {
		this.notes = notes;
		this.draw();
	}

	setVisible(on: boolean) {
		this.visible = on;
		this.draw();
	}

	private draw() {
		this.markers.forEach((m) => m.remove());
		this.markers = [];
		if (!this.visible) return;
		for (const n of this.notes) {
			const el = document.createElement('button');
			el.className = 'sticky-note';
			el.type = 'button';
			el.textContent = n.text.length > 28 ? n.text.slice(0, 26) + '…' : n.text;
			el.title = n.text;
			// a slight tilt from the id, so neighbouring notes do not look like one block
			el.style.setProperty('--tilt', `${((n.id * 37) % 9) - 4}deg`);
			el.addEventListener('click', (e) => {
				e.stopPropagation();
				this.onClick(n);
			});
			// anchored at the bottom left corner, which sits on the place — like a note stuck onto the stack
			this.markers.push(new maplibregl.Marker({ element: el, anchor: 'bottom-left', offset: [6, -6] }).setLngLat([n.lon, n.lat]).addTo(this.map));
		}
	}
}
