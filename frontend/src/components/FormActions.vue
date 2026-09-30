<template>
	<div class="lucarne-form-actions">
		<NcButton variant="tertiary" :disabled="!dirty" @click="$emit('cancel')">
			{{ t('Cancel') }}
		</NcButton>
		<NcButton type="submit" variant="primary" :disabled="!dirty">
			{{ t('Save') }}
		</NcButton>
	</div>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import { t } from '../i18n.js'

defineProps({
	/** Whether the fields differ from the saved values. */
	dirty: { type: Boolean, required: true },
})
defineEmits(['cancel'])
</script>

<style scoped>
/* Buttons at the end, like in the Nextcloud dialogs. */
.lucarne-form-actions {
	display: flex;
	grid-column: 1 / -1;
	justify-content: flex-end;
	gap: calc(var(--default-grid-baseline) * 2);
}
</style>
