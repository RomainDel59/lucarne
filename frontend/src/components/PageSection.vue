<template>
	<section class="lucarne-section">
		<h3 class="lucarne-section__name">
			{{ name }}
		</h3>
		<p v-if="description" class="lucarne-section__description">
			{{ description }}
		</p>
		<slot />
	</section>
</template>

<script setup>
defineProps({
	name: { type: String, required: true },
	description: { type: String, default: '' },
})
</script>

<style scoped>
/* Same look as a Nextcloud settings section, but using the whole width of the page. */
.lucarne-section__name {
	margin-block-start: 0;
}

.lucarne-section__description {
	margin-block: calc(var(--default-grid-baseline) * -1) calc(var(--default-grid-baseline) * 4);
	color: var(--color-text-maxcontrast);
}
</style>
