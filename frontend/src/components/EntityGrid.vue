<template>
	<ul class="lucarne-entity-grid">
		<EntityListItem v-for="item in visible" :key="item.id" :item="item" :type="type" />
		<!-- Invisible tiles keep the grid, and so the pagination buttons, at the same place on the last page. -->
		<EntityListItem
			v-for="index in missing"
			:key="`filler-${index}`"
			class="lucarne-entity-grid__filler"
			aria-hidden="true"
			inert
			:item="items[0]"
			:type="type" />
	</ul>
	<Pagination :page="page" :total="items.length" :per-page="pageSize" @change="$emit('change', $event)" />
</template>

<script setup>
import { computed } from 'vue'
import EntityListItem from './EntityListItem.vue'
import Pagination from './Pagination.vue'

const props = defineProps({
	/** The whole list: it is cut into pages here. */
	items: { type: Array, required: true },
	/** Either `channel` or `playlist`. */
	type: { type: String, required: true },
	page: { type: Number, required: true },
	pageSize: { type: Number, required: true },
})
defineEmits(['change'])

const visible = computed(() => props.items.slice((props.page - 1) * props.pageSize, props.page * props.pageSize))
const missing = computed(() => (props.items.length > props.pageSize ? props.pageSize - visible.value.length : 0))
</script>

<style scoped>
.lucarne-entity-grid {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr));
	gap: calc(var(--default-grid-baseline) * 5);
}

.lucarne-entity-grid__filler {
	visibility: hidden;
}
</style>
