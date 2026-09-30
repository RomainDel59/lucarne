<template>
	<nav v-if="total > perPage" class="lucarne-pagination">
		<NcButton variant="tertiary" :aria-label="t('Previous page')" :disabled="page <= 1" @click="$emit('change', page - 1)">
			<template #icon>
				<ChevronLeftIcon :size="20" />
			</template>
		</NcButton>
		<NcButton variant="tertiary" :aria-label="t('Next page')" :disabled="page * perPage >= total" @click="$emit('change', page + 1)">
			<template #icon>
				<ChevronRightIcon :size="20" />
			</template>
		</NcButton>
	</nav>
</template>

<script setup>
import NcButton from '@nextcloud/vue/components/NcButton'
import ChevronLeftIcon from 'vue-material-design-icons/ChevronLeft.vue'
import ChevronRightIcon from 'vue-material-design-icons/ChevronRight.vue'
import { t } from '../i18n.js'

defineProps({
	page: { type: Number, required: true },
	total: { type: Number, required: true },
	perPage: { type: Number, required: true },
})
defineEmits(['change'])
</script>

<style scoped>
.lucarne-pagination {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: calc(var(--default-grid-baseline) * 4);
	margin-block: calc(var(--default-grid-baseline) * 8);
}
</style>
