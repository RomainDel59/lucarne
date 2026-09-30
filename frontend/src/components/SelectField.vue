<template>
	<NcSelect
		:model-value="modelValue"
		:options="options"
		:reduce="(option) => option.id"
		:selectable="selectable"
		label="label"
		:input-label="compact ? undefined : label"
		:label-outside="compact"
		:aria-label-combobox="label"
		:clearable="false"
		:searchable="false"
		@update:model-value="(value) => $emit('update:modelValue', value)" />
</template>

<script setup>
import NcSelect from '@nextcloud/vue/components/NcSelect'

defineProps({
	modelValue: { type: [String, Number], default: '' },
	/** Array of `{ id, label }`. */
	options: { type: Array, required: true },
	label: { type: String, required: true },
	/** Hide the visible label, for selects placed in a toolbar. */
	compact: { type: Boolean, default: false },
	selectable: { type: Function, default: () => true },
})
defineEmits(['update:modelValue'])
</script>
