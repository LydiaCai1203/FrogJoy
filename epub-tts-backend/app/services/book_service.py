import os
import re
import uuid
import shutil
import json
import ebooklib
from ebooklib import epub
from loguru import logger
from bs4 import BeautifulSoup
from fastapi import UploadFile, HTTPException
from typing import List, Dict, Optional, Any
import hashlib

from shared.config import settings

IMAGES_DIR = "data/images"

# 章节标题正则 — 用于单文件 EPUB 自动拆章
_CHAPTER_HEADING_RE = re.compile(
    r'^(?:'
    r'第[一二三四五六七八九十百千万零○〇\d]+[章回节篇卷集部]'  # 中文: 第X章/回/节/篇/卷
    r'|Chapter\s+\d+'                                          # English
    r'|CHAPTER\s+\d+'
    r')'
)


def _detect_chapters_in_html(html_content: bytes | str) -> list[dict]:
    """扫描单个 HTML 文件, 检测章节标题模式, 返回虚拟章节列表.

    Returns:
        [{label, para_index}, ...] 其中 para_index 是该章节标题在 <p> 序列中的位置.
        如果检测不到 ≥2 个章节, 返回空列表(不做拆分).
    """
    if isinstance(html_content, bytes):
        html_content = html_content.decode('utf-8', errors='replace')

    soup = BeautifulSoup(html_content, 'html.parser')
    body = soup.find('body') or soup

    chapters = []
    para_index = 0

    for el in body.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        text = el.get_text().strip()
        if not text:
            para_index += 1
            continue
        if _CHAPTER_HEADING_RE.match(text):
            # 提取章节标题: 取整段文字, 但截断过长的
            label = text[:50].strip()
            chapters.append({"label": label, "para_index": para_index})
        para_index += 1

    return chapters if len(chapters) >= 2 else []


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
                # 1. Try OPF metadata: <meta name="cover" content="manifest-id"/>
                cover_meta = book.get_metadata('OPF', 'cover')
                if not cover_meta:
                    opf_meta = book.metadata.get('http://www.idpf.org/2007/opf', {}).get('meta', [])
                    for val, attrs in opf_meta:
                        if attrs.get('name') == 'cover' and attrs.get('content'):
                            cover_meta = [(attrs['content'], {})]
                            break
                if cover_meta:
                    manifest_id = cover_meta[0][0]
                    item = book.get_item_with_id(manifest_id)
                    if item and item.get_content():
                        cover_item = item

                # 2. Fallback: search ITEM_COVER type
                if not cover_item:
                    for item in book.get_items_of_type(ebooklib.ITEM_COVER):
                        if item.get_content():
                            cover_item = item
                            break

                # 3. Fallback: search ITEM_IMAGE by name/id containing 'cover'
                if not cover_item:
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
                        logger.warning(f"Failed to extract cover image: {e}")
                        cover_url = None
            except Exception as e:
                logger.warning(f"Error while searching for cover: {e}")
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

            # 收集 EPUB 中明确标记为封面/纯导航的文件（不应出现在章节列表）
            # 以及 guide 里各文件对应的标题（用于 spine fallback 时提供可读标签）
            nav_hrefs = set()      # 应当跳过的文件（封面等无内容页）
            guide_titles = {}      # href → guide title，spine fallback 时用
            try:
                # EPUB3: manifest item 有 properties="nav"（纯导航文档，无阅读内容）
                for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                    props = getattr(item, 'properties', '') or ''
                    if 'nav' in props.lower():
                        nav_hrefs.add(item.get_name())
                # EPUB2: guide 里的 cover / title-page 跳过；toc 保留但记录其标题
                for guide_item in getattr(book, 'guide', []) or []:
                    guide_type = (guide_item.get('type') or '').lower()
                    href = guide_item.get('href', '').split('#')[0]
                    title = guide_item.get('title', '')
                    if href:
                        guide_titles[href] = title
                    if guide_type in ('cover', 'title-page'):
                        nav_hrefs.add(href)
            except Exception:
                pass

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
                            logger.warning(f" Failed to parse TOC item: {e}")
                            continue
            except Exception as e:
                logger.warning(f" Error processing TOC: {e}")

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
                    logger.warning(f" Failed to extract title from HTML: {e}")

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
                                if item_name in nav_hrefs or any(skip in item_name.lower() for skip in ['cover', 'titlepage', 'toc', 'nav']):
                                    continue

                                label = None
                                try:
                                    item_content = item.get_content()
                                    label = extract_title_from_html(item_content)
                                except Exception as e:
                                    logger.warning(f" Failed to get content for title extraction: {e}")

                                if not label:
                                    # 优先用 guide 里记录的标题（如 "Table of Contents"）
                                    label = guide_titles.get(item_name) or None

                                if not label:
                                    label = os.path.basename(item_name)
                                    label = label.replace('.html', '').replace('.xhtml', '').replace('.htm', '')

                                    if not label or label.isdigit() or re.match(r'^(part|split|chapter|chap|section|seg)[\d_\-]*$', label.lower()):
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
                        logger.warning(f" Failed to get spine item {item_id}: {e}")
                        continue

                if spine_items:
                    original_toc_count = len(toc) if toc else 0
                    if should_use_spine:
                        toc = spine_items
                        print(f"Using spine: {len(spine_items)} chapters (replaced {original_toc_count} TOC items)")
                    else:
                        print(f"Keeping TOC ({original_toc_count} items), spine has {len(spine_items)} items")
            except Exception as e:
                logger.warning(f" Error getting items from spine: {e}")

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
                                        logger.warning(f" Failed to get content for title extraction: {e}")

                                    if not label:
                                        label = os.path.basename(item_name)
                                        label = label.replace('.html', '').replace('.xhtml', '').replace('.htm', '')

                                        if not label or label.isdigit() or re.match(r'^(part|split|chapter|chap|section|seg)[\d_\-]*$', label.lower()):
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
                            logger.warning(f" Failed to process item: {e}")
                            continue

                    if all_items:
                        toc = all_items
                        print(f"Using all items fallback: {len(toc)} chapters")
                except Exception as e:
                    logger.warning(f" Last resort failed: {e}")

            # ---- 单文件自动拆章 ----
            # 过滤掉封面等非正文条目, 看实际内容条目数
            content_toc = [
                t for t in toc
                if not any(skip in t.get('href', '').lower()
                           for skip in ['cover', 'titlepage', 'toc', 'nav'])
            ]
            if len(content_toc) <= 2:
                # 尝试对每个内容文件做章节检测
                for toc_item in content_toc:
                    try:
                        item_href = toc_item['href'].split('#')[0]
                        target = None
                        for item in book.get_items():
                            n = item.get_name()
                            if n == item_href or n.endswith('/' + item_href) or item_href.endswith(n):
                                target = item
                                break
                        if not target:
                            continue

                        detected = _detect_chapters_in_html(target.get_content())
                        if detected:
                            virtual_toc = []
                            for i, ch in enumerate(detected):
                                virtual_toc.append({
                                    "id": str(uuid.uuid4()),
                                    "href": f"{target.get_name()}#__auto_ch:{i}",
                                    "label": ch['label'],
                                    "subitems": []
                                })
                            # 替换原来的单条目
                            toc = [t for t in toc if t is not toc_item] + virtual_toc
                            # 保持顺序: 封面在前, 虚拟章节在后
                            toc = [t for t in toc if '__auto_ch:' not in t.get('href', '')] + virtual_toc
                            print(f"Auto-split single file into {len(detected)} virtual chapters")
                    except Exception as e:
                        logger.warning(f"Auto chapter detection failed: {e}")

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
    def flatten_toc(toc: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Flatten a hierarchical TOC into a flat list with only href and label."""
        result = []
        for item in toc:
            result.append({"href": item["href"], "label": item["label"]})
            if item.get("subitems"):
                result.extend(BookService.flatten_toc(item["subitems"]))
        return result

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
                logger.info(f"[BookService] Failed to extract image {item.get_name()}: {e}")

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

        # ---- 处理 __auto_ch:N 虚拟锚点 ----
        auto_ch_index = None
        if anchor and anchor.startswith('__auto_ch:'):
            try:
                auto_ch_index = int(anchor.split(':')[1])
            except (ValueError, IndexError):
                pass

        if auto_ch_index is not None:
            # 用同样的检测逻辑拆分, 只返回第 N 章的内容
            detected = _detect_chapters_in_html(content)
            if detected and auto_ch_index < len(detected):
                body = soup.find('body') or soup
                all_elements = body.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

                start_para = detected[auto_ch_index]['para_index']
                end_para = (detected[auto_ch_index + 1]['para_index']
                            if auto_ch_index + 1 < len(detected)
                            else len(all_elements))

                blocks = []
                for el in all_elements[start_para:end_para]:
                    text = ' '.join(el.get_text(separator=' ').split())
                    if text:
                        blocks.append(text)
            else:
                blocks = []
        else:
            # ---- 正常锚点/无锚点逻辑 ----
            target_element = None
            if anchor:
                target_element = soup.find(id=anchor)
                if not target_element:
                    target_element = soup.find(attrs={"name": anchor})

            heading_tags = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
            leaf_block_tags = {'p', 'blockquote', 'li', 'dt', 'dd', 'tr'}
            container_tags = {'div', 'section', 'article', 'ul', 'ol', 'nav', 'dl',
                              'table', 'thead', 'tbody', 'tfoot'}
            all_block_tags = heading_tags | leaf_block_tags | container_tags

            def collect_blocks(element):
                """Walk DOM tree, collect each block-level element as one text block."""
                blocks = []
                if element is None:
                    return blocks

                # Text node
                if not hasattr(element, 'name') or element.name is None:
                    text = element.get_text().strip() if hasattr(element, 'get_text') else str(element).strip()
                    if text:
                        blocks.append(text)
                    return blocks

                tag = element.name

                # If this block element has block-level children, recurse into them
                has_block_children = any(
                    hasattr(c, 'name') and c.name in all_block_tags
                    for c in element.children
                )

                if tag in (heading_tags | leaf_block_tags) and not has_block_children:
                    # Leaf block: collect as single text block
                    text = ' '.join(element.get_text(separator=' ').split())
                    if text:
                        blocks.append(text)
                else:
                    # Container or block-with-sub-blocks: recurse
                    for child in element.children:
                        blocks.extend(collect_blocks(child))

                return blocks

            if target_element:
                elements = [target_element]
                for sibling in target_element.find_next_siblings():
                    if hasattr(sibling, 'name') and sibling.name in heading_tags and sibling.get('id'):
                        break
                    elements.append(sibling)
                blocks = []
                for el in elements:
                    blocks.extend(collect_blocks(el))
            else:
                body = soup.find('body') or soup
                blocks = []
                for child in body.children:
                    blocks.extend(collect_blocks(child))

        text = '\n\n'.join(blocks)

        MAX_PARAGRAPH_LENGTH = 300

        sentences = []
        for block in blocks:
            if not block:
                continue
            if len(block) <= MAX_PARAGRAPH_LENGTH:
                sentences.append(block)
            else:
                parts = re.split(r'([。！？][）)」】\u201d\u2019"\'\]》〉]*)', block)
                current_sentence = ""
                for part in parts:
                    if re.match(r'^[。！？]', part):
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
