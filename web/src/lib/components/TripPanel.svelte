<script lang="ts">
	// Details of one trip: header with cover, stats, time slider to replay the route, the timeline of drives and
	// stays (with photos and "about this place"), and the editable title/note.
	import { untrack } from 'svelte';
	import { api, errorText, thumbUrl } from '$lib/api';
	import { countryName, date, dateRange, dateTime, flag, km, tripTitle } from '$lib/format';
	import { plural, t } from '$lib/i18n/index.svelte';
	import type { MapControl } from '$lib/map/control';
	import { canEdit } from '$lib/stores/session.svelte';
	import type { Photo, TimelineEntry, Tracker, TrackPoint, TripDetail } from '$lib/types';
	import NoteEditor from './NoteEditor.svelte';
	import NoteView from './NoteView.svelte';
	import PlaceCard from './PlaceCard.svelte';
	import RangeSlider from './RangeSlider.svelte';

	let {
		tripId,
		tracker,
		control,
		onclose
	}: { tripId: number; tracker: Tracker | undefined; control: MapControl; onclose: () => void } = $props();

	let trip = $state<TripDetail | null>(null);
	let points = $state<TrackPoint[]>([]);
	let photos = $state<Photo[]>([]);
	let timeline = $state<TimelineEntry[] | null>(null);
	let from = $state(0);
	let to = $state(0);
	let playing = $state(false);
	let follow = $state(false);
	let openPlace = $state<number | null>(null);
	let editing = $state<{ kind: 'trip' | 'stay'; dayKey: string; title: string; html: string } | null>(null);
	let saving = $state(false);
	let error = $state('');

	$effect(() => {
		load(tripId);
	});

	async function load(id: number) {
		trip = null;
		timeline = null;
		photos = [];
		error = '';
		try {
			const [detail, track] = await Promise.all([
				api.get<TripDetail>(`/api/trips/${id}`),
				api.get<{ points: TrackPoint[] }>(`/api/trips/${id}/track`)
			]);
			trip = detail;
			points = track.points;
			from = detail.start;
			to = detail.end;
			const avatar = tracker?.has_avatar ? `/api/trackers/${tracker.id}/avatar` : undefined;
			control.showTrip(points, detail.stays, tracker?.color ?? '#e4572e', avatar);
			control.fit(points.map((p) => ({ lat: p[1], lon: p[2] })));
			// Slower parts afterwards: photos and the timeline need Immich.
			api.get<{ photos: Photo[] }>(`/api/trips/${id}/photos`).then((r) => {
				photos = r.photos;
				control.showTripPhotos(photos);
			});
			api.get<{ entries: TimelineEntry[] }>(`/api/trips/${id}/timeline`).then((r) => (timeline = r.entries));
		} catch (e) {
			error = errorText(e);
		}
	}

	$effect(() => {
		if (trip) control.setRange(from, to, follow);
	});

	// Replay: move the right handle from the left handle to the end in about 40 seconds.
	$effect(() => {
		if (!playing || !trip) return;
		const end = trip.end;
		// untrack: the effect must not restart on every frame just because `to` moves
		untrack(() => {
			if (to >= end - 60) to = from + 60;
		});
		const stepPerFrame = (end - untrack(() => from)) / (40 * 60);
		let raf = 0;
		const frame = () => {
			to = Math.min(end, to + stepPerFrame);
			if (to >= end) playing = false;
			else raf = requestAnimationFrame(frame);
		};
		raf = requestAnimationFrame(frame);
		return () => cancelAnimationFrame(raf);
	});

	const photoTimes = $derived(Object.fromEntries(photos.map((p) => [p.id, p.t])));
	const videoIds = $derived(new Set(photos.filter((p) => p.is_video).map((p) => p.id)));
	const inRange = $derived(photos.filter((p) => p.t >= from && p.t <= to));

	function photosOf(e: TimelineEntry) {
		return photos.filter((p) => p.t >= e.start && p.t <= e.end);
	}

	function openStrip(list: Photo[], i: number) {
		control.openPhotos(
			list.map((p) => p.id),
			i,
			photoTimes,
			videoIds
		);
	}

	function showEntry(e: TimelineEntry) {
		from = e.start;
		to = e.end;
		const part = points.filter((p) => p[0] >= e.start && p[0] <= e.end).map((p) => ({ lat: p[1], lon: p[2] }));
		if (e.kind === 'stay' && e.lat !== null && e.lon !== null) control.focus(e.lat, e.lon, 12);
		else control.fit(part);
	}

	function resetRange() {
		if (!trip) return;
		from = trip.start;
		to = trip.end;
		control.fit(points.map((p) => ({ lat: p[1], lon: p[2] })));
	}

	async function save() {
		if (!editing || !trip) return;
		saving = true;
		try {
			const r = await api.put<{ title: string; note_html: string }>('/api/annotations', {
				tracker_id: trip.tracker_id,
				kind: editing.kind,
				day_key: editing.dayKey,
				title: editing.title,
				note_html: editing.html
			});
			if (editing.kind === 'trip') {
				trip.title = r.title;
				trip.note_html = r.note_html;
			} else if (timeline) {
				const entry = timeline.find((e) => e.day_key === editing!.dayKey);
				if (entry) {
					entry.title = r.title;
					entry.note_html = r.note_html;
				}
			}
			editing = null;
		} catch (e) {
			error = errorText(e);
		} finally {
			saving = false;
		}
	}
</script>

<div class="panel">
	<div class="top row">
		<button class="icon-btn" onclick={onclose} aria-label={t('back')}>←</button>
		<span class="muted">{tracker?.name ?? ''}</span>
	</div>

	{#if error}
		<p class="error">{error}</p>
	{:else if !trip}
		<p class="muted">{t('loading')}</p>
	{:else}
		{#if trip.cover_asset}
			<button class="cover" onclick={() => control.openPhotos([trip!.cover_asset!], 0)}>
				<img src={thumbUrl(trip.cover_asset, 'preview')} alt="" />
			</button>
		{/if}

		<header>
			<h2>{tripTitle(trip, t('trip_untitled'))}</h2>
			<p class="muted">
				{dateRange(trip.start, trip.end)}
				{#if trip.ongoing}<span class="live">● {t('trip_ongoing')}</span>{/if}
			</p>
			{#if canEdit()}
				<button
					class="btn small"
					onclick={() =>
						(editing = { kind: 'trip', dayKey: trip!.day_key, title: trip!.title, html: trip!.note_html })}
					>✎ {t('edit_title_note')}</button
				>
			{/if}
		</header>

		<div class="stats">
			<div><strong>{plural('nights', trip.nights)}</strong></div>
			<div><strong>{km(trip.distance_km)}</strong></div>
			<div><strong>{plural('photos', trip.photo_count)}</strong></div>
		</div>
		{#if trip.countries.length}
			<p class="countries">
				{#each trip.countries as c (c)}<span class="chip" title={countryName(c)}>{flag(c)} {countryName(c)}</span>{/each}
			</p>
		{/if}

		{#if trip.note_html && editing?.kind !== 'trip'}
			<NoteView html={trip.note_html} />
		{/if}

		{#if editing}
			<div class="edit card">
				<label class="field">
					<span>{t('title')}</span>
					<input type="text" bind:value={editing.title} placeholder={t('title_placeholder')} maxlength="200" />
				</label>
				<span class="field-label">{t('note')}</span>
				<NoteEditor html={editing.html} onchange={(h) => (editing!.html = h)} />
				<div class="row actions">
					<button class="btn primary" onclick={save} disabled={saving}>{t('save')}</button>
					<button class="btn" onclick={() => (editing = null)}>{t('cancel')}</button>
				</div>
			</div>
		{/if}

		<section class="replay">
			<div class="row">
				<button class="icon-btn" onclick={() => (playing = !playing)} aria-label={playing ? t('pause') : t('play')}>
					{playing ? '❚❚' : '▶'}
				</button>
				<div class="range-label">
					<strong>{dateTime(from)}</strong> – <strong>{dateTime(to)}</strong>
				</div>
				<span class="spacer"></span>
				<label class="chip" class:on={follow}>
					<input type="checkbox" bind:checked={follow} hidden />{t('follow')}
				</label>
			</div>
			<RangeSlider min={trip.start} max={trip.end} bind:from bind:to labelFrom={t('range_from')} labelTo={t('range_to')} />
			<div class="row">
				<span class="muted small">{plural('photos', inRange.length)}</span>
				<span class="spacer"></span>
				{#if from > trip.start || to < trip.end}
					<button class="btn small" onclick={resetRange}>{t('whole_trip')}</button>
				{/if}
			</div>
			{#if inRange.length}
				<div class="strip">
					{#each inRange.slice(0, 30) as p, i (p.id)}
						<button onclick={() => openStrip(inRange, i)}><img src={thumbUrl(p.id)} alt="" loading="lazy" />{#if p.is_video}<span class="play" aria-label="Video">▶</span>{/if}</button>
					{/each}
				</div>
			{/if}
		</section>

		<section>
			<h3>{t('timeline')}</h3>
			{#if !timeline}
				<p class="muted">{t('loading')}</p>
			{:else}
				<ol class="timeline">
					{#each timeline as e, i (e.start)}
						{@const list = photosOf(e)}
						<li class={e.kind}>
							<button class="entry" onclick={() => showEntry(e)}>
								<span class="dot">{e.kind === 'stay' ? '⌂' : '➜'}</span>
								<span class="what">
									<strong>
										{#if e.kind === 'stay'}
											{e.title || e.place || t('stay')}
										{:else if e.kind === 'ongoing'}
											{t('on_the_road')}
										{:else}
											{t('drive')}{e.place ? ` · ${e.place}` : ''}
										{/if}
									</strong>
									<span class="muted">
										{date(e.start, { day: 'numeric', month: 'short' })}
										{#if e.kind === 'stay'}· {plural('nights', e.nights)}{/if}
										{#if e.distance_km >= 1}· {km(e.distance_km)}{/if}
										{#if e.photo_count}· {plural('photos', e.photo_count)}{/if}
									</span>
								</span>
							</button>
							{#if list.length}
								<div class="strip small">
									{#each list.slice(0, 8) as p, j (p.id)}
										<button onclick={() => openStrip(list, j)}><img src={thumbUrl(p.id)} alt="" loading="lazy" />{#if p.is_video}<span class="play" aria-label="Video">▶</span>{/if}</button>
									{/each}
									{#if list.length > 8}<button class="more" onclick={() => openStrip(list, 8)}>+{list.length - 8}</button>{/if}
								</div>
							{/if}
							{#if e.kind === 'stay'}
								{#if e.note_html}<NoteView html={e.note_html} />{/if}
								<div class="row">
									{#if e.lat !== null && e.lon !== null}
										<button class="btn small" onclick={() => (openPlace = openPlace === i ? null : i)}>
											{openPlace === i ? t('hide') : t('about_place')}
										</button>
									{/if}
									{#if canEdit() && e.day_key}
										<button
											class="btn small"
											onclick={() =>
												(editing = { kind: 'stay', dayKey: e.day_key!, title: e.title ?? '', html: e.note_html ?? '' })}
											>✎ {t('note')}</button
										>
									{/if}
								</div>
								{#if openPlace === i && e.lat !== null && e.lon !== null}
									<div class="place card"><PlaceCard lat={e.lat} lon={e.lon} /></div>
								{/if}
							{/if}
						</li>
					{/each}
				</ol>
			{/if}
		</section>
	{/if}
</div>

<style>
	.panel {
		padding: 12px 16px 24px;
	}
	.top {
		margin-bottom: 10px;
	}
	.cover {
		display: block;
		width: 100%;
		padding: 0;
		border: 0;
		background: none;
		cursor: zoom-in;
	}
	.cover img {
		width: 100%;
		aspect-ratio: 16 / 9;
		object-fit: cover;
		border-radius: var(--radius);
	}
	header {
		margin: 12px 0;
	}
	header h2 {
		margin-bottom: 0.2em;
	}
	header p {
		margin: 0 0 0.6em;
	}
	.live {
		color: var(--danger);
		margin-left: 0.4em;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 8px;
		text-align: center;
	}
	.stats div {
		background: var(--surface-2);
		border-radius: var(--radius-sm);
		padding: 8px 4px;
		font-size: 0.92em;
	}
	.countries {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin: 10px 0;
	}
	.countries .chip {
		cursor: default;
	}
	.edit {
		padding: 12px;
		margin: 12px 0;
		box-shadow: none;
	}
	.field-label {
		display: block;
		font-size: 0.85em;
		font-weight: 600;
		color: var(--text-2);
		margin-bottom: 0.3em;
	}
	.actions {
		margin-top: 10px;
	}
	section {
		margin-top: 18px;
	}
	.replay {
		background: var(--surface-2);
		border-radius: var(--radius);
		padding: 10px 12px;
	}
	.range-label {
		font-size: 0.85em;
	}
	.small {
		font-size: 0.85em;
	}
	.strip {
		display: flex;
		gap: 6px;
		overflow-x: auto;
		padding: 6px 0 2px;
		scrollbar-width: thin;
	}
	.strip button {
		position: relative;
		flex: none;
		padding: 0;
		border: 0;
		background: none;
		cursor: pointer;
	}
	.strip img {
		width: 64px;
		height: 64px;
		object-fit: cover;
		border-radius: 8px;
		display: block;
	}
	.strip.small img,
	/* videos: a play sign on the thumbnail */
	.play {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		color: #fff;
		font-size: 18px;
		text-shadow: 0 1px 4px rgb(0 0 0 / 70%);
		background: rgb(0 0 0 / 18%);
		border-radius: 8px;
		pointer-events: none;
	}
	.strip .more {
		width: 52px;
		height: 52px;
	}
	/* videos: a play sign on the thumbnail */
	.play {
		position: absolute;
		inset: 0;
		display: grid;
		place-items: center;
		color: #fff;
		font-size: 18px;
		text-shadow: 0 1px 4px rgb(0 0 0 / 70%);
		background: rgb(0 0 0 / 18%);
		border-radius: 8px;
		pointer-events: none;
	}
	.strip .more {
		border-radius: 8px;
		background: var(--surface-2);
		font-weight: 700;
	}
	.timeline {
		list-style: none;
		margin: 0;
		padding: 0;
		border-left: 2px solid var(--border);
		margin-left: 12px;
	}
	.timeline li {
		position: relative;
		padding: 0 0 14px 22px;
	}
	.entry {
		display: flex;
		gap: 10px;
		align-items: flex-start;
		width: 100%;
		text-align: left;
		background: none;
		border: 0;
		padding: 0;
		cursor: pointer;
	}
	.dot {
		position: absolute;
		left: -13px;
		top: 0;
		width: 24px;
		height: 24px;
		border-radius: 50%;
		display: grid;
		place-items: center;
		font-size: 13px;
		background: var(--surface);
		border: 2px solid var(--border);
	}
	.stay .dot {
		border-color: var(--accent);
		color: var(--accent);
	}
	.what {
		display: grid;
	}
	.what .muted {
		font-size: 0.86em;
	}
	.place {
		padding: 10px 12px;
		margin-top: 8px;
		box-shadow: none;
	}
	li .row {
		margin-top: 6px;
	}
</style>
