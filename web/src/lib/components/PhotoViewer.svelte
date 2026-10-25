<script lang="ts">
	// Full-screen photo and video viewer: arrows / swipe / keyboard, Escape closes. The grid button shows every entry
	// at once (videos marked); picking one opens it large. Whether an entry is a video is asked from the server (map
	// markers do not carry the type) unless the caller already knows it.
	import { tick } from 'svelte';
	import { api, thumbUrl, videoUrl } from '$lib/api';
	import VideoHint from './VideoHint.svelte';
	import { zoomable } from '$lib/zoom';
	import { backLayer } from '$lib/back.svelte';
	import { countryName, dateTime } from '$lib/format';
	import { camera, duration, exposure, fileSize, place, takenAt, type PhotoInfo } from '$lib/photoInfo';
	import { i18n, t } from '$lib/i18n/index.svelte';

	let {
		ids,
		index = $bindable(0),
		times = {},
		videos,
		overview = false,
		onnote,
		onclose
	}: {
		ids: string[];
		index?: number;
		times?: Record<string, number>;
		/** ids known to be videos; when omitted the viewer asks the server */
		videos?: Set<string>;
		/** start with the grid of all entries (stacks, "all photos of a place") instead of the first photo */
		overview?: boolean;
		/** offered in the overview when set: pin a note to the place of these photos */
		onnote?: (photoId: string) => void;
		onclose: () => void;
	} = $props();

	let touchX = 0;
	// zoomed into the photo: swiping moves the photo instead of paging (lib/zoom.ts)
	let zoom = $state(1);
	let hiRes = $state(false);
	let multiTouch = false;
	// svelte-ignore state_referenced_locally
	let grid = $state(overview && ids.length > 1);
	let gridEl: HTMLElement | undefined = $state();
	// columns of the overview, remembered on this device
	const COLS_KEY = 'tripatlas.viewer.columns';
	let cols = $state(readCols());
	// tiles wider than the 250 px thumbnails (computer screens) get the preview size, so they are not blurry
	const wide = typeof window !== 'undefined' && window.innerWidth > 900;
	function readCols(): number {
		try {
			const n = Number(localStorage.getItem(COLS_KEY));
			return [1, 2, 3].includes(n) ? n : 3;
		} catch {
			return 3;
		}
	}
	async function setCols(n: number) {
		const keep = gridEl?.querySelector('.current');
		cols = n;
		try {
			localStorage.setItem(COLS_KEY, String(n));
		} catch {
			// storage blocked: the choice lasts until the viewer closes
		}
		await tick();
		keep?.scrollIntoView({ block: 'center' });
	}
	const id = $derived(ids[index]);
	// every photo starts unzoomed, with the preview
	$effect(() => {
		void id;
		zoom = 1;
		hiRes = false;
	});
	let known = $state<Record<string, boolean>>({});
	const isVideo = $derived(videos ? videos.has(id) : known[id]);

	// what is known about each photo (date, place, camera …): the quiet line underneath and the i panel
	let infos = $state<Record<string, PhotoInfo | null>>({});
	const info = $derived(infos[id]);
	let showInfo = $state(false);
	// back gesture: the info panel first, then a photo opened from the overview goes back to it, then the viewer closes
	backLayer(() => true, () => onclose());
	backLayer(() => !overview && grid, () => (grid = false));
	backLayer(() => !!overview && ids.length > 1 && !grid, () => (grid = true));
	backLayer(() => showInfo, () => (showInfo = false));
	let exifTags = $state<Record<string, Record<string, string> | null>>({});
	let exifOpen = $state(false);

	$effect(() => {
		const current = id;
		if (current in infos) return;
		infos[current] = null;
		api
			.get<PhotoInfo>(`/api/photos/${current}/info`)
			.then((r) => {
				infos[current] = r;
				known[current] = r.is_video;
			})
			.catch(() => {
				if (!(current in known)) known[current] = false;
			});
	});

	function loadExif() {
		exifOpen = true;
		const current = id;
		if (current in exifTags) return;
		exifTags[current] = null;
		api
			.get<{ tags: Record<string, string> }>(`/api/photos/${current}/exif`)
			.then((r) => (exifTags[current] = r.tags))
			.catch(() => (exifTags[current] = {}));
	}

	// a different photo: the full EXIF list folds up again
	$effect(() => {
		void id;
		exifOpen = false;
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
		if (e.key === 'Escape' && showInfo) {
			showInfo = false;
			return;
		}
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
	ontouchstart={(e) => {
		if (e.touches.length === 1) {
			touchX = e.touches[0].clientX;
			multiTouch = false;
		} else multiTouch = true;
	}}
	ontouchend={(e) => {
		if (grid || zoom > 1 || multiTouch || e.touches.length) return;
		if (e.target instanceof HTMLVideoElement) return; // swiping on the player's controls is seeking, not paging
		const dx = e.changedTouches[0].clientX - touchX;
		if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1);
	}}
>
	<button class="close icon-btn" onclick={onclose} aria-label={t('close')}>✕</button>
	{#if onnote && !grid}
		<button class="note-fab" onclick={() => onnote(ids[index])} title={t('note_pin')} aria-label={t('note_pin')}>📌</button>
	{/if}
	{#if ids.length > 1}
		<button class="grid-btn icon-btn" class:active={grid} onclick={() => (grid ? (grid = false) : showGrid())}
			aria-label={t('photos_overview')} title={t('photos_overview')}>
			<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg>
		</button>
	{/if}
	{#if grid}
		<div class="grid" bind:this={gridEl}>
			<div class="grid-head">
				<span>{t('photos_count', { n: ids.length })}</span>
				{#if onnote}
					<button class="note-btn" onclick={() => onnote(ids[index])} title={t('note_pin')}>📌 {t('note_label')}</button>
				{/if}
				<div class="cols" role="group" aria-label={t('photos_columns')}>
					{#each [3, 2, 1] as n (n)}
						<button class:on={cols === n} onclick={() => setCols(n)} aria-pressed={cols === n}
							title={t('photos_columns_n', { n })} aria-label={t('photos_columns_n', { n })}>
							<svg viewBox="0 0 24 24" aria-hidden="true">
								{#each Array(n) as _, k (k)}<rect x={3 + k * (18 / n) + 0.75} y="4" width={18 / n - 1.5} height="16" rx="1.5" />{/each}
							</svg>
						</button>
					{/each}
				</div>
			</div>
			<div class="tiles" class:wide={cols < 3} style="--cols:{cols}">
				{#each ids as gid, i (gid + i)}
					<button class="tile" class:current={i === index} onclick={() => pick(i)}>
						<img src={thumbUrl(gid, cols < 3 || wide ? 'medium' : 'thumbnail')} alt="" loading="lazy" />
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
			<!-- Zoomed in past 1.6× the full resolution replaces the preview (which stays behind it as a placeholder) -->
			<img class="photo zoomable" src={thumbUrl(id, hiRes ? 'fullsize' : 'preview')} alt=""
				style:background-image="url({thumbUrl(id, hiRes ? 'preview' : 'thumbnail')})"
				use:zoomable={{ onchange: (z) => ((zoom = z), z > 1.6 && (hiRes = true)) }}
				onerror={() => hiRes && (hiRes = false)} />
		{/if}
	{/key}
	{#if isVideo}<VideoHint />{/if}
	{#if ids.length > 1}
		<button class="nav prev icon-btn" onclick={() => go(-1)} aria-label={t('previous')}>‹</button>
		<button class="nav next icon-btn" onclick={() => go(1)} aria-label={t('next')}>›</button>
	{/if}
	<div class="caption">
		<span class="line">
			{#if info && takenAt(info)}{takenAt(info)}{:else if times[id]}{dateTime(times[id])}{/if}
			{#if info && place(info)}<span class="sep">·</span>{place(info)}{/if}
			{#if info && camera(info)}<span class="sep wide">·</span><span class="wide">{camera(info)}</span>{/if}
		</span>
		<span class="count">{index + 1} / {ids.length}</span>
	</div>
	<button class="info-btn" class:active={showInfo} onclick={() => (showInfo = !showInfo)} aria-expanded={showInfo}
		aria-label={t('photo_info')} title={t('photo_info')}>i</button>
	{#if showInfo}
		<aside class="info-panel" aria-label={t('photo_info')}>
			<button class="close-info" onclick={() => (showInfo = false)} aria-label={t('close')}>✕</button>
			{#if !info}
				<p class="muted">{t('loading')}</p>
			{:else}
				<dl>
					{#if takenAt(info, true)}<dt>{t('photo_taken')}</dt><dd>{takenAt(info, true)}{#if info.time_zone}<small> ({info.time_zone})</small>{/if}</dd>{/if}
					{#if place(info) || info.state}<dt>{t('photo_place')}</dt><dd>{[info.city, info.state, info.country_code ? countryName(info.country_code) : info.country].filter(Boolean).join(', ')}</dd>{/if}
					{#if info.lat != null && info.lon != null}
						<dt>{t('photo_coordinates')}</dt>
						<dd><a href="https://www.openstreetmap.org/?mlat={info.lat}&mlon={info.lon}#map=16/{info.lat}/{info.lon}" target="_blank" rel="noopener noreferrer">{info.lat.toFixed(5)}, {info.lon.toFixed(5)}</a></dd>
					{/if}
					{#if camera(info)}<dt>{t('photo_camera')}</dt><dd>{camera(info)}</dd>{/if}
					{#if info.lens}<dt>{t('photo_lens')}</dt><dd>{info.lens}</dd>{/if}
					{#if exposure(info)}<dt>{t('photo_exposure')}</dt><dd>{exposure(info)}</dd>{/if}
					{#if info.width && info.height}<dt>{t('photo_dimensions')}</dt><dd>{info.width} × {info.height} px{#if info.width * info.height > 0} ({(Math.round((info.width * info.height) / 1e5) / 10).toLocaleString(i18n.locale)} MP){/if}</dd>{/if}
					{#if duration(info.duration) && info.is_video}<dt>{t('photo_duration')}</dt><dd>{duration(info.duration)}</dd>{/if}
					{#if info.filename}<dt>{t('photo_file')}</dt><dd class="break">{info.filename}</dd>{/if}
					{#if info.mime || info.file_size}<dt>{t('photo_type')}</dt><dd>{[info.mime, fileSize(info.file_size)].filter(Boolean).join(' · ')}</dd>{/if}
					{#if info.description}<dt>{t('photo_description')}</dt><dd>{info.description}</dd>{/if}
					{#if info.rating}<dt>{t('photo_rating')}</dt><dd>{'★'.repeat(info.rating)}</dd>{/if}
				</dl>
				{#if !exifOpen}
					<button class="link-btn" onclick={loadExif}>{t('photo_all_exif')}</button>
				{:else if exifTags[id] === null || exifTags[id] === undefined}
					<p class="muted">{t('loading')}</p>
				{:else if Object.keys(exifTags[id] ?? {}).length === 0}
					<p class="muted">{t('photo_no_exif')}</p>
				{:else}
					<h4>{t('photo_all_exif')}</h4>
					<dl class="exif">
						{#each Object.entries(exifTags[id] ?? {}) as [k, v] (k)}<dt>{k}</dt><dd class="break">{v}</dd>{/each}
					</dl>
				{/if}
			{/if}
		</aside>
	{/if}
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
		/* The whole viewer except the caption strip; object-fit fits the picture in. Sizes relative to the fixed
		   viewer, not vh (0 in an Android WebView) — and not max-height in %: inside the grid that was not
		   recomputed when the phone was turned, the photo stayed at its old size and was cut off. */
		position: absolute;
		left: 0;
		top: 0;
		width: 100%;
		height: calc(100% - 60px);
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
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		max-width: 1100px;
		margin: 0 auto 10px;
		font-size: 0.9em;
	}
	.note-fab {
		position: absolute;
		top: 12px;
		right: 60px;
		z-index: 3;
		border: 0;
		border-radius: 50%;
		width: 36px;
		height: 36px;
		background: #fde68a;
		cursor: pointer;
		font-size: 16px;
	}
	.note-btn {
		white-space: nowrap;
		margin-left: auto;
		border: 0;
		border-radius: 999px;
		padding: 5px 12px;
		background: #fde68a;
		color: #422006;
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}
	.cols {
		display: flex;
		background: rgb(255 255 255 / 12%);
		border-radius: 999px;
		padding: 2px;
	}
	.cols button {
		border: 0;
		background: none;
		color: #ccc;
		padding: 5px 9px;
		border-radius: 999px;
		cursor: pointer;
		display: grid;
	}
	.cols button.on {
		background: rgb(255 255 255 / 22%);
		color: #fff;
	}
	.cols svg {
		width: 18px;
		height: 18px;
		fill: currentColor;
	}
	.tiles {
		display: grid;
		/* the chosen number of columns is for a phone held upright (about 430 px); wider (turned, computer) gets
		   proportionally more columns of the same tile size instead of a few huge ones */
		grid-template-columns: repeat(auto-fill, minmax(calc((min(100%, 430px) - (var(--cols) - 1) * 6px) / var(--cols)), 1fr));
		gap: 4px;
		max-width: 1100px;
		margin: 0 auto;
	}
	.tiles.wide {
		gap: 6px;
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
		left: 56px;
		right: 56px;
		bottom: 12px;
		display: flex;
		justify-content: center;
		align-items: baseline;
		gap: 12px;
		color: rgb(255 255 255 / 75%);
		font-size: 0.85em;
		text-shadow: 0 1px 2px rgb(0 0 0 / 70%);
		pointer-events: none;
	}
	.caption .line {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.caption .sep {
		margin: 0 6px;
		opacity: 0.6;
	}
	.caption .count {
		flex: none;
		opacity: 0.7;
	}
	@media (max-width: 600px) {
		.caption .wide {
			display: none;
		}
	}
	.info-btn {
		position: absolute;
		right: 12px;
		bottom: 8px;
		z-index: 3;
		width: 30px;
		height: 30px;
		border-radius: 50%;
		border: 1.5px solid rgb(255 255 255 / 70%);
		background: rgb(0 0 0 / 35%);
		color: #fff;
		font: italic 700 15px/1 Georgia, serif;
		cursor: pointer;
	}
	.info-btn.active {
		background: #fff;
		color: #111;
	}
	.info-panel {
		position: absolute;
		right: 0;
		bottom: 0;
		z-index: 4;
		width: min(380px, 100%);
		max-height: 70%;
		overflow-y: auto;
		background: var(--surface);
		color: var(--text);
		border-radius: 14px 14px 0 0;
		padding: 16px 16px 20px;
		box-shadow: 0 -6px 24px rgb(0 0 0 / 35%);
	}
	.close-info {
		position: absolute;
		top: 8px;
		right: 8px;
		border: 0;
		background: none;
		color: var(--text-2);
		font-size: 1.1em;
		cursor: pointer;
	}
	.info-panel dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 6px 12px;
		margin: 4px 0 12px;
		font-size: 0.9em;
	}
	.info-panel dt {
		color: var(--text-2);
	}
	.info-panel dd {
		margin: 0;
	}
	.info-panel .break {
		overflow-wrap: anywhere;
	}
	.info-panel dl.exif {
		font-size: 0.8em;
	}
	.info-panel h4 {
		margin: 8px 0 4px;
	}
	.link-btn {
		border: 0;
		background: none;
		color: var(--accent);
		padding: 0;
		font: inherit;
		cursor: pointer;
		text-decoration: underline;
	}
</style>
