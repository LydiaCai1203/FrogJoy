import os
import uuid
import shutil
import json
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from fastapi import UploadFile, HTTPException
from typing import List, Dict, Optional, Any
import hashlib

from app.config import settings

IMAGES_DIR = "data/images"


class BookService:
    @staticmethod
    def get_book_path(user_id: str, book_id: str) -> str:
        return settings.get_book_path(user_id, book_id)

    @staticmethod
    async def save_upload(file: UploadFile, user_id: str) -> tuple[str, str]:
        """Save uploaded EPUB file.
        Returns (book_id, file_path).
        """
        book_id = str(uuid.uuid4())
        book_dir = settings.get_user_book_dir(user_id, book_id)
        os.makedirs(book_dir, exist_ok=True)

        file_path = settings.get_book_path(user_id, book_id)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return book_id, file_path

    @staticmethod
    def parse_metadata(book_id: str, user_id: str) -> Dict[str, Any]:
        path = settings.get_book_path(user_id, book_id)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Book not found")

        try:
            book = epub.read_epub(path)

            # Helper to get metadata safely
            def get_meta(name: str, namespace: str = 'DC') -> str:
                try:
                    res = book.get_metadata(namespace, name)
                    if res:
                        return res[0][0]
                    return ""
                except:
                    return ""

            metadata = {
                "title": get_meta("title") or "Unknown Title",
                "creator": get_meta("creator") or "Unknown Author",
                "language": get_meta("language") or "en",
                "publisher": get_meta("publisher"),
                "pubdate": get_meta("date"),
            }

            # Extract Cover
            cover_url = None
            cover_item = None
            try:
                for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
                    try:
                        item_name = item.get_name().lower() if item.get_name() else ""
                        item_id = item.get_id().lower() if item.get_id() else ""
                        if 'cover' in item_name or 'cover' in item_id:
                            cover_item = item
                            break
                    except Exception:
                        continue

                if cover_item:
                    try:
                        cover_path = settings.get_cover_path(user_id, book_id)
                        with open(cover_path, "wb") as f:
                            f.write(cover_item.get_content())
                        cover_url = f"/api/files/{user_id}/{book_id}/cover.jpg"
                    except Exception as e:
                        print(f"Warning: Failed to extract cover image: {e}")
                        cover_url = None
            except Exception as e:
                print(f"Warning: Error while searching for cover: {e}")
                cover_url = None

            return {"metadata": metadata, "coverUrl": cover_url}
        except Exception as e:
            import traceback
            error_detail = f"Failed to parse EPUB metadata: {str(e)}"
            print(f"Error parsing metadata: {error_detail}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=error_detail)

    @staticmethod
    def get_toc(book_id: str, user_id: str) -> List[Dict[str, Any]]:
        path = settings.get_book_path(user_id, book_id)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Book not found")

        try:
            book = epub.read_epub(path)
            toc = []

            # Recursive function to parse TOC
            def parse_nav_map(nav_point):
                try:
                    if isinstance(nav_point, tuple) or isinstance(nav_point, list):
                        link = nav_point[0]
                        children = nav_point[1] if len(nav_point) > 1 else []
                    else:
                        link = nav_point
                        children = []

                    if hasattr(link, 'href') and hasattr(link, 'title'):
                        item = {
                            "id": str(uuid.uuid4()),
                            "href": link.href,
                            "label": link.title,
                            "subitems": [parse_nav_map(c) for c in children if c is not None]
                        }
                        return item
                    return None
                except Exception as e:
                    print(f"Error parsing nav_map item: {e}")
                    return None

            try:
                if hasattr(book, 'toc') and book.toc:
                    for item in book.toc:
                        try:
                            parsed = parse_nav_map(item)
                            if parsed:
                                toc.append(parsed)
                        except Exception as e:
                            print(f"Warning: Failed to parse TOC item: {e}")
                            continue
            except Exception as e:
                print(f"Warning: Error processing TOC: {e}")

            has_real_structure = False
            toc_item_count = 0

            if toc:
                def count_items(items):
                    count = len(items)
                    for item in items:
                        if item.get('subitems'):
                            count += count_items(item['subitems'])
                    return count

                toc_item_count = count_items(toc)
                has_real_structure = toc_item_count >= 3 or any(item.get('subitems') for item in toc)

            should_use_spine = not toc or toc_item_count <= 1 or not has_real_structure

            def extract_title_from_html(item_content: bytes) -> Optional[str]:
                try:
                    content_str = item_content.decode('utf-8')
                    soup = BeautifulSoup(content_str, 'html.parser')

                    for tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        title_tag = soup.find(tag_name)
                        if title_tag:
                            title_text = title_tag.get_text().strip()
                            if title_text and len(title_text) < 200:
                                return title_text

                    title_elements = soup.find_all(class_=lambda x: x and 'title' in x.lower())
                    for elem in title_elements:
                        text = elem.get_text().strip()
                        if text and len(text) < 200:
                            return text

                    strong_tag = soup.find(['strong', 'b'])
                    if strong_tag:
                        text = strong_tag.get_text().strip()
                        if text and len(text) < 200:
                            return text

                except Exception as e:
                    print(f"Warning: Failed to extract title from HTML: {e}")

                return None

            try:
                spine = book.spine
                spine_items = []
                chapter_num = 1

                for item_id, _ in spine:
                    try:
                        item = book.get_item_with_id(item_id)
                        if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                            item_name = item.get_name()
                            if item_name:
                                label = None
                                try:
                                    item_content = item.get_content()
                                    label = extract_title_from_html(item_content)
                                except Exception as e:
                                    print(f"Warning: Failed to get content for title extraction: {e}")

                                if not label:
                                    label = os.path.basename(item_name)
                                    label = label.replace('.html', '').replace('.xhtml', '').replace('.htm', '')

                                    if not label or label.isdigit() or ('part' in label.lower() and 'split' in label.lower()):
                                        label = f"第 {chapter_num} 章"
                                    else:
                                        label = label.replace('_', ' ').replace('-', ' ')

                                spine_items.append({
                                    "id": str(uuid.uuid4()),
                                    "href": item_name,
                                    "label": label or f"第 {chapter_num} 章",
                                    "subitems": []
                                })
                                chapter_num += 1
                    except Exception as e:
                        print(f"Warning: Failed to get spine item {item_id}: {e}")
                        continue

                if spine_items:
                    original_toc_count = len(toc) if toc else 0
                    if should_use_spine or len(spine_items) > max(original_toc_count, 2):
                        toc = spine_items
                        print(f"Using spine: {len(spine_items)} chapters (replaced {original_toc_count} TOC items, should_use_spine={should_use_spine})")
                    else:
                        print(f"Keeping TOC ({original_toc_count} items), spine has {len(spine_items)} items")
            except Exception as e:
                print(f"Warning: Error getting items from spine: {e}")

            if not toc:
                try:
                    all_items = []
                    chapter_num = 1
                    for item in book.get_items():
                        try:
                            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                                item_name = item.get_name()
                                if item_name:
                                    if any(skip in item_name.lower() for skip in ['cover', 'titlepage', 'toc', 'nav']):
                                        continue

                                    label = None
                                    try:
                                        item_content = item.get_content()
                                        label = extract_title_from_html(item_content)
                                    except Exception as e:
                                        print(f"Warning: Failed to get content for title extraction: {e}")

                                    if not label:
                                        label = os.path.basename(item_name)
                                        label = label.replace('.html', '').replace('.xhtml', '').replace('.htm', '')

                                        if not label or label.isdigit() or ('part' in label.lower() and 'split' in label.lower()):
                                            label = f"第 {chapter_num} 章"
                                        else:
                                            label = label.replace('_', ' ').replace('-', ' ')

                                    all_items.append({
                                        "id": str(uuid.uuid4()),
                                        "href": item_name,
                                        "label": label or f"第 {chapter_num} 章",
                                        "subitems": []
                                    })
                                    chapter_num += 1
                        except Exception as e:
                            print(f"Warning: Failed to process item: {e}")
                            continue

                    if all_items:
                        toc = all_items
                        print(f"Using all items fallback: {len(toc)} chapters")
                except Exception as e:
                    print(f"Warning: Last resort failed: {e}")

            print(f"TOC parsed: {len(toc)} items")
            if toc:
                print(f"First chapter: {toc[0]}")
            else:
                print("WARNING: TOC is empty after all fallback attempts")

            return toc
        except Exception as e:
            import traceback
            error_detail = f"Failed to parse EPUB TOC: {str(e)}"
            print(f"Error parsing TOC: {error_detail}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=error_detail)

    @staticmethod
    def get_first_available_chapter(book_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        path = settings.get_book_path(user_id, book_id)
        if not os.path.exists(path):
            return None

        try:
            book = epub.read_epub(path)

            try:
                spine = book.spine
                for item_id, _ in spine:
                    try:
                        item = book.get_item_with_id(item_id)
                        if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                            item_name = item.get_name()
                            if item_name:
                                return {
                                    "id": str(uuid.uuid4()),
                                    "href": item_name,
                                    "label": "第 1 章",
                                    "subitems": []
                                }
                    except:
                        continue
            except:
                pass

            for item in book.get_items():
                try:
                    if item.get_type() == ebooklib.ITEM_DOCUMENT:
                        item_name = item.get_name()
                        if item_name:
                            if any(skip in item_name.lower() for skip in ['cover', 'titlepage', 'toc', 'nav']):
                                continue
                            return {
                                "id": str(uuid.uuid4()),
                                "href": item_name,
                                "label": "第 1 章",
                                "subitems": []
                            }
                except:
                    continue

            return None
        except Exception as e:
            print(f"Error getting first chapter: {e}")
            return None

    @staticmethod
    def extract_images(book_id: str, user_id: str) -> Dict[str, str]:
        path = settings.get_book_path(user_id, book_id)
        if not os.path.exists(path):
            return {}

        book_images_dir = os.path.join(IMAGES_DIR, book_id)
        os.makedirs(book_images_dir, exist_ok=True)

        mapping_file = os.path.join(book_images_dir, "_mapping.json")
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass

        book = epub.read_epub(path)
        image_mapping = {}

        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            try:
                original_name = item.get_name()

                ext = os.path.splitext(original_name)[1].lower() or '.jpg'
                safe_name = hashlib.md5(original_name.encode()).hexdigest()[:12] + ext

                image_path = os.path.join(book_images_dir, safe_name)
                with open(image_path, "wb") as f:
                    f.write(item.get_content())

                server_url = f"/images/{book_id}/{safe_name}"

                image_mapping[original_name] = server_url
                base_name = os.path.basename(original_name)
                image_mapping[base_name] = server_url
                if original_name.startswith('OEBPS/'):
                    image_mapping[original_name[6:]] = server_url
                if original_name.startswith('OPS/'):
                    image_mapping[original_name[4:]] = server_url

            except Exception as e:
                print(f"[BookService] Failed to extract image {item.get_name()}: {e}")

        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(image_mapping, f, ensure_ascii=False, indent=2)

        return image_mapping

    @staticmethod
    def get_chapter_content(book_id: str, href: str, user_id: str) -> Dict[str, Any]:
        path = settings.get_book_path(user_id, book_id)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Book not found")

        image_mapping = BookService.extract_images(book_id, user_id)

        book = epub.read_epub(path)

        anchor = None
        if '#' in href:
            base_href, anchor = href.split('#', 1)
        else:
            base_href = href

        chapter_dir = os.path.dirname(base_href)

        target_item = None
        for item in book.get_items():
            item_name = item.get_name()
            if item_name == base_href or item_name.endswith('/' + base_href) or base_href.endswith(item_name):
                target_item = item
                break

        if not target_item:
            raise HTTPException(status_code=404, detail=f"Chapter {href} not found")

        content = target_item.get_content()
        soup = BeautifulSoup(content, 'html.parser')

        for img in soup.find_all('img'):
            src = img.get('src', '')
            if not src:
                continue

            server_url = None

            if src in image_mapping:
                server_url = image_mapping[src]
            elif chapter_dir:
                full_path = os.path.normpath(os.path.join(chapter_dir, src)).replace('\\', '/')
                if full_path in image_mapping:
                    server_url = image_mapping[full_path]
            if not server_url:
                base_name = os.path.basename(src)
                if base_name in image_mapping:
                    server_url = image_mapping[base_name]

            if server_url:
                img['src'] = server_url
                img['style'] = img.get('style', '') + '; max-width: 100%; height: auto;'

        target_element = None
        if anchor:
            target_element = soup.find(id=anchor)
            if not target_element:
                target_element = soup.find(attrs={"name": anchor})

        heading_tags = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
        block_tags = {'p', 'div', 'section', 'article', 'blockquote'}
        list_tags = {'ul', 'ol', 'nav', 'dl'}
        list_item_tags = {'li', 'dt', 'dd'}

        def extract_structured_text(element):
            if element is None:
                return ""

            if isinstance(element, str) or hasattr(element, 'strip') and not hasattr(element, 'name'):
                text = str(element).strip()
                return text if text else ""

            if not hasattr(element, 'name') or element.name is None:
                if hasattr(element, 'get_text'):
                    return element.get_text().strip()
                return str(element).strip()

            tag_name = element.name

            if tag_name in heading_tags:
                text = element.get_text(separator=' ').strip()
                return f"\n\n{text}\n\n" if text else ""

            if tag_name in list_tags:
                parts = []
                for child in element.children:
                    child_text = extract_structured_text(child)
                    if child_text:
                        parts.append(child_text)
                return '\n'.join(parts)

            if tag_name in list_item_tags:
                text = element.get_text(separator=' ').strip()
                return f"{text}\n" if text else ""

            if tag_name in block_tags:
                text = element.get_text(separator=' ').strip()
                return f"{text}\n" if text else ""

            if hasattr(element, 'children'):
                parts = []
                for child in element.children:
                    child_text = extract_structured_text(child)
                    if child_text:
                        parts.append(child_text)
                return ' '.join(parts) if parts else ""

            if hasattr(element, 'get_text'):
                return element.get_text(separator=' ').strip()
            return ""

        if target_element:
            parts = [extract_structured_text(target_element)]

            for sibling in target_element.find_next_siblings():
                if hasattr(sibling, 'name') and sibling.name in heading_tags and sibling.get('id'):
                    break
                sibling_text = extract_structured_text(sibling)
                if sibling_text:
                    parts.append(sibling_text)

            text = '\n'.join(parts)
        else:
            body = soup.find('body') or soup
            parts = []
            for child in body.children:
                child_text = extract_structured_text(child)
                if child_text:
                    parts.append(child_text)
            text = '\n'.join(parts)

        import re

        text = re.sub(r'\n{3,}', '\n\n', text)

        paragraphs = re.split(r'\n\s*\n', text)

        MAX_PARAGRAPH_LENGTH = 300

        sentences = []
        for para in paragraphs:
            para = ' '.join(line.strip() for line in para.split('\n') if line.strip())
            if not para:
                continue

            if len(para) <= MAX_PARAGRAPH_LENGTH:
                sentences.append(para)
            else:
                parts = re.split(r'([。！？])', para)

                current_sentence = ""
                for i, part in enumerate(parts):
                    if part in '。！？':
                        current_sentence += part
                        if current_sentence.strip():
                            sentences.append(current_sentence.strip())
                        current_sentence = ""
                    else:
                        current_sentence += part

                if current_sentence.strip():
                    sentences.append(current_sentence.strip())

        if not sentences and text.strip():
            sentences = [text.strip()]

        body = soup.find('body')
        html_content = str(body) if body else str(soup)

        return {
            "href": href,
            "text": text,
            "sentences": sentences,
            "html": html_content
        }
