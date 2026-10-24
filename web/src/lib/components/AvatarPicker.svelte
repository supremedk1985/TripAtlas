<script lang="ts">
	// Choose, change or remove a profile picture. `path` is /api/auth/me/avatar or /api/users/<id>/avatar.
	import { api, errorText } from '$lib/api';
	import { avatarUrl } from '$lib/avatar';
	import { t } from '$lib/i18n/index.svelte';
	import type { User } from '$lib/types';
	import Avatar from './Avatar.svelte';
	import AvatarCropper from './AvatarCropper.svelte';

	let {
		user,
		path,
		size = 64,
		compact = false,
		onchange
	}: {
		user: User;
		path: string;
		size?: number;
		/** only the picture (tap to choose) and a small × to remove — for lists */
		compact?: boolean;
		onchange: (u: User) => void;
	} = $props();

	let input: HTMLInputElement | undefined = $state();
	let busy = $state(false);
	let error = $state('');
	let cropping = $state<File | null>(null);

	function chosen(e: Event) {
		const file = (e.currentTarget as HTMLInputElement).files?.[0];
		(e.currentTarget as HTMLInputElement).value = '';
		error = '';
		if (file) cropping = file;
	}

	async function upload(jpeg: Blob) {
		cropping = null;
		busy = true;
		try {
			onchange(await api.put<User>(path, jpeg));
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}

	async function remove() {
		error = '';
		try {
			onchange(await api.del<User>(path));
		} catch (err) {
			error = errorText(err);
		}
	}
</script>

<div class="picker">
	<button type="button" class="pic" onclick={() => input?.click()} disabled={busy} aria-label={t('avatar_choose')}
		title={t('avatar_choose')}>
		<Avatar name={user.display_name} src={avatarUrl(user)} {size} />
	</button>
	{#if compact && user.avatar_version}
		<button type="button" class="x" onclick={remove} aria-label={t('avatar_remove')} title={t('avatar_remove')}>×</button>
	{/if}
	{#if !compact}<div class="actions">
		<button type="button" class="btn small" onclick={() => input?.click()} disabled={busy}>
			{user.avatar_version ? t('avatar_change') : t('avatar_choose')}
		</button>
		{#if user.avatar_version}<button type="button" class="btn small danger" onclick={remove}>{t('remove')}</button>{/if}
	</div>{/if}
	<input bind:this={input} type="file" accept="image/*" hidden onchange={chosen} />
	{#if error}<p class="error">{error}</p>{/if}
</div>

{#if cropping}
	{#key cropping}
		<AvatarCropper file={cropping} ondone={upload} oncancel={() => (cropping = null)} />
	{/key}
{/if}

<style>
	.picker {
		position: relative;
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
	}
	.pic {
		padding: 0;
		border: 0;
		background: none;
		cursor: pointer;
		border-radius: 50%;
	}
	.x {
		position: absolute;
		left: calc(100% - 14px);
		top: -4px;
		width: 18px;
		height: 18px;
		border-radius: 50%;
		border: 0;
		padding: 0;
		background: var(--surface-2);
		color: var(--text-2);
		line-height: 1;
		cursor: pointer;
	}
	.actions {
		display: flex;
		gap: 6px;
	}
	.error {
		flex-basis: 100%;
		margin: 0;
	}
</style>
