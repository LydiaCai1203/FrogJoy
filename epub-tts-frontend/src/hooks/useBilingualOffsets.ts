import { useEffect, useRef, useCallback, useState, type RefObject } from 'react'
import { prepare, layout, type PreparedText } from '@chenglou/pretext'

// English: Times New Roman Italic (italic), Chinese: YouYuan (幼圆)
const FONT_FAMILY = '"Times New Roman Italic", "YouYuan", "Georgia Italic", "KaiTi", serif'
const ITEM_PADDING_V = 32   // p-4 top+bottom = 16*2
const ITEM_PADDING_H = 34   // p-4 left+right (32) + border-l-2 (2)
const GRID_GAP = 16          // gap-4
const MD_BREAKPOINT = 768

function getCssFontSize(): number {
  const isMd = window.innerWidth >= MD_BREAKPOINT
  const cssVar = isMd ? '--font-size-desktop' : '--font-size-mobile'
  const value = getComputedStyle(document.documentElement).getPropertyValue(cssVar).trim()
  if (value) {
    return parseInt(value, 10)
  }
  return isMd ? 18 : 16
}

interface UseBilingualOffsetsOptions {
  disabled?: boolean
}

/**
 * Pretext-based cumulative offsets for bilingual (grid) mode.
 *
 * Desktop (md+): grid-cols-2 — row height = max(original, translated)
 * Mobile:        grid-cols-1 — original and translated stack vertically
 *
 * Returns the same { offsets, findVisibleIndex } API as useSentenceOffsets
 * so the Reader scroll handler can consume it identically.
 */
export function useBilingualOffsets(
  originalSentences: string[],
  translatedSentences: string[],
  containerRef: RefObject<HTMLElement | null>,
  options: UseBilingualOffsetsOptions = {}
) {
  const { disabled = false } = options
  const preparedOrigRef = useRef<PreparedText[]>([])
  const preparedTransRef = useRef<PreparedText[]>([])
  const [offsets, setOffsets] = useState<number[]>([0])
  const containerTopRef = useRef(0)

  const recalcLayout = useCallback(() => {
    const container = containerRef.current
    if (!container || preparedOrigRef.current.length === 0 || disabled) return

    const containerWidth = container.clientWidth
    const isMd = window.innerWidth >= MD_BREAKPOINT
    const fontSize = getCssFontSize()
    const lineHeight = fontSize * 1.625

    const newOffsets = [0]

    if (isMd) {
      // ── Desktop: 2-column grid ──
      // Each column = (container - gap) / 2
      const colWidth = (containerWidth - GRID_GAP) / 2
      const textWidth = colWidth - ITEM_PADDING_H
      if (textWidth <= 0) return

      for (let i = 0; i < preparedOrigRef.current.length; i++) {
        const origH = layout(preparedOrigRef.current[i], textWidth, lineHeight).height + ITEM_PADDING_V
        const transH = i < preparedTransRef.current.length
          ? layout(preparedTransRef.current[i], textWidth, lineHeight).height + ITEM_PADDING_V
          : 0
        const rowHeight = Math.max(origH, transH)
        const gap = i > 0 ? GRID_GAP : 0
        newOffsets.push(newOffsets[newOffsets.length - 1] + rowHeight + gap)
      }
    } else {
      // ── Mobile: 1-column grid ──
      // Items alternate vertically: orig₀, trans₀, orig₁, trans₁ …
      const textWidth = containerWidth - ITEM_PADDING_H
      if (textWidth <= 0) return

      for (let i = 0; i < preparedOrigRef.current.length; i++) {
        const origH = layout(preparedOrigRef.current[i], textWidth, lineHeight).height + ITEM_PADDING_V
        const transH = i < preparedTransRef.current.length
          ? layout(preparedTransRef.current[i], textWidth, lineHeight).height + ITEM_PADDING_V
          : 0
        // Pair height: orig + gap + trans (two grid rows with a gap between them)
        const pairHeight = origH + GRID_GAP + transH
        // Gap before this pair (between previous pair and this one)
        const gap = i > 0 ? GRID_GAP : 0
        newOffsets.push(newOffsets[newOffsets.length - 1] + pairHeight + gap)
      }
    }

    setOffsets(newOffsets)
  }, [containerRef, disabled])

  // Sentences change → prepare() + layout()
  useEffect(() => {
    if (disabled || originalSentences.length === 0) {
      preparedOrigRef.current = []
      preparedTransRef.current = []
      setOffsets([0])
      return
    }

    const fontSize = getCssFontSize()
    const font = `${fontSize}px ${FONT_FAMILY}`
    preparedOrigRef.current = originalSentences.map(text => prepare(text, font))
    preparedTransRef.current = translatedSentences.map(text => prepare(text, font))
    recalcLayout()
  }, [originalSentences, translatedSentences, disabled, recalcLayout])

  // Container resize → only layout() (very fast)
  useEffect(() => {
    const container = containerRef.current
    if (!container || disabled) return

    const observer = new ResizeObserver(() => {
      recalcLayout()
      containerTopRef.current = container.offsetTop
    })
    observer.observe(container)

    containerTopRef.current = container.offsetTop

    return () => observer.disconnect()
  }, [containerRef, disabled, recalcLayout])

  // Font size change -> re-prepare sentences with new font and recalculate layout
  useEffect(() => {
    if (disabled || originalSentences.length === 0) return

    const handleFontSizeChange = () => {
      const fontSize = getCssFontSize()
      const font = `${fontSize}px ${FONT_FAMILY}`
      preparedOrigRef.current = originalSentences.map(text => prepare(text, font))
      preparedTransRef.current = translatedSentences.map(text => prepare(text, font))
      recalcLayout()
    }

    window.addEventListener('font-size-change', handleFontSizeChange)
    return () => window.removeEventListener('font-size-change', handleFontSizeChange)
  }, [disabled, originalSentences, translatedSentences, recalcLayout])

  // Binary search: given scrollTop + viewportHeight → sentence pair index
  const findVisibleIndex = useCallback(
    (scrollTop: number, viewportHeight: number): number => {
      if (offsets.length <= 1) return 0

      const center = scrollTop + viewportHeight / 2 - containerTopRef.current
      const lastIndex = offsets.length - 2

      let lo = 0
      let hi = lastIndex
      while (lo < hi) {
        const mid = (lo + hi) >> 1
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
