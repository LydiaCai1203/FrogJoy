import ePub, { type Book, type NavItem, type Rendition } from "epubjs";

export class EpubParser {
  book: Book | null = null;
  rendition: Rendition | null = null;

  async load(data: ArrayBuffer): Promise<Book> {
    this.book = ePub(data);
    await this.book.ready;
    return this.book;
  }

  async getToc(): Promise<NavItem[]> {
    if (!this.book) throw new Error("Book not loaded");
    const nav = await this.book.loaded.navigation;
    return nav.toc;
  }

  async getMetadata() {
    if (!this.book) throw new Error("Book not loaded");
    return await this.book.loaded.metadata;
  }

  async getCover() {
    if (!this.book) throw new Error("Book not loaded");
    return await this.book.coverUrl();
  }

  // Render to a hidden element to extract text or display
  render(elementId: string, width: string = "100%", height: string = "100%") {
    if (!this.book) throw new Error("Book not loaded");
    this.rendition = this.book.renderTo(elementId, {
      width,
      height,
      flow: "scrolled",
      manager: "continuous",
    });
    return this.rendition;
  }

  async getChapterText(href: string): Promise<string> {
    if (!this.book) throw new Error("Book not loaded");
    // Load the spine item
    const item = this.book.spine.get(href);
    if (!item) return "";
    
    // We need to load the document to extract text
    // @ts-ignore - load method exists but types might be tricky
    const doc = await item.load(this.book.load.bind(this.book));
    // Extract text content cleanly
    return doc.body.innerText || doc.body.textContent || "";
  }
  
  destroy() {
    if (this.book) {
      this.book.destroy();
      this.book = null;
    }
  }
}

export const epubParser = new EpubParser();
