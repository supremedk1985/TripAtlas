<script lang="ts">
	// User management: roles, which trackers each user sees, live access, password reset.
	import { api, errorText } from '$lib/api';
	import { LANGUAGES, t } from '$lib/i18n/index.svelte';
	import { confirmDialog, promptDialog } from '$lib/stores/dialog.svelte';
	import { session, setUser } from '$lib/stores/session.svelte';
	import AvatarPicker from '$lib/components/AvatarPicker.svelte';
	import type { Role, Tracker, User } from '$lib/types';

	let users = $state<User[]>([]);
	let trackers = $state<Tracker[]>([]);
	let error = $state('');
	let saved = $state('');
	let form = $state(blank());

	function blank() {
		return { username: '', display_name: '', password: '', role: 'member' as Role, locale: session.user?.locale ?? 'en', tracker_ids: [] as number[] };
	}

	async function load() {
		[users, trackers] = await Promise.all([api.get<User[]>('/api/users'), api.get<Tracker[]>('/api/trackers')]);
	}
	load();

	async function create(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		try {
			await api.post('/api/users', form);
			form = blank();
			await load();
		} catch (err) {
			error = errorText(err);
		}
	}

	async function patch(u: User, body: Record<string, unknown>) {
		error = '';
		try {
			Object.assign(u, await api.patch<User>(`/api/users/${u.id}`, body));
		} catch (err) {
			error = errorText(err);
			await load();
		}
	}

	function toggleTracker(u: User, id: number) {
		const ids = u.tracker_ids.includes(id) ? u.tracker_ids.filter((x) => x !== id) : [...u.tracker_ids, id];
		patch(u, { tracker_ids: ids });
	}

	async function resetPassword(u: User) {
		const pw = await promptDialog(t('new_password_for', { name: u.display_name }), {
			inputType: 'password',
			minLength: 8,
			confirmLabel: t('save')
		});
		if (pw) {
			await patch(u, { password: pw });
			if (!error) saved = t('password_set', { name: u.display_name });
		}
	}

	async function remove(u: User) {
		if (!(await confirmDialog(t('user_delete_confirm', { name: u.display_name }), { danger: true, confirmLabel: t('delete') })))
			return;
		await api.del(`/api/users/${u.id}`);
		await load();
	}

	const roles: Role[] = ['admin', 'member', 'child'];
</script>

{#if saved}<p class="success">{saved}</p>{/if}
<ul class="users">
	{#each users as u (u.id)}
		<li class="card">
			<div class="row head">
				<AvatarPicker user={u} path="/api/users/{u.id}/avatar" size={40} compact
					onchange={(n) => (Object.assign(u, n), u.id === session.user?.id && setUser(n))} />
				<strong>{u.display_name}</strong>
				<span class="muted">@{u.username}</span>
				<span class="spacer"></span>
				<select value={u.role} onchange={(e) => patch(u, { role: e.currentTarget.value })} aria-label={t('role')}>
					{#each roles as r (r)}<option value={r}>{t(`role_${r}`)}</option>{/each}
				</select>
			</div>
			{#if u.role !== 'admin'}
				<div class="row">
					<span class="muted small">{t('sees_trackers')}:</span>
					{#each trackers as tk (tk.id)}
						<button class="chip" class:on={u.tracker_ids.includes(tk.id)} onclick={() => toggleTracker(u, tk.id)}>{tk.name}</button>
					{/each}
				</div>
			{/if}
			<div class="row small">
				<label class="row"><input type="checkbox" checked={u.can_see_live} onchange={(e) => patch(u, { can_see_live: e.currentTarget.checked })} /> {t('can_see_live')}</label>
				<span class="spacer"></span>
				<button class="btn small" onclick={() => resetPassword(u)}>{t('reset_password')}</button>
				{#if u.id !== session.user?.id}<button class="btn small danger" onclick={() => remove(u)}>{t('delete')}</button>{/if}
			</div>
			{#if u.role === 'child'}<p class="muted small hint">{t('child_hint')}</p>{/if}
		</li>
	{/each}
</ul>

<h4>{t('add_user')}</h4>
<form onsubmit={create} class="new card">
	<div class="grid">
		<label class="field"><span>{t('display_name')}</span><input type="text" bind:value={form.display_name} required /></label>
		<label class="field"><span>{t('username')}</span><input type="text" bind:value={form.username} pattern="[A-Za-z0-9._\-]+" required autocapitalize="none" /></label>
		<label class="field"><span>{t('password')}</span><input type="password" bind:value={form.password} minlength="8" required autocomplete="new-password" /></label>
		<label class="field">
			<span>{t('role')}</span>
			<select bind:value={form.role}>{#each roles as r (r)}<option value={r}>{t(`role_${r}`)}</option>{/each}</select>
		</label>
		<label class="field">
			<span>{t('language')}</span>
			<select bind:value={form.locale}>{#each LANGUAGES as l (l.code)}<option value={l.code}>{l.name}</option>{/each}</select>
		</label>
	</div>
	{#if form.role !== 'admin'}
		<div class="row">
			<span class="muted small">{t('sees_trackers')}:</span>
			{#each trackers as tk (tk.id)}
				<label class="chip" class:on={form.tracker_ids.includes(tk.id)}>
					<input type="checkbox" hidden value={tk.id} bind:group={form.tracker_ids} />{tk.name}
				</label>
			{/each}
		</div>
	{/if}
	{#if error}<p class="error">{error}</p>{/if}
	<button class="btn primary">{t('add')}</button>
</form>

<style>
	.users {
		list-style: none;
		padding: 0;
		margin: 0 0 16px;
		display: grid;
		gap: 10px;
	}
	li {
		padding: 12px;
		display: grid;
		gap: 8px;
		box-shadow: none;
	}
	.head select {
		width: auto;
	}
	.small {
		font-size: 0.86em;
	}
	.hint {
		margin: 0;
	}
	.new {
		padding: 14px;
		box-shadow: none;
		display: grid;
		gap: 10px;
		justify-items: start;
	}
	.grid {
		width: 100%;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
		gap: 0 12px;
	}
</style>
