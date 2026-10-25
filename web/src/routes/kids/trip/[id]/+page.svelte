<script lang="ts">
	// A trip told as a story for children (lib/components/TripStory.svelte, child-friendly texts).
	import { page } from '$app/state';
	import TripStory from '$lib/components/TripStory.svelte';
	import { t } from '$lib/i18n/index.svelte';
</script>

<TripStory id={Number(page.params.id)} kids back={{ href: '/kids', label: t('kids_back') }} />
