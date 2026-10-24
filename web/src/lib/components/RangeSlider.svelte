<script lang="ts">
	// Two-handle slider over a time span. The track between the handles is what the map draws; the right handle is
	// "now" for the vehicle marker. Built from two native range inputs for keyboard and screen-reader support.
	let {
		min,
		max,
		from = $bindable(),
		to = $bindable(),
		step = 60,
		labelFrom = 'From',
		labelTo = 'To'
	}: {
		min: number;
		max: number;
		from: number;
		to: number;
		step?: number;
		labelFrom?: string;
		labelTo?: string;
	} = $props();

	const pct = (v: number) => ((v - min) / (max - min || 1)) * 100;
</script>

<div class="range" style="--a:{pct(from)}%;--b:{pct(to)}%">
	<div class="rail"></div>
	<div class="fill"></div>
	<input
		type="range"
		{min}
		{max}
		{step}
		bind:value={from}
		aria-label={labelFrom}
		oninput={() => (from = Math.min(from, to - step))}
	/>
	<input
		type="range"
		{min}
		{max}
		{step}
		bind:value={to}
		aria-label={labelTo}
		oninput={() => (to = Math.max(to, from + step))}
	/>
</div>

<style>
	.range {
		position: relative;
		height: 28px;
	}
	.rail,
	.fill {
		position: absolute;
		top: 12px;
		height: 4px;
		border-radius: 2px;
	}
	.rail {
		left: 0;
		right: 0;
		background: var(--border);
	}
	.fill {
		left: var(--a);
		right: calc(100% - var(--b));
		background: var(--accent);
	}
	input {
		position: absolute;
		inset: 0;
		width: 100%;
		margin: 0;
		background: none;
		pointer-events: none;
		appearance: none;
		-webkit-appearance: none;
	}
	input::-webkit-slider-thumb {
		pointer-events: auto;
		-webkit-appearance: none;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: var(--surface);
		border: 3px solid var(--accent);
		cursor: grab;
		box-shadow: var(--shadow);
	}
	input::-moz-range-thumb {
		pointer-events: auto;
		width: 18px;
		height: 18px;
		border-radius: 50%;
		background: var(--surface);
		border: 3px solid var(--accent);
		cursor: grab;
	}
	input::-moz-range-track {
		background: none;
	}
</style>
