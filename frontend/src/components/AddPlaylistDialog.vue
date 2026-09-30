<template>
	<FormDialog :name="t('Add a playlist')" :submit-label="t('Add')" @submit="submit" @close="$emit('close')">
		<SelectField v-model="kind" :options="kinds" :label="t('Type')" />
		<NcTextField
			v-model="value"
			:label="imported ? t('YouTube playlist URL') : t('Name')"
			:type="imported ? 'url' : 'text'"
			:helper-text="imported ? t('Playlist history is collected progressively and follows your personal history limit.') : ''"
			required />
	</FormDialog>
</template>

<script setup>
import NcTextField from '@nextcloud/vue/components/NcTextField'
import { computed, ref } from 'vue'
import { send } from '../api.js'
import { t } from '../i18n.js'
import { notify, notifyError } from '../notify.js'
import FormDialog from './FormDialog.vue'
import SelectField from './SelectField.vue'

const emit = defineEmits(['added', 'close'])

const kind = ref('personal')
const value = ref('')
const kinds = [
	{ id: 'personal', label: t('Personal playlist') },
	{ id: 'youtube', label: t('YouTube playlist') },
]
const imported = computed(() => kind.value === 'youtube')

async function submit() {
	try {
		if (imported.value) {
			await send('POST', 'api/playlists/import', { url: value.value })
		} else {
			await send('POST', 'api/playlists', { title: value.value })
		}
		notify(t('Playlist added'))
		emit('added')
	} catch (error) {
		notifyError(error)
	}
}
</script>
