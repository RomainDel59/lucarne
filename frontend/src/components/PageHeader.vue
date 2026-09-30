<template>
	<div class="lucarne-page-header">
		<h2 class="lucarne-page-header__title" :title="title">
			{{ title }}
		</h2>
		<div class="lucarne-page-header__actions">
			<slot />
		</div>
	</div>
</template>

<script setup>
defineProps({
	title: { type: String, required: true },
})
</script>

<style scoped>
.lucarne-page-header {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	justify-content: space-between;
	gap: calc(var(--default-grid-baseline) * 2);
	min-height: var(--default-clickable-area);
	margin-block-end: calc(var(--default-grid-baseline) * 4);
}

.lucarne-page-header__title {
	flex: 1 1 0;
	min-width: 0;
	margin: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.lucarne-page-header__actions {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: calc(var(--default-grid-baseline) * 2);
}
</style>
