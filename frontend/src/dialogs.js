import { createApp, h } from 'vue'
import ConfirmDialog from './components/ConfirmDialog.vue'

/**
 * Ask for a confirmation and resolve with `{ confirmed, checked }`.
 */
export function confirm(options) {
	return new Promise((resolve) => {
		const host = document.createElement('div')
		document.body.append(host)
		const app = createApp({
			render: () => h(ConfirmDialog, {
				...options,
				onFinish: (result) => {
					resolve(result)
					setTimeout(() => {
						app.unmount()
						host.remove()
					}, 500)
				},
			}),
		})
		app.mount(host)
	})
}
