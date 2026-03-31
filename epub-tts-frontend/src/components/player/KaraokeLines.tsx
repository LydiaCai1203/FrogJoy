import { useMemo, type RefObject } from "react"
import { cn } from "@/lib/utils"
import type { LayoutLine } from "@/hooks/useLineLayout"
import type { WordTimestamp } from "@/api/types"

interface KaraokeLineProps {
  lines: LayoutLine[]
  wordTimestamps: WordTimestamp[]
  currentWordIndex: number
  activeWordRef: RefObject<HTMLSpanElement>
}

type LineState = "past" | "current" | "future"

/**
 * Maps each word timestamp to its line index by sequentially searching
 * through the layout lines.
 */
function mapWordsToLines(
  wordTimestamps: WordTimestamp[],
  lines: LayoutLine[]
): number[] {
  const wordLineIndices: number[] = []
  let lineIdx = 0
  let searchStart = 0

  for (const wordTs of wordTimestamps) {
    // Search forward through lines to find the one containing this word
    while (lineIdx < lines.length) {
      const lineText = lines[lineIdx].text
      const pos = lineText.indexOf(wordTs.text, searchStart)
      if (pos !== -1) {
        wordLineIndices.push(lineIdx)
        searchStart = pos + wordTs.text.length
        break
      }
      // Move to next line, reset search position
      lineIdx++
      searchStart = 0
    }

    // If we've exhausted all lines, assign remaining words to the last line
    if (lineIdx >= lines.length) {
      wordLineIndices.push(lines.length - 1)
    }
  }

  return wordLineIndices
}

const LINE_STATE_CLASSES: Record<LineState, string> = {
  past: "text-foreground/85 transition-all duration-300 ease-out",
  current: "text-foreground transition-all duration-300 ease-out",
  future: "text-foreground/30 translate-y-1 blur-[0.3px] transition-all duration-300 ease-out",
}

export function KaraokeLines({
  lines,
  wordTimestamps,
  currentWordIndex,
  activeWordRef,
}: KaraokeLineProps) {
  // Map words to their line indices
  const wordLineIndices = useMemo(
    () => mapWordsToLines(wordTimestamps, lines),
    [wordTimestamps, lines]
  )

  // Determine which line is currently active
  const currentLineIndex = currentWordIndex >= 0 && currentWordIndex < wordLineIndices.length
    ? wordLineIndices[currentWordIndex]
    : -1 // TTS hasn't started yet → all lines are "future"

  // Get words that belong to a specific line
  const getWordsForLine = (lineIndex: number) => {
    const result: { wordTs: WordTimestamp; globalWordIdx: number }[] = []
    for (let i = 0; i < wordLineIndices.length; i++) {
      if (wordLineIndices[i] === lineIndex) {
        result.push({ wordTs: wordTimestamps[i], globalWordIdx: i })
      }
    }
    return result
  }

  const getLineState = (lineIndex: number): LineState => {
    if (currentLineIndex === -1) return "future"
    if (lineIndex < currentLineIndex) return "past"
    if (lineIndex === currentLineIndex) return "current"
    return "future"
  }

  // Render the current line with per-word highlighting (same as existing renderSentence logic)
  const renderCurrentLine = (lineIndex: number) => {
    const lineText = lines[lineIndex].text
    const lineWords = getWordsForLine(lineIndex)

    if (lineWords.length === 0) {
      return <span>{lineText}</span>
    }

    const nodes: React.ReactNode[] = []
    let lastIndex = 0

    for (const { wordTs, globalWordIdx } of lineWords) {
      const wordStart = lineText.indexOf(wordTs.text, lastIndex)
      if (wordStart === -1) continue

      // Text before this word
      if (wordStart > lastIndex) {
        const segment = lineText.slice(lastIndex, wordStart)
        nodes.push(
          <span key={`pre-${globalWordIdx}`} className="transition-colors duration-150">
            {segment}
          </span>
        )
      }

      const isCurrentWord = globalWordIdx === currentWordIndex
      const isPastWord = globalWordIdx < currentWordIndex

      nodes.push(
        <span
          key={`word-${globalWordIdx}`}
          ref={isCurrentWord ? activeWordRef : undefined}
          className={cn(
            "transition-all duration-150 rounded-sm px-0.5 -mx-0.5",
            isCurrentWord
              ? "bg-primary text-primary-foreground font-semibold shadow-[0_0_12px_rgba(204,255,0,0.6)] scale-105 inline-block"
              : isPastWord
                ? "text-foreground/90"
                : "text-foreground/60"
          )}
        >
          {wordTs.text}
        </span>
      )

      lastIndex = wordStart + wordTs.text.length
    }

    // Remaining text after last word
    if (lastIndex < lineText.length) {
      nodes.push(
        <span key="rest" className="text-foreground/60">
          {lineText.slice(lastIndex)}
        </span>
      )
    }

    return nodes.length > 0 ? nodes : <span>{lineText}</span>
  }

  return (
    <>
      {lines.map((line, lineIndex) => {
        const state = getLineState(lineIndex)

        return (
          <span
            key={lineIndex}
            className={cn("block", LINE_STATE_CLASSES[state])}
          >
            {state === "current"
              ? renderCurrentLine(lineIndex)
              : line.text}
          </span>
        )
      })}
    </>
  )
}
