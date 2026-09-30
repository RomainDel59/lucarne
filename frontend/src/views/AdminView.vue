<template>
	<div class="lucarne-page">
		<PageHeader :title="t('Administration')" />
		<NcLoadingIcon v-if="loading && !data" :size="44" />
		<NcEmptyContent v-else-if="error" :name="t('Something went wrong')" :description="error.message">
			<template #icon>
				<AlertCircleIcon />
			</template>
		</NcEmptyContent>
		<NcSettingsSection
			v-else-if="data"
			:name="t('Collection agent')"
			:description="t('Control the pace of automatic YouTube requests and temporary media retention.')">
			<form class="lucarne-settings-form" @submit.prevent="save">
				<NcTextField
					v-model="form.batch_size"
					type="number"
					min="5"
					max="50"
					required
					:label="t('Videos per batch')"
					:helper-text="t('Large batches increase the risk of temporary YouTube rate limits.')" />
				<SelectField v-model="form.lot_wait_seconds" :options="waitOptions" :label="t('Delay between batches')" />
				<SelectField v-model="form.campaign_duration_seconds" :options="durationOptions" :label="t('Maximum campaign time')" />
				<NcTextField
					v-model="form.temporary_retention_days"
					type="number"
					min="1"
					max="365"
					required
					:label="t('Temporary media retention (days)')"
					:helper-text="t('The duration restarts after each playback. Quality variants remain separate.')" />
				<div>
					<NcButton type="submit" variant="primary">
						{{ t('Save') }}
					</NcButton>
				</div>
			</form>
		</NcSettingsSection>
	</div>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import NcEmptyContent from '@nextcloud/vue/components/NcEmptyContent'
import NcLoadingIcon from '@nextcloud/vue/components/NcLoadingIcon'
import NcSettingsSection from '@nextcloud/vue/components/NcSettingsSection'
import NcTextField from '@nextcloud/vue/components/NcTextField'
import { reactive, watch } from 'vue'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import { request, send } from '../api.js'
import PageHeader from '../components/PageHeader.vue'
import SelectField from '../components/SelectField.vue'
import { useAsync } from '../composables/useAsync.js'
import { t } from '../i18n.js'
import { notify, notifyError } from '../notify.js'

const form = reactive({
	batch_size: '10',
	lot_wait_seconds: '300',
	campaign_duration_seconds: '7200',
	temporary_retention_days: '7',
})

const waitOptions = [
	{ id: '60', label: t('1 minute') },
	{ id: '120', label: t('2 minutes') },
	{ id: '300', label: t('5 minutes') },
	{ id: '600', label: t('10 minutes') },
	{ id: '900', label: t('15 minutes') },
	{ id: '1800', label: t('30 minutes') },
	{ id: '3600', label: t('1 hour') },
]
const durationOptions = [
	{ id: '1800', label: t('30 minutes') },
	{ id: '3600', label: t('1 hour') },
	{ id: '7200', label: t('2 hours') },
	{ id: '14400', label: t('4 hours') },
	{ id: '28800', label: t('8 hours') },
	{ id: '43200', label: t('12 hours') },
]

const { data, loading, error } = useAsync(() => request('api/admin/settings'), () => 'admin')

watch(data, (values) => {
	if (values) {
		for (const key of Object.keys(form)) {
			form[key] = String(values[key])
		}
	}
}, { immediate: true })

async function save() {
	try {
		await send('PUT', 'api/admin/settings', Object.fromEntries(Object.entries(form).map(([key, value]) => [key, Number(value)])))
		notify(t('Settings saved'))
	} catch (failure) {
		notifyError(failure)
	}
}
</script>

<style scoped>
.lucarne-settings-form {
	display: flex;
	flex-direction: column;
	gap: calc(var(--default-grid-baseline) * 4);
	max-width: 400px;
}
</style>
