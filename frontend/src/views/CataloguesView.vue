<template>
	<div class="lucarne-page">
		<PageHeader :title="t('Catalogues')" />
		<NcLoadingIcon v-if="loading && !data" :size="44" />
		<NcEmptyContent v-else-if="error" :name="t('Something went wrong')" :description="error.message">
			<template #icon>
				<AlertCircleIcon />
			</template>
		</NcEmptyContent>
		<NcSettingsSection
			v-else-if="data"
			:name="t('Channel catalogues')"
			:description="t('Group subscriptions and browse their videos from the navigation.')">
			<div class="lucarne-catalogues">
				<div class="lucarne-catalogues__toolbar">
					<SelectField
						v-if="catalogs.length"
						class="lucarne-catalogues__select"
						:model-value="activeId"
						:options="catalogOptions"
						:label="t('Catalogue')"
						@update:model-value="changeCatalog" />
					<NcButton variant="secondary" @click="naming = { mode: 'add', value: '' }">
						<template #icon>
							<PlusIcon :size="20" />
						</template>
						{{ t('Add') }}
					</NcButton>
					<template v-if="current">
						<NcButton variant="secondary" @click="naming = { mode: 'edit', value: current.name }">
							<template #icon>
								<PencilIcon :size="20" />
							</template>
							{{ t('Edit') }}
						</NcButton>
						<NcButton variant="error" @click="deleteCatalog">
							<template #icon>
								<DeleteIcon :size="20" />
							</template>
							{{ t('Delete') }}
						</NcButton>
					</template>
				</div>
				<template v-if="current">
					<NcSelect
						v-model="selectedIds"
						:options="channelOptions"
						:reduce="(option) => option.id"
						label="label"
						:input-label="t('Catalogue channels')"
						multiple />
					<div class="lucarne-catalogues__actions">
						<NcButton variant="tertiary" :disabled="!dirty" @click="selectedIds = [...original]">
							{{ t('Cancel') }}
						</NcButton>
						<NcButton variant="primary" :disabled="!dirty" @click="saveChannels">
							{{ t('Save') }}
						</NcButton>
					</div>
				</template>
			</div>
		</NcSettingsSection>
		<FormDialog
			v-if="naming"
			:name="naming.mode === 'add' ? t('Add a catalogue') : t('Edit catalogue')"
			:submit-label="naming.mode === 'add' ? t('Create') : t('Save')"
			@submit="saveName"
			@close="naming = null">
			<NcTextField v-model="naming.value" :label="t('Name')" required />
		</FormDialog>
	</div>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import NcEmptyContent from '@nextcloud/vue/components/NcEmptyContent'
import NcLoadingIcon from '@nextcloud/vue/components/NcLoadingIcon'
import NcSelect from '@nextcloud/vue/components/NcSelect'
import NcSettingsSection from '@nextcloud/vue/components/NcSettingsSection'
import NcTextField from '@nextcloud/vue/components/NcTextField'
import { computed, ref } from 'vue'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import DeleteIcon from 'vue-material-design-icons/Delete.vue'
import PencilIcon from 'vue-material-design-icons/Pencil.vue'
import PlusIcon from 'vue-material-design-icons/Plus.vue'
import { request, send } from '../api.js'
import FormDialog from '../components/FormDialog.vue'
import PageHeader from '../components/PageHeader.vue'
import SelectField from '../components/SelectField.vue'
import { useAsync } from '../composables/useAsync.js'
import { confirm } from '../dialogs.js'
import { t } from '../i18n.js'
import { notify, notifyError } from '../notify.js'
import { setCatalogs } from '../store.js'

const catalogs = ref([])
const channels = ref([])
const activeId = ref('')
const original = ref([])
const selectedIds = ref([])
const naming = ref(null)

const { data, loading, error } = useAsync(async () => {
	const [catalogList, channelList] = await Promise.all([request('api/catalogs'), request('api/channels')])
	catalogs.value = catalogList
	channels.value = channelList
	await select(catalogList[0]?.id)
	return true
}, () => 'catalogues')

const current = computed(() => catalogs.value.find((item) => String(item.id) === String(activeId.value)) || null)
const catalogOptions = computed(() => catalogs.value.map((item) => ({ id: String(item.id), label: item.name })))
const channelOptions = computed(() => channels.value.map((item) => ({ id: item.id, label: item.title })))
const dirty = computed(() => JSON.stringify([...selectedIds.value].sort((a, b) => a - b)) !== JSON.stringify([...original.value].sort((a, b) => a - b)))

async function select(id) {
	if (id === undefined || id === null) {
		activeId.value = ''
		original.value = []
		selectedIds.value = []
		return
	}
	const details = await request(`api/catalogs/${id}`)
	activeId.value = String(id)
	original.value = (details.channel_ids || []).map(Number)
	selectedIds.value = [...original.value]
}

async function confirmDiscard() {
	if (!dirty.value) {
		return true
	}
	const answer = await confirm({
		title: t('Discard changes'),
		message: t('Discard the unsaved catalogue changes?'),
		submit: t('Yes'),
		cancel: t('No'),
		danger: true,
	})
	return answer.confirmed
}

function publish() {
	catalogs.value.sort((a, b) => a.name.localeCompare(b.name))
	setCatalogs(catalogs.value)
}

async function changeCatalog(id) {
	if (String(id) === activeId.value || !await confirmDiscard()) {
		return
	}
	try {
		await select(id)
	} catch (failure) {
		notifyError(failure)
	}
}

async function saveName() {
	const { mode, value } = naming.value
	try {
		if (mode === 'add') {
			const item = await send('POST', 'api/catalogs', { name: value })
			catalogs.value.push(item)
			publish()
			await select(item.id)
		} else {
			const item = await send('PUT', `api/catalogs/${current.value.id}`, { name: value })
			Object.assign(current.value, item)
			publish()
		}
	} catch (failure) {
		notifyError(failure)
	}
}

async function deleteCatalog() {
	const answer = await confirm({
		title: t('Delete catalogue'),
		message: t('The catalogue will be deleted. Channels and videos will remain.'),
		submit: t('Yes'),
		cancel: t('No'),
		danger: true,
	})
	if (!answer.confirmed) {
		return
	}
	try {
		const id = current.value.id
		await send('DELETE', `api/catalogs/${id}`)
		catalogs.value = catalogs.value.filter((item) => item.id !== id)
		publish()
		await select(catalogs.value[0]?.id)
	} catch (failure) {
		notifyError(failure)
	}
}

async function saveChannels() {
	try {
		await send('PUT', `api/catalogs/${current.value.id}/channels`, { channel_ids: [...selectedIds.value].sort((a, b) => a - b) })
		notify(t('Catalogue saved'))
		await select(current.value.id)
	} catch (failure) {
		notifyError(failure)
	}
}
</script>

<style scoped>
.lucarne-catalogues {
	display: flex;
	flex-direction: column;
	gap: calc(var(--default-grid-baseline) * 4);
	max-width: 700px;
}

.lucarne-catalogues__toolbar {
	display: flex;
	flex-wrap: wrap;
	align-items: flex-end;
	gap: calc(var(--default-grid-baseline) * 2);
}

.lucarne-catalogues__select {
	flex: 1 1 240px;
}

.lucarne-catalogues__actions {
	display: flex;
	justify-content: flex-end;
	gap: calc(var(--default-grid-baseline) * 2);
}
</style>
