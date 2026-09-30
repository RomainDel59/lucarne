<template>
	<NcDialog
		v-model:open="open"
		:name="title"
		size="small"
		:buttons="buttons"
		@closing="onClosing">
		<p v-if="message" class="lucarne-confirm__message">
			{{ message }}
		</p>
		<NcCheckboxRadioSwitch v-if="checkboxLabel" v-model="checked">
			{{ checkboxLabel }}
		</NcCheckboxRadioSwitch>
	</NcDialog>
</template>

<script setup>
import NcCheckboxRadioSwitch from '@nextcloud/vue/components/NcCheckboxRadioSwitch'
import NcDialog from '@nextcloud/vue/components/NcDialog'
import { computed, ref } from 'vue'
import { t } from '../i18n.js'

const props = defineProps({
	title: { type: String, required: true },
	message: { type: String, default: '' },
	submit: { type: String, default: '' },
	cancel: { type: String, default: '' },
	danger: { type: Boolean, default: false },
	checkboxLabel: { type: String, default: '' },
})
const emit = defineEmits(['finish'])

const open = ref(true)
const checked = ref(false)
const buttons = computed(() => [
	{ label: props.cancel || t('Cancel'), variant: 'tertiary' },
	{
		label: props.submit || t('Yes'),
		variant: props.danger ? 'error' : 'primary',
		callback: () => ({ confirmed: true, checked: checked.value }),
	},
])

function onClosing(result) {
	emit('finish', result?.confirmed ? result : { confirmed: false, checked: false })
}
</script>

<style scoped>
.lucarne-confirm__message {
	margin-block-end: calc(var(--default-grid-baseline) * 2);
}
</style>
