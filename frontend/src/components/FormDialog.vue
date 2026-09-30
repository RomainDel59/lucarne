<template>
	<NcDialog
		v-model:open="open"
		:name="name"
		size="small"
		is-form
		:buttons="buttons"
		@closing="onClosing">
		<div class="lucarne-form-dialog">
			<slot />
		</div>
	</NcDialog>
</template>

<script setup>
import NcDialog from '@nextcloud/vue/components/NcDialog'
import { computed, ref, watch } from 'vue'
import { t } from '../i18n.js'

const props = defineProps({
	name: { type: String, required: true },
	submitLabel: { type: String, default: '' },
	danger: { type: Boolean, default: false },
})
const emit = defineEmits(['submit', 'close'])

const open = ref(true)
const SUBMITTED = 'submitted'

// The dialog closes itself when a button is pressed and reports the value returned by
// the button callback, so the submission is handled when it closes.
const buttons = computed(() => [
	{ label: t('Cancel'), variant: 'tertiary' },
	{
		label: props.submitLabel || t('Save'),
		type: 'submit',
		variant: props.danger ? 'error' : 'primary',
		callback: () => SUBMITTED,
	},
])

function onClosing(result) {
	if (result === SUBMITTED) {
		emit('submit')
	}
}

// Once the closing transition is over, let the parent remove the dialog.
watch(open, (value) => {
	if (!value) {
		emit('close')
	}
})
</script>

<style scoped>
.lucarne-form-dialog {
	display: flex;
	flex-direction: column;
	gap: calc(var(--default-grid-baseline) * 3);
	padding-block-end: calc(var(--default-grid-baseline) * 2);
}
</style>
