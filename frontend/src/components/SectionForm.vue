<template>
	<form class="lucarne-section-form" @submit.prevent="$emit('submit')">
		<slot />
		<FormActions :dirty="dirty" @cancel="$emit('cancel')" />
	</form>
</template>

<script setup>
import FormActions from './FormActions.vue'

defineProps({
	/** Whether the fields differ from the saved values. */
	dirty: { type: Boolean, required: true },
})
defineEmits(['submit', 'cancel'])
</script>

<style scoped>
/* Fields share the whole width, in as many columns as it allows. */
.lucarne-section-form {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(min(320px, 100%), 1fr));
	gap: calc(var(--default-grid-baseline) * 4);
	align-items: start;
}
</style>
