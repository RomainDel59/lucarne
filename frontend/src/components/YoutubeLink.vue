<template>
	<NcButton
		v-if="safeUrl"
		variant="secondary"
		:href="safeUrl"
		target="_blank"
		rel="noopener noreferrer"
		:title="t('Open on YouTube')"
		:aria-label="t('Open on YouTube')">
		<template #icon>
			<OpenInNewIcon :size="20" />
		</template>
	</NcButton>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import { computed } from 'vue'
import OpenInNewIcon from 'vue-material-design-icons/OpenInNew.vue'
import { t } from '../i18n.js'

const props = defineProps({
	/** Address of the item on YouTube. */
	url: { type: String, default: '' },
})

// Only a secure link to YouTube itself is shown, whatever the stored address is.
const safeUrl = computed(() => {
	try {
		const address = new URL(props.url)
		const host = address.hostname
		const youtube = host === 'youtube.com' || host.endsWith('.youtube.com') || host === 'youtu.be'
		return address.protocol === 'https:' && youtube ? address.href : ''
	} catch {
		return ''
	}
})
</script>
