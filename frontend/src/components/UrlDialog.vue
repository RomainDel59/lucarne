<template>
	<FormDialog :name="title" :submit-label="submitLabel" @submit="$emit('submit', value)" @close="$emit('close')">
		<NcTextField v-model="value" :label="label" type="url" required />
	</FormDialog>
</template>

<script setup>
import NcTextField from '@nextcloud/vue/components/NcTextField'
import { ref } from 'vue'
import FormDialog from './FormDialog.vue'

defineProps({
	title: { type: String, required: true },
	label: { type: String, required: true },
	submitLabel: { type: String, required: true },
})
defineEmits(['submit', 'close'])

const value = ref('')
</script>
