<template>
	<FormDialog :name="t('Settings')" @submit="submit" @close="$emit('close')">
		<NcTextField v-if="includeName" v-model="form.title" :label="t('Name')" required />
		<SelectField v-model="form.mode" :options="modeOptions" :label="t('Playback mode')" />
		<SelectField
			v-if="form.mode !== 'audio'"
			v-model="form.quality"
			:options="qualityOptions"
			:label="t('Video quality')" />
		<SelectField v-model="form.audio_quality" :options="audioOptions" :label="t('Audio quality')" />
		<SelectField
			v-if="includeHistory"
			v-model="form.history_limit"
			:options="historyOptions"
			:label="t('History limit')" />
	</FormDialog>
</template>

<script setup>
import NcTextField from '@nextcloud/vue/components/NcTextField'
import { reactive } from 'vue'
import { send } from '../api.js'
import { t } from '../i18n.js'
import { notify, notifyError } from '../notify.js'
import { state } from '../store.js'
import FormDialog from './FormDialog.vue'
import SelectField from './SelectField.vue'

const props = defineProps({
	item: { type: Object, required: true },
	/** One of `channel`, `playlist` or `video`. */
	type: { type: String, required: true },
})
const emit = defineEmits(['saved', 'close'])

const INHERIT = 'inherit'
const personal = state.bootstrap.personal_settings
const inherited = props.item.inherited || {
	mode: personal.default_mode,
	quality: personal.default_quality,
	audio_quality: personal.default_audio_quality,
}
const includeHistory = props.type === 'channel' || (props.type === 'playlist' && props.item.kind === 'youtube')
const includeName = props.type === 'playlist' && props.item.kind !== 'youtube'

const inheritLabel = (value) => t('Inherit ({value})', { value })
const inheritedQuality = inherited.quality === 'best' ? t('Best available') : `${inherited.quality}p`
const historyLabel = personal.history_limit ? String(personal.history_limit) : t('Unlimited')

const modeOptions = [
	{ id: INHERIT, label: inheritLabel(inherited.mode === 'audio' ? t('Audio only') : t('Video')) },
	{ id: 'video', label: t('Video') },
	{ id: 'audio', label: t('Audio only') },
]
const qualityOptions = [
	{ id: INHERIT, label: inheritLabel(inheritedQuality) },
	...['360', '480', '720', '1080'].map((value) => ({ id: value, label: `${value}p` })),
	{ id: 'best', label: t('Best available') },
]
const audioOptions = [
	{ id: INHERIT, label: inheritLabel(`${inherited.audio_quality || 128} kbps`) },
	...['64', '96', '128', '192', '256'].map((value) => ({ id: value, label: `${value} kbps` })),
]
const historyOptions = [
	{ id: INHERIT, label: inheritLabel(historyLabel) },
	{ id: '0', label: t('Unlimited') },
	...['10', '25', '50', '100', '250'].map((value) => ({ id: value, label: value })),
]

const valueOf = (value) => (value === null || value === undefined ? INHERIT : String(value))
const form = reactive({
	title: props.item.title || '',
	mode: valueOf(props.item.mode),
	quality: valueOf(props.item.quality),
	audio_quality: valueOf(props.item.audio_quality),
	history_limit: valueOf(props.item.history_limit),
})

async function submit() {
	const nullable = (value) => (value === INHERIT ? null : value)
	const values = {
		mode: nullable(form.mode),
		quality: form.mode === 'audio' ? null : nullable(form.quality),
		audio_quality: nullable(form.audio_quality),
	}
	if (includeName) {
		values.title = form.title
	}
	if (includeHistory) {
		values.history_limit = nullable(form.history_limit)
	}
	const path = { channel: 'channels', playlist: 'playlists', video: 'videos' }[props.type]
	try {
		await send('PUT', `api/${path}/${props.item.id}`, values)
		notify(t('Settings saved'))
		emit('saved')
	} catch (error) {
		notifyError(error)
	}
}
</script>
