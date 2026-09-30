<template>
	<NcActions
		v-model:open="open"
		class="lucarne-toolbar-menu"
		force-menu
		force-name
		variant="tertiary"
		:menu-name="isMobile ? '' : current.label"
		:title="`${label} : ${current.label}`"
		:aria-label="`${label} : ${current.label}`">
		<template #icon>
			<component :is="triggerIcon" :size="20" />
		</template>
		<NcActionButton
			v-for="option in options"
			:key="option.id"
			:class="{ 'lucarne-toolbar-menu__selected': option.id === modelValue }"
			:aria-pressed="option.id === modelValue"
			close-after-click
			@click="$emit('update:modelValue', option.id)">
			<template #icon>
				<component :is="option.icon" :size="20" />
			</template>
			{{ option.label }}
		</NcActionButton>
	</NcActions>
</template>

<script setup>
import NcActionButton from '@nextcloud/vue/components/NcActionButton'
import NcActions from '@nextcloud/vue/components/NcActions'
import { useIsMobile } from '@nextcloud/vue/composables/useIsMobile'
import { computed, ref } from 'vue'
import ChevronDownIcon from 'vue-material-design-icons/ChevronDown.vue'
import ChevronUpIcon from 'vue-material-design-icons/ChevronUp.vue'

const props = defineProps({
	modelValue: { type: String, required: true },
	/** Array of `{ id, label, icon }`, the icon being a component. */
	options: { type: Array, required: true },
	/** What the menu changes, for example "Catalogue". */
	label: { type: String, required: true },
	/** Icon shown alone when the screen is too narrow for the text. */
	icon: { type: Object, required: true },
})
defineEmits(['update:modelValue'])

const isMobile = useIsMobile()
const open = ref(false)

const current = computed(() => props.options.find((option) => option.id === props.modelValue) || props.options[0])
// Like the Files breadcrumb: a chevron next to the text, the icon alone on narrow screens.
const triggerIcon = computed(() => (isMobile.value ? props.icon : open.value ? ChevronUpIcon : ChevronDownIcon))
</script>

<style scoped>
/* A long name is cut with an ellipsis; the title attribute shows it in full. */
.lucarne-toolbar-menu :deep(.button-vue__text) {
	max-width: calc(var(--default-clickable-area) * 5);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.lucarne-toolbar-menu__selected :deep(.action-button) {
	background-color: var(--color-primary-element-light);
}
</style>
