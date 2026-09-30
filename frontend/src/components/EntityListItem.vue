<template>
	<NcListItem :name="title" :to="to" :details="status">
		<template #name>
			<span :title="title">{{ title }}</span>
		</template>
		<template #icon>
			<NcAvatar
				:url="imageUrl"
				:display-name="title"
				:size="44"
				is-no-user
				hide-status
				disable-menu
				disable-tooltip />
		</template>
		<template #subname>
			{{ subtitle }}
		</template>
	</NcListItem>
</template>

<script setup>
import NcAvatar from '@nextcloud/vue/components/NcAvatar'
import NcListItem from '@nextcloud/vue/components/NcListItem'
import { computed } from 'vue'
import { apiUrl } from '../api.js'
import { entityTitle, formatDate } from '../format.js'
import { t } from '../i18n.js'

const props = defineProps({
	item: { type: Object, required: true },
	/** Either `channel` or `playlist`. */
	type: { type: String, required: true },
})

const title = computed(() => entityTitle(props.item, props.type))
const imageUrl = computed(() => (props.item.image_url ? apiUrl(props.item.image_url) : undefined))
const to = computed(() => ({ name: props.type, params: { id: props.item.id } }))
const subtitle = computed(() => {
	const count = Number(props.item.video_count || 0)
	return count ? t('{count} videos · {date}', { count, date: formatDate(props.item.latest_published_at) }) : t('No videos')
})
const status = computed(() => {
	if (['pending', 'initializing', 'syncing'].includes(props.item.sync_status)) {
		return t('Initialization pending')
	}
	if (props.item.sync_status === 'error') {
		return props.type === 'playlist' ? t('Import needs retry') : t('Synchronization needs retry')
	}
	return ''
})
</script>
