<script lang="ts">
	// Full-screen photo and video viewer: arrows / swipe / keyboard, Escape closes. The grid button shows every entry
	// at once (videos marked); picking one opens it large. Whether an entry is a video is asked from the server (map
	// markers do not carry the type) unless the caller already knows it.
	import { tick } from 'svelte';
	import { api, thumbUrl, videoUrl } from '$lib/api';
	import { dateTime } from '$lib/format';
	import { t } from '$lib/i18n/index.svelte';

	let {
		ids,
		index = $bindable(0),
		times = {},
		videos,
		overview = false,
		onclose
	}: {
		ids: string[];
		index?: number;
		times?: Record<string, number>;
		/** ids known to be videos; when omitted the viewer asks the server */
		videos?: Set<string>;
		/** start with the grid of all entries (stacks, "all photos of a place") instead of the first photo */
		overview?: boolean;
		onclose: () => void;
	} = $props();

	let touchX = 0;
	// svelte-ignore state_referenced_locally
	let grid = $state(overview && ids.length > 1);
	let gridEl: HTMLElement | undefined = $state();
	const id = $derived(ids[index]);
	let known = $state<Record<string, boolean>>({});
	const isVideo = $derived(videos ? videos.has(id) : known[id]);

	$effect(() => {
		const current = id;
		if (videos || current in known) return;
		api
			.get<{ is_video: boolean }>(`/api/photos/${current}/info`)
			.then((r) => (known[current] = r.is_video))
			.catch(() => (known[current] = false));
	});

	// Overview: ask for the kinds of everything in one go (in chunks the server accepts)
	$effect(() => {
		if (!grid || videos) return;
		const missing = ids.filter((i) => !(i in known));
		for (let k = 0; k < missing.length; k += 200) {
			const chunk = missing.slice(k, k + 200);
			api
				.post<{ videos: string[] }>('/api/photos/kinds', { ids: chunk })
				.then((r) => {
					const v = new Set(r.videos);
					for (const i of chunk) known[i] = v.has(i);
				})
				.catch(() => {});
		}
	});

	async function showGrid() {
		grid = true;
		await tick();
		gridEl?.querySelector('.current')?.scrollIntoView({ block: 'center' });
	}

	function pick(i: number) {
		index = i;
		grid = false;
	}

	const markedVideo = (i: string) => (videos ? videos.has(i) : known[i]);

	function go(delta: number) {
		index = (index + delta + ids.length) % ids.length;
	}

	function key(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			// opened as an overview: a photo goes back to the grid, the grid closes; otherwise the other way round
			if (grid === (overview && ids.length > 1)) onclose();
			else if (grid) grid = false;
			else showGrid();
		} else if (grid) return;
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
		if (grid) return;
		if (e.target instanceof HTMLVideoElement) return; // swiping on the player's controls is seeking, not paging
		const dx = e.changedTouches[0].clientX - touchX;
		if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1);
	}}
>
	<button class="close icon-btn" onclick={onclose} aria-label={t('close')}>✕</button>
	{#if ids.length > 1}
		<button class="grid-btn icon-btn" class:active={grid} onclick={() => (grid ? (grid = false) : showGrid())}
			aria-label={t('photos_overview')} title={t('photos_overview')}>
			<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg>
		</button>
	{/if}
	{#if grid}
		<div class="grid" bind:this={gridEl}>
			<div class="grid-head">{t('photos_count', { n: ids.length })}</div>
			<div class="tiles">
				{#each ids as gid, i (gid + i)}
					<button class="tile" class:current={i === index} onclick={() => pick(i)}>
						<img src={thumbUrl(gid)} alt="" loading="lazy" />
						{#if markedVideo(gid)}<span class="play" aria-label={t('video')}>▶</span>{/if}
					</button>
				{/each}
			</div>
		</div>
	{:else}
	{#key id}
		{#if isVideo}
			<!-- svelte-ignore a11y_media_has_caption -->
			<video class="photo" src={videoUrl(id)} poster={thumbUrl(id, 'preview')} controls autoplay playsinline></video>
		{:else}
			<!-- Small thumbnail first (usually cached), the large preview replaces it when loaded -->
			<img class="photo" src={thumbUrl(id, 'preview')} alt="" style="background-image:url({thumbUrl(id)})" />
		{/if}
	{/key}
	{#if ids.length > 1}
		<button class="nav prev icon-btn" onclick={() => go(-1)} aria-label={t('previous')}>‹</button>
		<button class="nav next icon-btn" onclick={() => go(1)} aria-label={t('next')}>›</button>
	{/if}
	<div class="caption">
		{index + 1} / {ids.length}
		{#if times[id]}· {dateTime(times[id])}{/if}
	</div>
	{/if}
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
		/* % of the fixed viewer, not vh — viewport units can be 0 in an Android WebView */
		max-width: 100%;
		max-height: calc(100% - 60px);
		object-fit: contain;
		background: center / contain no-repeat;
	}
	.close,
	.grid-btn {
		position: absolute;
		top: 12px;
		right: 12px;
		z-index: 3;
	}
	.grid-btn {
		right: auto;
		left: 12px;
	}
	.grid-btn svg {
		width: 18px;
		height: 18px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
	}
	.grid-btn.active {
		color: var(--accent);
		border-color: var(--accent);
	}
	.grid {
		position: absolute;
		inset: 0;
		overflow-y: auto;
		padding: 64px 8px 16px;
	}
	.grid-head {
		color: #ddd;
		text-align: center;
		margin-bottom: 10px;
		font-size: 0.9em;
	}
	.tiles {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(104px, 1fr));
		gap: 4px;
		max-width: 1100px;
		margin: 0 auto;
	}
	.tile {
		position: relative;
		aspect-ratio: 1;
		padding: 0;
		border: 2px solid transparent;
		background: #222;
		cursor: pointer;
		border-radius: 4px;
		overflow: hidden;
	}
	.tile.current {
		border-color: var(--accent);
	}
	.tile img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.play {
		position: absolute;
		inset: 0;
		margin: auto;
		width: 34px;
		height: 34px;
		border-radius: 50%;
		background: rgb(0 0 0 / 55%);
		color: #fff;
		display: grid;
		place-items: center;
		font-size: 14px;
		padding-left: 3px;
	}
	video.photo {
		width: 100%;
		background: #000;
	}
	.nav {
		position: absolute;
		top: 50%;
		z-index: 2;
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
