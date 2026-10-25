// See https://svelte.dev/docs/kit/types#app.d.ts
declare global {
	namespace App {
		interface PageState {
			/** overlays open on top of the page, one history entry each (lib/back.svelte.ts) */
			layers?: number[];
		}
	}
}
export {};
