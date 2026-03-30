import { useEffect, useRef, useCallback, useState, type RefObject } from 'react'
import { prepare, layout, type PreparedText } from '@chenglou/pretext'

// English: Times New Roman Italic (italic), Chinese: YouYuan (幼圆)
const FONT_FAMILY = '"Times New Roman Italic", "YouYuan", "Georgia Italic", "KaiTi", serif'

function getCssFontSize(): number {
  const isMd = window.innerWidth >= 768
  const cssVar = isMd ? '--font-size-desktop' : '--font-size-mobile'
  const value = getComputedStyle(document.documentElement).getPropertyValue(cssVar).trim()
  if (value) {
    return parseInt(value, 10)
  }
  return isMd ? 18 : 16
}

interface UseSentenceOffsetsOptions {
  /** Disable when in HTML mode or bilingual mode */
  disabled?: boolean
}

/**
 * Uses pretext to precompute cumulative sentence offsets for O(log n) binary
 * search during scroll, instead of O(n) DOM reads via getBoundingClientRect().
 *
 * - sentences change -> prepare() (one-time preprocessing) + layout()
 * - container width change -> only layout() (very fast, ~0.09ms for 500 items)
 */
export function useSentenceOffsets(
  sentences: string[],
  containerRef: RefObject<HTMLElement | null>,
  options: UseSentenceOffsetsOptions = {}
) {
  const { disabled = false } = options
  const preparedRef = useRef<PreparedText[]>([])
  const [offsets, setOffsets] = useState<number[]>([0])
  // Top offset of the sentence container relative to scroll viewport
  const containerTopRef = useRef(0)

  // Detect desktop (md breakpoint = 768px)
  // Use CSS variables for font size (set by ThemeContext)
  // leading-relaxed = lineHeight * 1.625
  const getFontConfig = useCallback(() => {
    const isMd = window.innerWidth >= 768
    const fontSize = getCssFontSize()
    const lineHeight = fontSize * 1.625
    return { fontSize, lineHeight, font: `${fontSize}px ${FONT_FAMILY}` }
  }, [])

  // Run layout() to compute all heights and cumulative offsets
  const recalcLayout = useCallback(() => {
    const container = containerRef.current
    if (!container || preparedRef.current.length === 0 || disabled) return

    const { lineHeight } = getFontConfig()

    // Single DOM read for container width
    const containerWidth = container.clientWidth
    // Content width = container width - padding (p-4 = 16px*2) - border-left (border-l-2 = 2px)
    const textWidth = containerWidth - 34

    if (textWidth <= 0) return

    const newOffsets = [0]
    for (let i = 0; i < preparedRef.current.length; i++) {
      const { height } = layout(preparedRef.current[i], textWidth, lineHeight)
      const itemHeight = height + 32 // p-4 top+bottom padding = 32px
      const gap = i > 0 ? 24 : 0    // space-y-6 = 24px (first item has no gap)
      newOffsets.push(newOffsets[newOffsets.length - 1] + itemHeight + gap)
    }

    setOffsets(newOffsets)
  }, [containerRef, disabled, getFontConfig])

  // sentences change -> prepare() (~19ms/500 items) + layout()
  useEffect(() => {
    if (disabled || sentences.length === 0) {
      preparedRef.current = []
      setOffsets([0])
      return
    }

    const { font } = getFontConfig()
    preparedRef.current = sentences.map(text => prepare(text, font))
    recalcLayout()
  }, [sentences, disabled, getFontConfig, recalcLayout])

  // Container width change -> only layout() (very fast)
  useEffect(() => {
    const container = containerRef.current
    if (!container || disabled) return

    const observer = new ResizeObserver(() => {
      recalcLayout()
      // Also update container top offset
      containerTopRef.current = container.offsetTop
    })
    observer.observe(container)

    // Initial measurement of container offset
    containerTopRef.current = container.offsetTop

    return () => observer.disconnect()
  }, [containerRef, disabled, recalcLayout])

  // Font size change -> re-prepare sentences with new font and recalculate layout
  useEffect(() => {
    if (disabled || sentences.length === 0) return

    const handleFontSizeChange = () => {
      const { font } = getFontConfig()
      preparedRef.current = sentences.map(text => prepare(text, font))
      recalcLayout()
    }

    window.addEventListener('font-size-change', handleFontSizeChange)
    return () => window.removeEventListener('font-size-change', handleFontSizeChange)
  }, [disabled, sentences, getFontConfig, recalcLayout])

  // Binary search: given scrollTop and viewportHeight, return the sentence index
  // closest to the viewport center
  const findVisibleIndex = useCallback(
    (scrollTop: number, viewportHeight: number): number => {
      if (offsets.length <= 1) return 0

      const center = scrollTop + viewportHeight / 2 - containerTopRef.current
      const lastIndex = offsets.length - 2 // offsets has one more element than sentences

      let lo = 0
      let hi = lastIndex
      while (lo < hi) {
        const mid = (lo + hi) >> 1
        // offsets[mid+1] is the bottom edge of sentence mid
        if (offsets[mid + 1] < center) {
          lo = mid + 1
        } else {
          hi = mid
        }
      }

      return Math.min(lo, lastIndex)
    },
    [offsets]
  )

  return { offsets, findVisibleIndex, disabled: disabled || offsets.length <= 1 }
}
