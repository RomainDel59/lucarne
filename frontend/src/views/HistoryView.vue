<template>
	<div class="lucarne-page">
		<PageHeader :title="t('History')">
			<NcButton v-if="data && data.items.length" variant="error" @click="clear">
				<template #icon>
					<DeleteIcon :size="20" />
				</template>
				{{ t('Clear') }}
			</NcButton>
		</PageHeader>
		<NcLoadingIcon v-if="loading && !data" :size="44" />
		<NcEmptyContent v-else-if="error" :name="t('Something went wrong')" :description="error.message">
			<template #icon>
				<AlertCircleIcon />
			</template>
		</NcEmptyContent>
		<template v-else-if="data">
			<NcEmptyContent v-if="!data.items.length" :name="t('No history')" :description="t('Videos you watch will appear here.')">
				<template #icon>
					<HistoryIcon />
				</template>
			</NcEmptyContent>
			<template v-else>
				<VideoGrid :videos="data.items" />
				<Pagination :page="page" :total="data.total" @change="goTo" />
			</template>
		</template>
	</div>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import NcEmptyContent from '@nextcloud/vue/components/NcEmptyContent'
import NcLoadingIcon from '@nextcloud/vue/components/NcLoadingIcon'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AlertCircleIcon from 'vue-material-design-icons/AlertCircle.vue'
import DeleteIcon from 'vue-material-design-icons/Delete.vue'
import HistoryIcon from 'vue-material-design-icons/History.vue'
import { request, send } from '../api.js'
import PageHeader from '../components/PageHeader.vue'
import Pagination from '../components/Pagination.vue'
import VideoGrid from '../components/VideoGrid.vue'
import { useAsync } from '../composables/useAsync.js'
import { confirm } from '../dialogs.js'
import { t } from '../i18n.js'
import { notifyError } from '../notify.js'

const route = useRoute()
const router = useRouter()
const page = computed(() => Number(route.query.page || 1))

const { data, loading, error, reload } = useAsync(
	() => (route.name === 'history' ? request(`api/history?page=${page.value}`) : Promise.resolve(null)),
	() => [route.name, route.query.page],
)

function goTo(value) {
	router.push({ query: { ...route.query, page: value } })
}

async function clear() {
	const answer = await confirm({
		title: t('Clear history'),
		message: t('All playback positions will be removed.'),
		submit: t('Clear'),
		danger: true,
	})
	if (!answer.confirmed) {
		return
	}
	try {
		await send('DELETE', 'api/history')
		reload()
	} catch (failure) {
		notifyError(failure)
	}
}
</script>
