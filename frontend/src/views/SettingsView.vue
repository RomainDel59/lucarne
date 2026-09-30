<template>
	<div class="lucarne-page">
		<PageHeader :title="t('Settings')" />
		<NcLoadingIcon v-if="loading && !data" :size="44" />
		<NcEmptyContent v-else-if="error" :name="t('Something went wrong')" :description="error.message">
			<template #icon>
				<AlertCircleIcon />
			</template>
		</NcEmptyContent>
		<PageSection
			v-else-if="data"
			:name="t('Playback and collection')"
			:description="t('Defaults inherited by channels, playlists and videos.')">
			<SectionForm :dirty="dirty" @submit="save" @cancel="reset">
				<SelectField v-model="form.default_mode" :options="modeOptions" :label="t('Playback mode')" />
				<SelectField
					v-if="form.default_mode !== 'audio'"
					v-model="form.default_quality"
					:options="qualityOptions"
					:label="t('Video quality')" />
				<SelectField v-model="form.default_audio_quality" :options="audioOptions" :label="t('Audio quality')" />
				<NcTextField
					v-model="form.history_limit"
					type="number"
					min="0"
					max="100000"
					required
					:label="t('History limit')"
					:helper-text="t('Use 0 for no limit. Channel and playlist settings take priority.')" />
			</SectionForm>
		</PageSection>
	</div>
</template>

<script setup>
import NcEmptyContent from '@nextcloud/vue/components/NcEmptyContent'
import NcLoadingIcon from '@nextcloud/vue/components/NcLoadingIcon'
import NcTextField from '@nextcloud/vue/components/NcTextField'
import { computed, reactive, watch } from 'vue'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import { request, send } from '../api.js'
import PageHeader from '../components/PageHeader.vue'
import PageSection from '../components/PageSection.vue'
import SectionForm from '../components/SectionForm.vue'
import SelectField from '../components/SelectField.vue'
import { useAsync } from '../composables/useAsync.js'
import { t } from '../i18n.js'
import { notify, notifyError } from '../notify.js'
import { state } from '../store.js'

const form = reactive({ default_mode: 'video', default_quality: '720', default_audio_quality: '128', history_limit: '0' })

const modeOptions = [
	{ id: 'video', label: t('Video') },
	{ id: 'audio', label: t('Audio only') },
]
const qualityOptions = [
	...['360', '480', '720', '1080'].map((value) => ({ id: value, label: `${value}p` })),
	{ id: 'best', label: t('Best available') },
]
const audioOptions = ['96', '128', '192', '256'].map((value) => ({ id: value, label: `${value} kbps` }))

const { data, loading, error } = useAsync(() => request('api/settings/personal'), () => 'personal')

function reset() {
	const values = data.value
	if (values) {
		form.default_mode = values.default_mode
		form.default_quality = String(values.default_quality)
		form.default_audio_quality = String(values.default_audio_quality)
		form.history_limit = String(values.history_limit)
	}
}

watch(data, reset, { immediate: true })

const dirty = computed(() => Boolean(data.value) && (
	form.default_mode !== data.value.default_mode
	|| form.default_quality !== String(data.value.default_quality)
	|| form.default_audio_quality !== String(data.value.default_audio_quality)
	|| form.history_limit !== String(data.value.history_limit)
))

async function save() {
	try {
		await send('PUT', 'api/settings/personal', {
			default_mode: form.default_mode,
			default_quality: form.default_quality,
			default_audio_quality: form.default_audio_quality,
			history_limit: Number(form.history_limit),
		})
		state.bootstrap.personal_settings = await request('api/settings/personal')
		data.value = state.bootstrap.personal_settings
		notify(t('Settings saved'))
	} catch (failure) {
		notifyError(failure)
	}
}
</script>
