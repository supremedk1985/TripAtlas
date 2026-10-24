<script lang="ts">
	// Full-screen photo viewer: arrows / swipe / keyboard, Escape closes.
	import { thumbUrl } from '$lib/api';
	import { dateTime } from '$lib/format';
	import { t } from '$lib/i18n/index.svelte';

	let {
		ids,
		index = $bindable(0),
		times = {},
		onclose
	}: { ids: string[]; index?: number; times?: Record<string, number>; onclose: () => void } = $props();

	let touchX = 0;
	const id = $derived(ids[index]);

	function go(delta: number) {
		index = (index + delta + ids.length) % ids.length;
	}

	function key(e: KeyboardEvent) {
		if (e.key === 'Escape') onclose();
		else if (e.key === 'ArrowRight') go(1);
		else if (e.key === 'ArrowLeft') go(-1);
	}
</script>

<svelte:window onkeydown={key} />

<div
	class="viewer"
	role="dialog"
	aria-modal="true"
	tabindex="-1"
	ontouchstart={(e) => (touchX = e.touches[0].clientX)}
	ontouchend={(e) => {
		const dx = e.changedTouches[0].clientX - touchX;
		if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1);
	}}
>
	<button class="close icon-btn" onclick={onclose} aria-label={t('close')}>✕</button>
	{#key id}
		<!-- Small thumbnail first (usually cached), the large preview replaces it when loaded -->
		<img class="photo" src={thumbUrl(id, 'preview')} alt="" style="background-image:url({thumbUrl(id)})" />
	{/key}
	{#if ids.length > 1}
		<button class="nav prev icon-btn" onclick={() => go(-1)} aria-label={t('previous')}>‹</button>
		<button class="nav next icon-btn" onclick={() => go(1)} aria-label={t('next')}>›</button>
	{/if}
	<div class="caption">
		{index + 1} / {ids.length}
		{#if times[id]}· {dateTime(times[id])}{/if}
	</div>
</div>

<style>
	.viewer {
		position: fixed;
		inset: 0;
		z-index: 100;
		background: rgb(0 0 0 / 92%);
		display: grid;
		place-items: center;
	}
	.photo {
		max-width: 100vw;
		max-height: calc(100vh - 60px);
		object-fit: contain;
		background: center / contain no-repeat;
	}
	.close {
		position: absolute;
		top: 12px;
		right: 12px;
		z-index: 2;
	}
	.nav {
		position: absolute;
		top: 50%;
		font-size: 1.6em;
		width: 1.8em;
		height: 1.8em;
		opacity: 0.85;
	}
	.prev {
		left: 12px;
	}
	.next {
		right: 12px;
	}
	.caption {
		position: absolute;
		bottom: 14px;
		color: #ddd;
		font-size: 0.9em;
	}
</style>
