import type maplibregl from 'maplibre-gl';

/** False once the map was removed (page left): MapLibre then has no style, and any source access throws. Answers that
 * arrive late — a slow API call, a debounced redraw — check this before they draw. */
export const alive = (map: maplibregl.Map) => !!(map as unknown as { style?: unknown }).style;
