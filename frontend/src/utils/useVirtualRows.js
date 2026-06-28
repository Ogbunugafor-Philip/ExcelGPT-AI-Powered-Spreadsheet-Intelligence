import { useCallback, useRef, useState } from 'react'

// Lightweight windowed-list virtualisation for large tables. Only rows within
// the viewport (± a 2-viewport buffer) are rendered; spacer rows preserve the
// scroll height. Disabled automatically for small tables (<= threshold rows).
export function useVirtualRows(total, { rowHeight = 40, maxHeight = 520, threshold = 60 } = {}) {
  const ref = useRef(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [viewport, setViewport] = useState(maxHeight)

  const onScroll = useCallback((event) => {
    setScrollTop(event.currentTarget.scrollTop)
    setViewport(event.currentTarget.clientHeight || maxHeight)
  }, [maxHeight])

  if (total <= threshold) {
    return { enabled: false, ref, onScroll, start: 0, end: total, topPad: 0, bottomPad: 0, rowHeight, maxHeight }
  }

  const buffer = Math.ceil((viewport * 2) / rowHeight)
  const start = Math.max(0, Math.floor(scrollTop / rowHeight) - buffer)
  const end = Math.min(total, Math.ceil((scrollTop + viewport) / rowHeight) + buffer)

  return {
    enabled: true,
    ref,
    onScroll,
    start,
    end,
    topPad: start * rowHeight,
    bottomPad: (total - end) * rowHeight,
    rowHeight,
    maxHeight,
  }
}

export default useVirtualRows
