import { useEffect, useRef, useCallback, useState, type RefObject } from 'react'
import { prepareWithSegments, layoutWithLines, type PreparedTextWithSegments, type LayoutLine } from '@chenglou/pretext'

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

interface UseLineLayoutOptions {
  /** Disable when not in play mode or no need for line layout */
  disabled?: boolean
}

/**
 * Uses pretext `prepareWithSegments` + `layoutWithLines` to split a single
 * sentence into actual rendered lines, enabling karaoke line-by-line reveal.
 *
 * - text changes  → prepareWithSegments() (~19ms) + layoutWithLines()
 * - width changes → only layoutWithLines() (~0.09ms)
 */
export function useLineLayout(
  text: string,
  containerRef: RefObject<HTMLElement | null>,
  options: UseLineLayoutOptions = {}
): LayoutLine[] {
  const { disabled = false } = options
  const preparedRef = useRef<PreparedTextWithSegments | null>(null)
  const [lines, setLines] = useState<LayoutLine[]>([])
  const lastWidthRef = useRef(0)

  // Use CSS variables for font size (set by ThemeContext), leading-relaxed (1.625)
  const getFontConfig = useCallback(() => {
    const isMd = window.innerWidth >= 768
    const fontSize = getCssFontSize()
    const lineHeight = fontSize * 1.625
    return { fontSize, lineHeight, font: `${fontSize}px ${FONT_FAMILY}` }
  }, [])

  // Run layoutWithLines to compute line breaks
  const recalcLayout = useCallback(() => {
    const container = containerRef.current
    if (!container || !preparedRef.current || disabled) return

    const { lineHeight } = getFontConfig()
    const containerWidth = container.clientWidth
    // Content width = container - p-4 padding (32px) - border-l-2 (2px)
    const textWidth = containerWidth - 34

    if (textWidth <= 0) return

    // Skip if width hasn't changed
    if (textWidth === lastWidthRef.current && lines.length > 0) return
    lastWidthRef.current = textWidth

    const result = layoutWithLines(preparedRef.current, textWidth, lineHeight)
    setLines(result.lines)
  }, [containerRef, disabled, getFontConfig, lines.length])

  // Text changes → prepare (one-time) + layout
  useEffect(() => {
    if (disabled || !text) {
      preparedRef.current = null
      setLines([])
      lastWidthRef.current = 0
      return
    }

    const { font } = getFontConfig()
    preparedRef.current = prepareWithSegments(text, font)
    lastWidthRef.current = 0 // Force re-layout
    recalcLayout()
  }, [text, disabled, getFontConfig, recalcLayout])

  // Container width changes → only re-layout (very fast)
  useEffect(() => {
    const container = containerRef.current
    if (!container || disabled) return

    const observer = new ResizeObserver(() => {
      lastWidthRef.current = 0 // Force re-layout on resize
      recalcLayout()
    })
    observer.observe(container)

    return () => observer.disconnect()
  }, [containerRef, disabled, recalcLayout])

  // Font size change -> re-prepare text with new font and recalculate layout
  useEffect(() => {
    if (disabled || !text) return

    const handleFontSizeChange = () => {
      const { font } = getFontConfig()
      preparedRef.current = prepareWithSegments(text, font)
      lastWidthRef.current = 0 // Force re-layout
      recalcLayout()
    }

    window.addEventListener('font-size-change', handleFontSizeChange)
    return () => window.removeEventListener('font-size-change', handleFontSizeChange)
  }, [disabled, text, getFontConfig, recalcLayout])

  return lines
}

export type { LayoutLine }
