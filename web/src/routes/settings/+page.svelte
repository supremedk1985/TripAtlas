<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import AppHeader from '$lib/components/AppHeader.svelte';
	import ConnectionsForm from '$lib/components/settings/ConnectionsForm.svelte';
	import HouseholdForm from '$lib/components/settings/HouseholdForm.svelte';
	import ImportForm from '$lib/components/settings/ImportForm.svelte';
	import ProfileForm from '$lib/components/settings/ProfileForm.svelte';
	import TrackersForm from '$lib/components/settings/TrackersForm.svelte';
	import StatusPanel from '$lib/components/settings/StatusPanel.svelte';
	import UsersForm from '$lib/components/settings/UsersForm.svelte';
	import { t } from '$lib/i18n/index.svelte';
	import { isAdmin } from '$lib/stores/session.svelte';

	const tabs = $derived(
		[
			{ id: 'profile', label: 'tab_profile', admin: false },
			{ id: 'import', label: 'tab_import', admin: false },
			{ id: 'trackers', label: 'tab_trackers', admin: true },
			{ id: 'users', label: 'tab_users', admin: true },
			{ id: 'household', label: 'tab_household', admin: true },
			{ id: 'connections', label: 'tab_connections', admin: true },
			{ id: 'status', label: 'tab_status', admin: true }
		].filter((x) => !x.admin || isAdmin())
	);
	const tab = $derived(page.url.searchParams.get('tab') ?? 'profile');

</script>

<div class="page">
	<AppHeader />
	<h1>{t('nav_settings')}</h1>
	<div class="tabs row">
		{#each tabs as x (x.id)}
			<button class="chip" class:on={tab === x.id} onclick={() => goto(`?tab=${x.id}`, { replaceState: true, noScroll: true })}>
				{t(x.label as Parameters<typeof t>[0])}
			</button>
		{/each}
	</div>
	<div class="card body">
		{#if tab === 'profile'}<ProfileForm />
		{:else if tab === 'import'}<ImportForm />
		{:else if tab === 'trackers'}<TrackersForm />
		{:else if tab === 'users'}<UsersForm />
		{:else if tab === 'household'}<HouseholdForm />
		{:else if tab === 'connections'}<ConnectionsForm />
		{:else if tab === 'status'}<StatusPanel />
		{/if}
	</div>
</div>

<style>
	.page {
		max-width: 860px;
		margin: 0 auto;
		padding: 12px 16px 40px;
	}
	h1 {
		margin: 22px 0 12px;
	}
	.tabs {
		margin-bottom: 14px;
	}
	.body {
		padding: 20px;
		box-shadow: none;
	}
</style>
