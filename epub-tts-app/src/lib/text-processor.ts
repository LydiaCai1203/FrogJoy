export function splitTextIntoSentences(text: string): string[] {
  // Simple regex for splitting by punctuation
  // Supports CJK and Western punctuation
  // Keep the delimiter with the sentence
  const regex = /([^.!?。！？\n\r]+[.!?。！？\n\r]+)|([^.!?。！？\n\r]+$)/g;
  const matches = text.match(regex);
  
  if (!matches) return [text];
  
  // Filter out empty strings and trim
  return matches.map(s => s.trim()).filter(s => s.length > 0);
}
