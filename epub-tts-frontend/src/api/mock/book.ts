import type { IBookService, BookMetadata, NavItem, ChapterContent } from "@/api/types";
import ePub, { type Book } from "epubjs";

export class MockBookService implements IBookService {
  private book: Book | null = null;
  private currentBuffer: ArrayBuffer | null = null;

  async uploadBook(file: File): Promise<{ bookId: string; metadata: BookMetadata; toc: NavItem[]; coverUrl?: string }> {
    const buffer = await file.arrayBuffer();
    this.currentBuffer = buffer;
    
    if (this.book) {
       this.book.destroy();
    }
    this.book = ePub(buffer);
    await this.book.ready;
    
    const metadata = await this.book.loaded.metadata;
    const nav = await this.book.loaded.navigation;
    const coverUrl = await this.book.coverUrl();
    
    const bookId = `mock-${Date.now()}`;
    
    return {
      bookId,
      metadata: {
        title: metadata.title,
        creator: metadata.creator,
        language: metadata.language,
        publisher: metadata.publisher,
        pubdate: metadata.pubdate
      },
      toc: nav.toc,
      coverUrl: coverUrl || undefined
    };
  }

  async getChapter(bookId: string, href: string): Promise<ChapterContent> {
    // Handle Demo Book ID
    if (bookId === "demo-book") {
        return this.getDemoChapter(href);
    }

    if (!this.book) {
      throw new Error("Book not loaded in Mock Service");
    }
    
    const item = this.book.spine.get(href);
    if (!item) throw new Error("Chapter not found");
    
    // @ts-ignore
    const doc = await item.load(this.book.load.bind(this.book));
    const text = doc.body.innerText || doc.body.textContent || "";
    
    const sentences = text.match(/([^.!?。！？\n\r]+[.!?。！？\n\r]+)|([^.!?。！？\n\r]+$)/g)
        ?.map(s => s.trim())
        .filter(s => s.length > 0) || [text];

    return {
      href,
      text,
      sentences
    };
  }

  private getDemoChapter(href: string): ChapterContent {
      const demoContent: Record<string, string[]> = {
        "chapter1": [
            "The neon lights of Neo-Tokyo flickered like a dying heartbeat.",
            "Jack plugged his neural interface into the deck, feeling the familiar cold rush of data.",
            "\"Access denied,\" the system whispered, a voice devoid of empathy.",
            "He smiled, his fingers dancing across the holographic keyboard.",
            "\"Not for long,\" he muttered, bypassing the firewall with a custom exploit.",
            "The virtual world expanded around him, a kaleidoscope of infinite information."
        ],
        "chapter2": [
            "Static filled the airwaves, a constant reminder of the signal decay.",
            "Sarah tuned her receiver, searching for a ghost in the machine.",
            "\"Can anyone hear me?\" she broadcasted into the void.",
            "Only the wind answered, howling through the ruins of the old internet hub.",
            "She adjusted the frequency, hoping for a miracle."
        ]
      };

      const sentences = demoContent[href] || ["Content not found."];
      return {
          href,
          text: sentences.join(" "),
          sentences
      };
  }
}
