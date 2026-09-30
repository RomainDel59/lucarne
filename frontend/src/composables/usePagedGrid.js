import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

// Same values as the video grid (`VideoGrid.vue`): tiles are at least this wide, with this gap.
const MIN_TILE_WIDTH = 280
const GAP_IN_BASELINES = 5
// A single column (phone) scrolls naturally, so a page holds more than a couple of rows.
const SINGLE_COLUMN_PAGE_SIZE = 10

/**
 * Page size and navigation for a paginated grid: a page always holds complete rows, whatever the
 * width available, so the page fits the screen and its last row is never ragged.
 *
 * @param {import('vue').Ref<HTMLElement|null>} pageElement The element that contains the grid.
 * @param {number} rows Rows per page: 2 for tall video tiles, more for compact tiles.
 */
export function usePagedGrid(pageElement, rows = 2) {
	const route = useRoute()
	const router = useRouter()
	const pageSize = ref(0)
	const page = computed(() => Number(route.query.page || 1))
	let observer = null

	function measure() {
		const element = pageElement.value
		if (!element) {
			return
		}
		const style = getComputedStyle(element)
		const baseline = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--default-grid-baseline')) || 4
		const gap = baseline * GAP_IN_BASELINES
		const width = element.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)
		const columns = Math.max(1, Math.floor((width + gap) / (MIN_TILE_WIDTH + gap)))
		pageSize.value = columns === 1 ? SINGLE_COLUMN_PAGE_SIZE : columns * rows
	}

	onMounted(() => {
		measure()
		observer = new ResizeObserver(measure)
		observer.observe(pageElement.value)
	})
	onBeforeUnmount(() => observer?.disconnect())

	function goTo(value) {
		router.push({ query: { ...route.query, page: value } })
	}

	/** Come back to the last page when a larger page size leaves the current one beyond the end. */
	function settle(total) {
		if (!pageSize.value) {
			return
		}
		const last = Math.max(1, Math.ceil(total / pageSize.value))
		if (page.value > last) {
			router.replace({ query: { ...route.query, page: last } })
		}
	}

	return { pageSize, page, goTo, settle }
}
