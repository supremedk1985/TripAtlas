<script lang="ts">
	// One trip in the diary (lib/components/TripStory.svelte).
	import { page } from '$app/state';
	import TripStory from '$lib/components/TripStory.svelte';
	import { t } from '$lib/i18n/index.svelte';
</script>

<TripStory id={Number(page.params.id)} back={{ href: '/diary', label: t('diary_all') }} />
