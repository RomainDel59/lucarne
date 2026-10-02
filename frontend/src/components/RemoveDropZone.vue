<template>
	<div
		v-if="dragging"
		class="lucarne-remove-zone"
		:class="{ 'lucarne-remove-zone--over': over }"
		@dragover="allow"
		@dragenter="over = true"
		@dragleave="over = false"
		@drop.prevent="release">
		<FolderRemoveOutlineIcon :size="20" />
		{{ label }}
	</div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import FolderRemoveOutlineIcon from 'vue-material-design-icons/FolderRemoveOutline.vue'

const props = defineProps({
	/** Data type of the dragged items this zone accepts. */
	type: { type: String, required: true },
	label: { type: String, required: true },
})
const emit = defineEmits(['drop'])

const dragging = ref(false)
const over = ref(false)

// The zone only exists while an item of its type is dragged, wherever the drag started in the page.
const start = (event) => { dragging.value = Boolean(event.dataTransfer?.types.includes(props.type)) }
const stop = () => {
	dragging.value = false
	over.value = false
}
onMounted(() => {
	window.addEventListener('dragstart', start)
	window.addEventListener('dragend', stop)
})
onBeforeUnmount(() => {
	window.removeEventListener('dragstart', start)
	window.removeEventListener('dragend', stop)
})

function allow(event) {
	if (event.dataTransfer?.types.includes(props.type)) {
		event.preventDefault()
		event.dataTransfer.dropEffect = 'move'
	}
}

function release(event) {
	const payload = event.dataTransfer?.getData(props.type)
	stop()
	if (payload) {
		emit('drop', JSON.parse(payload))
	}
}
</script>

<style scoped>
/* Footer of the content area: it does not follow the list, which can be short. */
.lucarne-remove-zone {
	position: absolute;
	inset-inline: 0;
	inset-block-end: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	gap: calc(var(--default-grid-baseline) * 2);
	padding: calc(var(--default-grid-baseline) * 5);
	color: var(--color-main-text);
	background-color: var(--color-main-background);
	border-block-start: 2px dashed var(--color-border-maxcontrast);
}

.lucarne-remove-zone--over {
	border-block-start-color: var(--color-primary-element);
	background-color: var(--color-background-hover);
}
</style>
