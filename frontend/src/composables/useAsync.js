import { onBeforeUnmount, ref, watch } from 'vue'

/**
 * Run an asynchronous loader now and every time the watched source changes.
 */
export function useAsync(loader, source) {
	const data = ref(null)
	const loading = ref(true)
	const error = ref(null)
	let current = 0

	async function run() {
		const token = ++current
		loading.value = true
		error.value = null
		try {
			const result = await loader()
			if (token === current) {
				data.value = result
			}
		} catch (failure) {
			if (token === current) {
				error.value = failure
			}
		} finally {
			if (token === current) {
				loading.value = false
			}
		}
	}

	watch(source, run, { immediate: true })
	onBeforeUnmount(() => { current++ })

	return { data, loading, error, reload: run }
}
