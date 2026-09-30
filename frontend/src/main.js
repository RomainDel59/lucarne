import '@nextcloud/dialogs/style.css'
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router.js'

// AppAPI provides the `#content` container of the page, like the legacy layout
// of any Nextcloud app. The application renders its own Nextcloud content inside.
const content = document.getElementById('content')
if (content) {
	createApp(App).use(router).mount(content)
}
