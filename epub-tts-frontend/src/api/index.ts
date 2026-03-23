import { MockBookService } from "./mock/book";
import { BookService, TTSService } from "./services";
import type { IBookService, ITTSService } from "./types";

export type { IBookService, ITTSService } from "./types";
export type { BookMetadata, NavItem, ChapterContent, TTSOptions, WordTimestamp, TTSResponse } from "./types";

// 切换为使用真实后端服务
const USE_MOCK = false;

export const bookService: IBookService = USE_MOCK ? new MockBookService() : new BookService();
export const ttsService: ITTSService = USE_MOCK ? new MockBookService() as unknown as ITTSService : new TTSService();
