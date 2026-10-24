<script lang="ts">
	// Trackers: link Traccar devices, create empty trackers for imports, colour, photo priority, avatar.
	import { api } from '$lib/api';
	import { t } from '$lib/i18n/index.svelte';
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
			error = (e as Error).message;
		}
	}

	async function update(tk: Tracker, patch: Partial<Tracker>) {
		await api.patch(`/api/trackers/${tk.id}`, patch);
		Object.assign(tk, patch);
	}

	async function remove(tk: Tracker) {
		if (!confirm(t('tracker_delete_confirm', { name: tk.name }))) return;
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
			error = (e as Error).message;
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
						<label class="row">{t('color')} <input type="color" value={tk.color} onchange={(e) => update(tk, { color: e.currentTarget.value })} /></label>
						<label class="row" title={t('photo_priority_hint')}>
							{t('photo_priority')}
							<input class="num" type="number" min="0" max="100" value={tk.photo_priority} onchange={(e) => update(tk, { photo_priority: Number(e.currentTarget.value) })} />
						</label>
						<span class="muted">
							{tk.traccar_device_id ? `Traccar #${tk.traccar_device_id}` : t('import_only')} ·
							{(tk.position_count ?? 0).toLocaleString()} {t('positions')}
						</span>
					</div>
				</div>
				<button class="btn small danger" onclick={() => remove(tk)}>{t('delete')}</button>
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
	.trackers {
		list-style: none;
		padding: 0;
		margin: 0 0 16px;
		display: grid;
		gap: 10px;
	}
	li {
		display: flex;
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
</style>
