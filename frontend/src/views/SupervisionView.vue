<template>
	<div class="lucarne-page">
		<PageHeader :title="t('Supervision')" />
		<NcLoadingIcon v-if="!data && !failure" :size="44" />
		<NcEmptyContent v-else-if="failure" :name="t('Something went wrong')" :description="failure">
			<template #icon>
				<AlertCircleIcon />
			</template>
		</NcEmptyContent>
		<PageSection
			v-else
			:name="t('Agent')"
			:description="t('Real-time campaign and batch supervision.')">
			<ul class="lucarne-agent">
				<NcListItem
					:name="running ? t('Current batch') : t('Next batch in')"
					:details="running ? t('In progress') : countdown(seconds)" />
				<NcListItem
					:name="running ? t('Current operation') : t('Next operation')"
					:details="operation" />
				<li v-if="!data.jobs.length" class="lucarne-agent__empty">
					{{ t('No queued batches.') }}
				</li>
				<template v-for="job in data.jobs" :key="job.id">
					<NcListItem
						:name="jobTitle(job)"
						:details="`${technicalLabel(`status.${job.status}`)} · ${job.manual ? t('User request') : t('Automatic')}`">
						<template #subname>
							{{ job.error || presentationText(job.presentation?.summary) }}
						</template>
						<template #extra-actions>
							<div class="lucarne-agent__actions">
								<NcButton
									v-if="job.status === 'queued'"
									variant="tertiary"
									:title="t('Move up')"
									:aria-label="t('Move up')"
									:disabled="queued.indexOf(job) === 0"
									@click="alter(job, 'move', { direction: 'up' })">
									<template #icon>
										<ArrowUpIcon :size="20" />
									</template>
								</NcButton>
								<NcButton
									v-if="job.status === 'queued'"
									variant="tertiary"
									:title="t('Move down')"
									:aria-label="t('Move down')"
									:disabled="queued.indexOf(job) === queued.length - 1"
									@click="alter(job, 'move', { direction: 'down' })">
									<template #icon>
										<ArrowDownIcon :size="20" />
									</template>
								</NcButton>
								<NcButton
									v-if="job.status === 'error'"
									variant="tertiary"
									:title="t('Retry')"
									:aria-label="t('Retry')"
									@click="alter(job, 'retry')">
									<template #icon>
										<RefreshIcon :size="20" />
									</template>
								</NcButton>
								<NcButton
									v-if="job.status !== 'running'"
									variant="tertiary"
									:title="t('Delete')"
									:aria-label="t('Delete')"
									@click="alter(job, 'delete')">
									<template #icon>
										<DeleteIcon :size="20" />
									</template>
								</NcButton>
							</div>
						</template>
					</NcListItem>
					<li v-if="job.presentation?.details?.length" class="lucarne-agent__details">
						<NcButton
							variant="tertiary"
							:aria-expanded="expanded.has(job.id)"
							@click="toggle(job.id)">
							<template #icon>
								<ChevronDownIcon v-if="expanded.has(job.id)" :size="20" />
								<ChevronRightIcon v-else :size="20" />
							</template>
							{{ t('Show details ({count})', { count: job.presentation.details.length }) }}
						</NcButton>
						<ul v-if="expanded.has(job.id)">
							<li v-for="line in job.presentation.details" :key="line">
								{{ presentationText(line) }}
							</li>
						</ul>
					</li>
				</template>
				<NcListItem
					v-for="step in data.future_steps || []"
					:key="step.title"
					:name="t(step.title)"
					:details="t('Future step')">
					<template #subname>
						{{ t(step.summary) }}
					</template>
				</NcListItem>
			</ul>
		</PageSection>
	</div>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import NcEmptyContent from '@nextcloud/vue/components/NcEmptyContent'
import NcListItem from '@nextcloud/vue/components/NcListItem'
import NcLoadingIcon from '@nextcloud/vue/components/NcLoadingIcon'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import ArrowDownIcon from 'vue-material-design-icons/ArrowDown.vue'
import ArrowUpIcon from 'vue-material-design-icons/ArrowUp.vue'
import ChevronDownIcon from 'vue-material-design-icons/ChevronDown.vue'
import ChevronRightIcon from 'vue-material-design-icons/ChevronRight.vue'
import DeleteIcon from 'vue-material-design-icons/Delete.vue'
import RefreshIcon from 'vue-material-design-icons/Refresh.vue'
import { request, send } from '../api.js'
import PageHeader from '../components/PageHeader.vue'
import PageSection from '../components/PageSection.vue'
import { countdown } from '../format.js'
import { t } from '../i18n.js'
import { presentationText, technicalLabel } from '../labels.js'
import { notifyError } from '../notify.js'

const data = ref(null)
const failure = ref('')
const expanded = ref(new Set())
let timer = null

const seconds = computed(() => Math.max(0, Number(data.value.campaign.next_lot_at) - Number(data.value.server_time)))
const running = computed(() => data.value.jobs.find((job) => job.status === 'running'))
const queued = computed(() => data.value.jobs.filter((job) => job.status === 'queued'))
const operation = computed(() => {
	const presentation = (running.value || queued.value[0])?.presentation
	return presentation
		? presentationText(presentation.title, presentation.variables)
		: technicalLabel(`phase.${data.value.campaign.phase || 'discover'}`)
})

function toggle(id) {
	const next = new Set(expanded.value)
	if (!next.delete(id)) {
		next.add(id)
	}
	expanded.value = next
}

function jobTitle(job) {
	const presentation = job.presentation || {}
	return presentation.title ? presentationText(presentation.title, presentation.variables) : technicalLabel(`job.${job.type}`)
}

async function refresh() {
	try {
		data.value = await request('api/agent')
		failure.value = ''
	} catch (error) {
		failure.value = error.message
	}
}

async function alter(job, action, body = {}) {
	try {
		if (action === 'delete') {
			await request(`api/agent/jobs/${job.id}`, { method: 'DELETE' })
		} else {
			await send('POST', `api/agent/jobs/${job.id}/${action}`, body)
		}
		await refresh()
	} catch (error) {
		notifyError(error)
	}
}

onMounted(() => {
	refresh()
	timer = setInterval(refresh, 1000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.lucarne-agent {
	display: flex;
	flex-direction: column;
	gap: var(--default-grid-baseline);
}

/* These rows have no link: no pointer cursor and no hover highlight, which suggest a click. */
.lucarne-agent :deep(.list-item),
.lucarne-agent :deep(.list-item__anchor),
.lucarne-agent :deep(.list-item__anchor *) {
	cursor: default;
}

.lucarne-agent :deep(.list-item:hover),
.lucarne-agent :deep(.list-item:focus-within) {
	background-color: transparent !important;
}

.lucarne-agent__actions {
	display: flex;
	align-items: center;
	gap: var(--default-grid-baseline);
}

.lucarne-agent :deep(.list-item-content__extra-actions) {
	align-self: flex-start;
}

.lucarne-agent__empty {
	padding: calc(var(--default-grid-baseline) * 2) calc(var(--default-grid-baseline) * 3);
	color: var(--color-text-maxcontrast);
}

.lucarne-agent__details {
	padding-inline: calc(var(--default-grid-baseline) * 3);
	color: var(--color-text-maxcontrast);
}

/* The details line up with the text of the button, a bit smaller, to read as a sub-element. */
.lucarne-agent__details ul {
	margin-inline-start: calc(var(--default-clickable-area) + var(--default-grid-baseline) * 0.25);
	padding-block-end: var(--default-grid-baseline);
	font-size: var(--font-size-small, 13px);
}
</style>
