<script lang="ts">
	// Cut a round profile picture out of a chosen photo: drag to move, slider / wheel / two fingers to zoom.
	import { cropJpeg } from '$lib/avatar';
	import { t } from '$lib/i18n/index.svelte';
	import { onDestroy } from 'svelte';

	let { file, ondone, oncancel }: { file: File; ondone: (jpeg: Blob) => void; oncancel: () => void } = $props();

	const V = 280; // size of the cut-out on screen, px
	// one cropper per file (the picker re-creates it with {#key})
	// svelte-ignore state_referenced_locally
	const url = URL.createObjectURL(file);
	onDestroy(() => URL.revokeObjectURL(url));

	let w = $state(0); // picture size as displayed by the browser (already upright)
	let h = $state(0);
	let zoom = $state(1);
	let x = $state(0); // top-left corner of the picture inside the cut-out, px
	let y = $state(0);
	let busy = $state(false);
	let error = $state('');

	const base = $derived(w && h ? V / Math.min(w, h) : 1); // zoom 1 = the picture just covers the circle
	const s = $derived(base * zoom);

	function clamp() {
		x = Math.min(0, Math.max(V - w * s, x));
		y = Math.min(0, Math.max(V - h * s, y));
	}

	function loaded(e: Event) {
		const img = e.currentTarget as HTMLImageElement;
		w = img.naturalWidth;
		h = img.naturalHeight;
		x = (V - w * base) / 2;
		y = (V - h * base) / 2;
	}

	function setZoom(z: number) {
		// zoom around the middle of the circle
		const nz = Math.min(5, Math.max(1, z));
		const cx = (V / 2 - x) / s;
		const cy = (V / 2 - y) / s;
		zoom = nz;
		x = V / 2 - cx * base * nz;
		y = V / 2 - cy * base * nz;
		clamp();
	}

	// pointers: one finger drags, two fingers pinch
	const pts = new Map<number, { x: number; y: number }>();
	let pinch = 0;
	function down(e: PointerEvent) {
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
		pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
		if (pts.size === 2) pinch = dist();
	}
	function move(e: PointerEvent) {
		const p = pts.get(e.pointerId);
		if (!p) return;
		if (pts.size === 1) {
			x += e.clientX - p.x;
			y += e.clientY - p.y;
			clamp();
		}
		pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
		if (pts.size === 2 && pinch) {
			const d = dist();
			setZoom((zoom * d) / pinch);
			pinch = d;
		}
	}
	function up(e: PointerEvent) {
		pts.delete(e.pointerId);
		pinch = 0;
	}
	function dist() {
		const [a, b] = [...pts.values()];
		return Math.hypot(a.x - b.x, a.y - b.y);
	}

	async function apply() {
		busy = true;
		try {
			ondone(await cropJpeg(file, -x / s, -y / s, V / s));
		} catch {
			error = t('avatar_unreadable');
			busy = false;
		}
	}
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && oncancel()} />

<div class="backdrop" role="dialog" aria-modal="true" aria-label={t('avatar_crop')}>
	<div class="card box">
		<h3>{t('avatar_crop')}</h3>
		<div
			class="stage"
			style="width:{V}px;height:{V}px"
			onpointerdown={down}
			onpointermove={move}
			onpointerup={up}
			onpointercancel={up}
			onwheel={(e) => (e.preventDefault(), setZoom(zoom * (e.deltaY < 0 ? 1.1 : 1 / 1.1)))}
			role="presentation"
		>
			<img src={url} alt="" onload={loaded} onerror={() => (error = t('avatar_unreadable'))} draggable="false"
				style="width:{w * s}px;height:{h * s}px;transform:translate({x}px,{y}px)" />
			<div class="mask"></div>
		</div>
		<label class="zoom">
			<span aria-hidden="true">−</span>
			<input type="range" min="1" max="5" step="0.01" value={zoom} oninput={(e) => setZoom(+e.currentTarget.value)}
				aria-label={t('avatar_zoom')} />
			<span aria-hidden="true">+</span>
		</label>
		<p class="muted small">{t('avatar_crop_hint')}</p>
		{#if error}<p class="error">{error}</p>{/if}
		<div class="row buttons">
			<button class="btn" onclick={oncancel}>{t('cancel')}</button>
			<button class="btn primary" onclick={apply} disabled={busy || !w}>{t('avatar_apply')}</button>
		</div>
	</div>
</div>

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 200;
		background: rgb(0 0 0 / 55%);
		display: grid;
		place-items: center;
		padding: 16px;
	}
	.box {
		padding: 18px;
		display: grid;
		gap: 10px;
		justify-items: center;
		max-width: 100%;
	}
	h3 {
		margin: 0;
	}
	.stage {
		position: relative;
		overflow: hidden;
		touch-action: none;
		cursor: grab;
		background: #111;
		border-radius: 12px;
		max-width: 100%;
	}
	.stage img {
		position: absolute;
		left: 0;
		top: 0;
		transform-origin: 0 0;
		user-select: none;
		pointer-events: none;
		max-width: none;
	}
	.mask {
		position: absolute;
		inset: 0;
		border-radius: 50%;
		box-shadow: 0 0 0 999px rgb(0 0 0 / 55%);
		outline: 2px solid #fff;
		pointer-events: none;
	}
	.zoom {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
	}
	.zoom input {
		flex: 1;
	}
	.buttons {
		justify-content: flex-end;
		width: 100%;
	}
	p {
		margin: 0;
		text-align: center;
	}
</style>
