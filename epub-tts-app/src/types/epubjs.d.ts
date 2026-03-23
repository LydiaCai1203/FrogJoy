declare module 'epubjs/lib/index' {
    import Epub from 'epubjs';
    export default Epub;
}

declare module 'epubjs' {
    export interface BookOptions {
        replacements?: string;
        restore?: boolean;
        reload?: boolean;
        openAs?: string;
    }

    export interface RenditionOptions {
        width?: number | string;
        height?: number | string;
        ignoreClass?: string;
        manager?: string;
        view?: string;
        flow?: string;
        layout?: string;
        spread?: string;
        minSpreadWidth?: number;
        stylesheet?: string;
        resizeOnOrientationChange?: boolean;
        script?: string;
        allowScriptedContent?: boolean;
        snap?: boolean;
        defaultDirection?: string;
    }

    export interface Location {
        start: {
            cfi: string;
            displayed: {
                page: number;
                total: number;
            };
        };
        end: {
            cfi: string;
            displayed: {
                page: number;
                total: number;
            };
        };
        atStart: boolean;
        atEnd: boolean;
    }

    export interface NavItem {
        id: string;
        href: string;
        label: string;
        subitems?: NavItem[];
        parent?: string;
    }

    export interface Navigation {
        toc: NavItem[];
        get: (target: string) => NavItem;
    }

    export interface SpineItem {
        index: number;
        cfiBase: string;
        href: string;
        url: string;
        canonical: string;
        idref: string;
        linear: string;
        spinePos: number;
        load: (book: Book) => Promise<Document>;
        unload: () => void;
    }

    export interface Spine {
        spineItems: SpineItem[];
        get: (target: string | number) => SpineItem;
        each: (callback: (item: SpineItem) => void) => void;
    }

    export interface Rendition {
        settings: RenditionOptions;
        location: Location;
        display: (target?: string) => Promise<void>;
        attachTo: (element: HTMLElement) => void;
        themes: {
            register: (name: string, url: string | object) => void;
            select: (name: string) => void;
            fontSize: (size: string) => void;
            font: (font: string) => void;
        };
        next: () => Promise<void>;
        prev: () => Promise<void>;
        on: (event: string, callback: (data: any) => void) => void;
        off: (event: string, callback: (data: any) => void) => void;
        destroy: () => void;
    }

    export class Book {
        constructor(url?: string | ArrayBuffer, options?: BookOptions);
        renderTo: (element: string | HTMLElement, options?: RenditionOptions) => Rendition;
        ready: Promise<any>;
        loaded: {
            navigation: Promise<Navigation>;
            spine: Promise<Spine>;
            metadata: Promise<any>;
            cover: Promise<string>;
            resources: Promise<any>;
        };
        navigation: Navigation;
        spine: Spine;
        coverUrl: () => Promise<string>;
        destroy: () => void;
        archive: {
            createUrl: (url: string) => Promise<string>;
            revokeUrl: (url: string) => void;
        };
    }

    const ePub: (url?: string | ArrayBuffer, options?: BookOptions) => Book;
    export default ePub;
}