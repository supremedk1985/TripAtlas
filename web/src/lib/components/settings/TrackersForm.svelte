<script lang="ts">
	// Trackers: link Traccar devices, create empty trackers for imports, colour, photo priority, avatar.
	import ImportKey from './ImportKey.svelte';
	import { api, errorText } from '$lib/api';
	import { dateTime } from '$lib/format';
	import { i18n, t } from '$lib/i18n/index.svelte';
	import { confirmDialog } from '$lib/stores/dialog.svelte';
	import type { Tracker } from '$lib/types';

	type Device = { id: number; name: string; status: string; tracker_id: number | null };

	let trackers = $state<Tracker[]>([]);
	let devices = $state<Device[] | null>(null);
	let devicesError = $state('');
	let newName = $state('');
	let error = $state('');

	const COLORS = ['#e4572e', '#3b82f6', '#76b041', '#7e5bef', '#ffc914', '#17bebb', '#ef476f'];

	async function load() {
		trackers = await api.get<Tracker[]>('/api/trackers');
		api
			.get<Device[]>('/api/settings/traccar/devices')
			.then((d) => (devices = d))
			.catch((e) => {
				devices = [];
				devicesError = e.message;
			});
	}
	load();

	async function add(name: string, deviceId: number | null) {
		error = '';
		try {
			await api.post('/api/trackers', {
				name,
				traccar_device_id: deviceId,
				color: COLORS[trackers.length % COLORS.length]
			});
			newName = '';
			await load();
		} catch (e) {
			error = errorText(e);
		}
	}

	async function update(tk: Tracker, patch: Partial<Tracker>) {
		await api.patch(`/api/trackers/${tk.id}`, patch);
		Object.assign(tk, patch);
	}

	async function remove(tk: Tracker) {
		if (!(await confirmDialog(t('tracker_delete_confirm', { name: tk.name }), { danger: true, confirmLabel: t('delete') })))
			return;
		await api.del(`/api/trackers/${tk.id}`);
		await load();
	}

	async function avatar(tk: Tracker, files: FileList | null) {
		if (!files?.[0]) return;
		const form = new FormData();
		form.append('file', files[0]);
		try {
			await api.put(`/api/trackers/${tk.id}/avatar`, form);
			tk.has_avatar = true;
			avatarVersion++;
		} catch (e) {
			error = errorText(e);
		}
	}
	let avatarVersion = $state(0);
</script>

{#if trackers.length}
	<ul class="trackers">
		{#each trackers as tk (tk.id)}
			<li class="card">
				<label class="avatar" style="--c:{tk.color}" title={t('avatar_upload')}>
					{#if tk.has_avatar}<img src="/api/trackers/{tk.id}/avatar?v={avatarVersion}" alt="" />{:else}{tk.name.slice(0, 1)}{/if}
					<input type="file" accept="image/png,image/jpeg,image/webp" hidden onchange={(e) => avatar(tk, e.currentTarget.files)} />
				</label>
				<div class="body">
					<input type="text" value={tk.name} onchange={(e) => update(tk, { name: e.currentTarget.value })} aria-label={t('name')} />
					<div class="row small">
						<select value={tk.kind} onchange={(e) => update(tk, { kind: e.currentTarget.value as Tracker['kind'] })} aria-label={t('tracker_kind')} title={t('tracker_kind_hint')}>
							<option value="vehicle">{t('tracker_kind_vehicle')}</option>
							<option value="camper">{t('tracker_kind_camper')}</option>
							<option value="bike">{t('tracker_kind_bike')}</option>
							<option value="person">{t('tracker_kind_person')}</option>
						</select>
						<label class="row">{t('color')} <input type="color" value={tk.color} onchange={(e) => update(tk, { color: e.currentTarget.value })} /></label>
						<label class="row" title={t('photo_priority_hint')}>
							{t('photo_priority')} <span class="help" aria-hidden="true">?</span>
							<input class="num" type="number" min="0" max="100" value={tk.photo_priority} onchange={(e) => update(tk, { photo_priority: Number(e.currentTarget.value) })} />
						</label>
						<span class="muted">
							{tk.traccar_device_id ? `Traccar #${tk.traccar_device_id}` : t('import_only')} ·
							{(tk.position_count ?? 0).toLocaleString(i18n.locale)} {t('positions')}
							{#if tk.last}· {t('last_seen', { when: dateTime(tk.last) })}{/if}
						</span>
					</div>
				</div>
				<button class="btn small danger" onclick={() => remove(tk)}>{t('delete')}</button>
				<!-- under the card over its whole width: on a phone the middle column is too narrow for sentences -->
				<div class="extra">
					{#if tk.kind === 'bike'}
						<label class="check small">
							<input type="checkbox" checked={tk.hide_empty_day_trips} onchange={(e) => update(tk, { hide_empty_day_trips: e.currentTarget.checked })} />
							<span>{t('hide_empty_day_trips')}</span>
						</label>
					{/if}
					<ImportKey tracker={tk} />
				</div>
			</li>
		{/each}
	</ul>
{/if}

<h4>{t('add_tracker')}</h4>
{#if devices === null}
	<p class="muted">{t('loading')}</p>
{:else if devices.length}
	<p class="muted">{t('traccar_devices')}</p>
	<div class="row">
		{#each devices as d (d.id)}
			<button class="chip" disabled={d.tracker_id !== null} onclick={() => add(d.name, d.id)}>
				{d.tracker_id !== null ? '✓' : '+'} {d.name}
			</button>
		{/each}
	</div>
{:else if devicesError}
	<p class="muted small">{t('traccar_not_connected')}</p>
{/if}
<form class="row manual" onsubmit={(e) => (e.preventDefault(), newName && add(newName, null))}>
	<input type="text" bind:value={newName} placeholder={t('tracker_manual_placeholder')} />
	<button class="btn">{t('add')}</button>
</form>
{#if error}<p class="error">{error}</p>{/if}

<style>
	.extra {
		flex-basis: 100%;
		border-top: 1px solid var(--border);
		padding-top: 8px;
	}
	.check {
		display: flex;
		align-items: flex-start;
		gap: 8px;
	}
	.check input {
		margin-top: 2px;
		flex: none;
	}
	.trackers {
		list-style: none;
		padding: 0;
		margin: 0 0 16px;
		display: grid;
		gap: 10px;
	}
	li {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 12px;
		padding: 10px 12px;
		box-shadow: none;
	}
	.avatar {
		width: 52px;
		height: 52px;
		flex: none;
		border-radius: 50%;
		display: grid;
		place-items: center;
		background: var(--c);
		color: #fff;
		font-weight: 700;
		font-size: 1.3em;
		cursor: pointer;
		overflow: hidden;
		border: 3px solid var(--c);
	}
	.avatar img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.body {
		flex: 1;
		min-width: 0;
		display: grid;
		gap: 6px;
	}
	.small {
		font-size: 0.86em;
	}
	.num {
		width: 4.5em;
		padding: 0.2em 0.4em;
	}
	input[type='color'] {
		width: 2em;
		height: 1.6em;
		padding: 0;
		border: 0;
		background: none;
	}
	.manual {
		margin-top: 12px;
		flex-wrap: nowrap;
	}
	.help {
		display: inline-grid;
		place-items: center;
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background: var(--surface-2);
		font-size: 11px;
		cursor: help;
	}
</style>
