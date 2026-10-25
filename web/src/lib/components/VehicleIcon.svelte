<script lang="ts">
	// A tracker's pictogram in its colour — the same shapes as on the map, small enough for lists and chips.
	import { vehicleSvg } from '$lib/map/vehicleMarker';
	import type { Tracker } from '$lib/types';

	let { color, kind, size = 18, title }: { color?: string; kind?: Tracker['kind']; size?: number; title?: string } = $props();
</script>

<span class="vehicle-icon small" style="--c:{color ?? 'var(--text-2)'};width:{size}px;height:{size}px" {title}>
	<!-- fixed SVG shapes from vehicleMarker.ts, no user input -->
	{@html vehicleSvg(kind)}
</span>

<style>
	.small {
		display: inline-block;
		flex: none;
		vertical-align: -0.2em;
		filter: drop-shadow(0 1px 1px rgb(0 0 0 / 30%));
	}
</style>
