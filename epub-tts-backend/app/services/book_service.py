import os
import uuid
import shutil
import base64
import json
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from fastapi import UploadFile, HTTPException
from typing import List, Dict, Optional, Any
import hashlib
from datetime import datetime

UPLOAD_DIR = "data/uploads"
LIBRARY_INDEX_FILE = "data/uploads/library.json"
IMAGES_DIR = "data/images"


class BookLibrary:
    """书架管理 - 保存和管理已上传的书籍"""
    
    @staticmethod
    def _load_index() -> Dict:
        """加载书架索引"""
        if os.path.exists(LIBRARY_INDEX_FILE):
            try:
                with open(LIBRARY_INDEX_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {"books": {}}
        return {"books": {}}
    
    @staticmethod
    def _save_index(index: Dict) -> None:
        """保存书架索引"""
        os.makedirs(os.path.dirname(LIBRARY_INDEX_FILE), exist_ok=True)
        with open(LIBRARY_INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def add_book(book_id: str, metadata: Dict, cover_url: Optional[str] = None) -> None:
        """添加书籍到书架"""
        index = BookLibrary._load_index()
        index["books"][book_id] = {
            "id": book_id,
            "title": metadata.get("title", "Unknown"),
            "creator": metadata.get("creator", "Unknown"),
            "language": metadata.get("language", ""),
            "publisher": metadata.get("publisher", ""),
            "coverUrl": cover_url,
            "addedAt": datetime.now().isoformat(),
            "lastOpenedAt": datetime.now().isoformat()
        }
        BookLibrary._save_index(index)
    
    @staticmethod
    def get_all_books() -> List[Dict]:
        """获取所有书籍列表"""
        index = BookLibrary._load_index()
        books = list(index["books"].values())
        # 按最后打开时间排序（最近的在前）
        books.sort(key=lambda x: x.get("lastOpenedAt", ""), reverse=True)
        return books
    
    @staticmethod
    def get_book(book_id: str) -> Optional[Dict]:
        """获取单本书的信息"""
        index = BookLibrary._load_index()
        return index["books"].get(book_id)
    
    @staticmethod
    def update_last_opened(book_id: str) -> None:
        """更新最后打开时间"""
        index = BookLibrary._load_index()
        if book_id in index["books"]:
            index["books"][book_id]["lastOpenedAt"] = datetime.now().isoformat()
            BookLibrary._save_index(index)
    
    @staticmethod
    def delete_book(book_id: str) -> bool:
        """从书架删除书籍"""
        index = BookLibrary._load_index()
        if book_id in index["books"]:
            del index["books"][book_id]
            BookLibrary._save_index(index)
            return True
        return False


class BookService:
    @staticmethod
    def get_book_path(book_id: str) -> str:
        return os.path.join(UPLOAD_DIR, f"{book_id}.epub")

    @staticmethod
    async def save_upload(file: UploadFile) -> str:
        # Generate ID based on content hash or random
        # For simplicity, random ID
        book_id = str(uuid.uuid4())
        file_path = BookService.get_book_path(book_id)
        
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return book_id

    @staticmethod
    def parse_metadata(book_id: str) -> Dict[str, Any]:
        path = BookService.get_book_path(book_id)
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
            # Ebooklib way to find cover
            # Often it is an item with id 'cover' or check metadata
            # For simplicity, we skip complex cover extraction for now or return a placeholder
            # If we want cover, we need to extract image item and save it to static folder
            
            # Try to find cover image
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
                        cover_filename = f"{book_id}_cover.jpg" # Assume jpg/png
                        cover_path = os.path.join(UPLOAD_DIR, cover_filename)
                        with open(cover_path, "wb") as f:
                            f.write(cover_item.get_content())
                        cover_url = f"/covers/{cover_filename}"
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
    def get_toc(book_id: str) -> List[Dict[str, Any]]:
        path = BookService.get_book_path(book_id)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Book not found")
        
        try:
            book = epub.read_epub(path)
            toc = []
            
            # Recursive function to parse TOC
            def parse_nav_map(nav_point):
                try:
                    # Ebooklib TOC structure can be complex (tuple or Link object)
                    # Typically: (Link, [child_links]) or Link
                    if isinstance(nav_point, tuple) or isinstance(nav_point, list):
                        link = nav_point[0]
                        children = nav_point[1] if len(nav_point) > 1 else []
                    else:
                        link = nav_point
                        children = []
                        
                    if hasattr(link, 'href') and hasattr(link, 'title'):
                        item = {
                            "id": str(uuid.uuid4()), # Generate transient ID
                            "href": link.href,
                            "label": link.title,
                            "subitems": [parse_nav_map(c) for c in children if c is not None]
                        }
                        return item
                    return None
                except Exception as e:
                    print(f"Error parsing nav_map item: {e}")
                    return None

            # Process book.toc
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
                # Continue to fallback
            
            # Check if TOC is valid (has multiple chapters or meaningful content)
            # If TOC has only 1 item, it might be just the book title, not real chapters
            # Also check if TOC items have subitems (which would indicate real structure)
            has_real_structure = False
            toc_item_count = 0
            
            if toc:
                # Count total items including subitems
                def count_items(items):
                    count = len(items)
                    for item in items:
                        if item.get('subitems'):
                            count += count_items(item['subitems'])
                    return count
                
                toc_item_count = count_items(toc)
                # If we have at least 3 items total, or if any item has subitems, consider it valid
                has_real_structure = toc_item_count >= 3 or any(item.get('subitems') for item in toc)
            
            # Always try to get spine items for comparison
            # If TOC is empty, has only 1 item, or doesn't have real structure, use spine
            should_use_spine = not toc or toc_item_count <= 1 or not has_real_structure
            
            # Helper function to extract title from HTML content
            def extract_title_from_html(item_content: bytes) -> Optional[str]:
                """从 HTML 内容中提取标题"""
                try:
                    content_str = item_content.decode('utf-8')
                    soup = BeautifulSoup(content_str, 'html.parser')
                    
                    # 按优先级查找标题标签
                    for tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        title_tag = soup.find(tag_name)
                        if title_tag:
                            title_text = title_tag.get_text().strip()
                            if title_text and len(title_text) < 200:  # 标题不应该太长
                                return title_text
                    
                    # 查找 class 包含 title 的元素
                    title_elements = soup.find_all(class_=lambda x: x and 'title' in x.lower())
                    for elem in title_elements:
                        text = elem.get_text().strip()
                        if text and len(text) < 200:
                            return text
                    
                    # 查找第一个 strong 或 b 标签（可能是标题）
                    strong_tag = soup.find(['strong', 'b'])
                    if strong_tag:
                        text = strong_tag.get_text().strip()
                        if text and len(text) < 200:
                            return text
                    
                except Exception as e:
                    print(f"Warning: Failed to extract title from HTML: {e}")
                
                return None
            
            # Always try to get spine items (even if TOC seems valid, for comparison)
            try:
                # Try to get items from spine (reading order) - this is the most reliable method
                spine = book.spine
                spine_items = []
                chapter_num = 1
                
                for item_id, _ in spine:
                    try:
                        item = book.get_item_with_id(item_id)
                        if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                            item_name = item.get_name()
                            if item_name:
                                # 尝试从 HTML 内容中提取标题
                                label = None
                                try:
                                    item_content = item.get_content()
                                    label = extract_title_from_html(item_content)
                                except Exception as e:
                                    print(f"Warning: Failed to get content for title extraction: {e}")
                                
                                # 如果无法从 HTML 提取标题，使用文件名
                                if not label:
                                    label = os.path.basename(item_name)
                                    # Remove common extensions
                                    label = label.replace('.html', '').replace('.xhtml', '').replace('.htm', '')
                                    
                                    # 如果文件名看起来像 "part007_split_000" 这样的格式，使用章节编号
                                    if not label or label.isdigit() or ('part' in label.lower() and 'split' in label.lower()):
                                        label = f"第 {chapter_num} 章"
                                    else:
                                        # Clean up the label
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
                    # Replace TOC if:
                    # 1. TOC is empty
                    # 2. TOC has only 1 item (likely just book title)
                    # 3. Spine has significantly more items
                    original_toc_count = len(toc) if toc else 0
                    if should_use_spine or len(spine_items) > max(original_toc_count, 2):
                        toc = spine_items
                        print(f"Using spine: {len(spine_items)} chapters (replaced {original_toc_count} TOC items, should_use_spine={should_use_spine})")
                    else:
                        print(f"Keeping TOC ({original_toc_count} items), spine has {len(spine_items)} items")
            except Exception as e:
                print(f"Warning: Error getting items from spine: {e}")
            
            # If still empty, try to get all document items
            if not toc:
                try:
                    all_items = []
                    chapter_num = 1
                    for item in book.get_items():
                        try:
                            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                                item_name = item.get_name()
                                if item_name:
                                    # Skip common non-content files
                                    if any(skip in item_name.lower() for skip in ['cover', 'titlepage', 'toc', 'nav']):
                                        continue
                                    
                                    # 尝试从 HTML 内容中提取标题
                                    label = None
                                    try:
                                        item_content = item.get_content()
                                        label = extract_title_from_html(item_content)
                                    except Exception as e:
                                        print(f"Warning: Failed to get content for title extraction: {e}")
                                    
                                    # 如果无法从 HTML 提取标题，使用文件名
                                    if not label:
                                        label = os.path.basename(item_name)
                                        label = label.replace('.html', '').replace('.xhtml', '').replace('.htm', '')
                                        
                                        # 如果文件名看起来像 "part007_split_000" 这样的格式，使用章节编号
                                        if not label or label.isdigit() or ('part' in label.lower() and 'split' in label.lower()):
                                            label = f"第 {chapter_num} 章"
                                        else:
                                            # Clean up the label
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
    def get_first_available_chapter(book_id: str) -> Optional[Dict[str, Any]]:
        """获取第一个可用的章节（当 TOC 为空时使用）"""
        path = BookService.get_book_path(book_id)
        if not os.path.exists(path):
            return None
        
        try:
            book = epub.read_epub(path)
            
            # 优先从 spine 获取（阅读顺序）
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
            
            # 回退：获取任何文档项
            for item in book.get_items():
                try:
                    if item.get_type() == ebooklib.ITEM_DOCUMENT:
                        item_name = item.get_name()
                        if item_name:
                            # 跳过常见非内容文件
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
        except Exception as e:
            import traceback
            error_detail = f"Failed to parse EPUB TOC: {str(e)}"
            print(f"Error parsing TOC: {error_detail}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=error_detail)

    @staticmethod
    def extract_images(book_id: str) -> Dict[str, str]:
        """
        提取书籍中的所有图片，保存到静态目录
        返回: {原始路径: 服务器URL} 的映射
        """
        path = BookService.get_book_path(book_id)
        if not os.path.exists(path):
            return {}
        
        # 创建书籍专属的图片目录
        book_images_dir = os.path.join(IMAGES_DIR, book_id)
        os.makedirs(book_images_dir, exist_ok=True)
        
        # 检查是否已提取过（存在映射文件）
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
                original_name = item.get_name()  # e.g., "images/fig1.png" or "OEBPS/Images/cover.jpg"
                
                # 生成安全的文件名
                ext = os.path.splitext(original_name)[1].lower() or '.jpg'
                safe_name = hashlib.md5(original_name.encode()).hexdigest()[:12] + ext
                
                # 保存图片
                image_path = os.path.join(book_images_dir, safe_name)
                with open(image_path, "wb") as f:
                    f.write(item.get_content())
                
                # 记录映射：原始路径 -> 服务器URL
                # 需要处理多种可能的原始路径格式
                server_url = f"/images/{book_id}/{safe_name}"
                
                # 保存多种可能的键（EPUB 内部引用可能用不同格式）
                image_mapping[original_name] = server_url
                # 也保存不带目录的文件名
                base_name = os.path.basename(original_name)
                image_mapping[base_name] = server_url
                # 保存相对路径变体
                if original_name.startswith('OEBPS/'):
                    image_mapping[original_name[6:]] = server_url
                if original_name.startswith('OPS/'):
                    image_mapping[original_name[4:]] = server_url
                    
            except Exception as e:
                print(f"[BookService] Failed to extract image {item.get_name()}: {e}")
        
        # 保存映射文件
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(image_mapping, f, ensure_ascii=False, indent=2)
        
        return image_mapping

    @staticmethod
    def get_chapter_content(book_id: str, href: str) -> Dict[str, Any]:
        path = BookService.get_book_path(book_id)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Book not found")
        
        # 先提取图片（如果尚未提取）
        image_mapping = BookService.extract_images(book_id)
            
        book = epub.read_epub(path)
        
        # Href might contain anchor like chapter1.html#section1
        # ebooklib items are keyed by filename usually
        anchor = None
        if '#' in href:
            base_href, anchor = href.split('#', 1)
        else:
            base_href = href
        
        # 获取章节的目录路径（用于解析相对路径）
        chapter_dir = os.path.dirname(base_href)
        
        # Find item by href
        target_item = None
        for item in book.get_items():
            item_name = item.get_name()
            # 尝试多种匹配方式
            if item_name == base_href or item_name.endswith('/' + base_href) or base_href.endswith(item_name):
                target_item = item
                break
                
        if not target_item:
            # Try searching by ID if href failed?
            # Or try relative paths logic
            raise HTTPException(status_code=404, detail=f"Chapter {href} not found")
            
        # Parse HTML content
        content = target_item.get_content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # 处理图片：替换 src 为服务器 URL
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if not src:
                continue
            
            # 尝试多种路径匹配
            server_url = None
            
            # 1. 直接匹配
            if src in image_mapping:
                server_url = image_mapping[src]
            # 2. 解析相对路径
            elif chapter_dir:
                full_path = os.path.normpath(os.path.join(chapter_dir, src)).replace('\\', '/')
                if full_path in image_mapping:
                    server_url = image_mapping[full_path]
            # 3. 只匹配文件名
            if not server_url:
                base_name = os.path.basename(src)
                if base_name in image_mapping:
                    server_url = image_mapping[base_name]
            
            if server_url:
                img['src'] = server_url
                # 添加一些默认样式
                img['style'] = img.get('style', '') + '; max-width: 100%; height: auto;'
        
        # 如果有锚点，尝试定位到特定元素
        target_element = None
        if anchor:
            # 尝试通过 id 查找
            target_element = soup.find(id=anchor)
            # 如果没找到，尝试通过 name 属性查找
            if not target_element:
                target_element = soup.find(attrs={"name": anchor})
        
        # 提取文本（保留结构）
        heading_tags = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
        block_tags = {'p', 'div', 'section', 'article', 'blockquote'}
        list_tags = {'ul', 'ol', 'nav', 'dl'}
        list_item_tags = {'li', 'dt', 'dd'}
        
        def extract_structured_text(element):
            """递归提取文本，保留结构"""
            if element is None:
                return ""
            
            # 处理字符串节点
            if isinstance(element, str) or hasattr(element, 'strip') and not hasattr(element, 'name'):
                text = str(element).strip()
                return text if text else ""
            
            # 没有 name 属性的节点
            if not hasattr(element, 'name') or element.name is None:
                if hasattr(element, 'get_text'):
                    return element.get_text().strip()
                return str(element).strip()
            
            tag_name = element.name
            
            # 标题标签：前后加双换行
            if tag_name in heading_tags:
                text = element.get_text(separator=' ').strip()
                return f"\n\n{text}\n\n" if text else ""
            
            # 列表容器：递归处理子元素
            if tag_name in list_tags:
                parts = []
                for child in element.children:
                    child_text = extract_structured_text(child)
                    if child_text:
                        parts.append(child_text)
                return '\n'.join(parts)
            
            # 列表项：每项单独一行
            if tag_name in list_item_tags:
                text = element.get_text(separator=' ').strip()
                return f"{text}\n" if text else ""
            
            # 块级元素：内容后加换行
            if tag_name in block_tags:
                text = element.get_text(separator=' ').strip()
                return f"{text}\n" if text else ""
            
            # 其他元素：递归处理子元素
            if hasattr(element, 'children'):
                parts = []
                for child in element.children:
                    child_text = extract_structured_text(child)
                    if child_text:
                        parts.append(child_text)
                return ' '.join(parts) if parts else ""
            
            # 兜底：直接获取文本
            if hasattr(element, 'get_text'):
                return element.get_text(separator=' ').strip()
            return ""
        
        if target_element:
            # 找到锚点元素后，提取该元素及其后续兄弟元素的内容
            parts = [extract_structured_text(target_element)]
            
            # 获取后续兄弟元素，直到遇到下一个标题标签
            for sibling in target_element.find_next_siblings():
                if hasattr(sibling, 'name') and sibling.name in heading_tags and sibling.get('id'):
                    break
                sibling_text = extract_structured_text(sibling)
                if sibling_text:
                    parts.append(sibling_text)
            
            text = '\n'.join(parts)
        else:
            # 没有锚点或找不到锚点元素，遍历 body 的直接子元素
            body = soup.find('body') or soup
            parts = []
            for child in body.children:
                child_text = extract_structured_text(child)
                if child_text:
                    parts.append(child_text)
            text = '\n'.join(parts)
        
        # 保持原始段落结构，不做额外分句
        import re
        
        # 清理多余的空行
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 按段落分割（双换行分隔）
        paragraphs = re.split(r'\n\s*\n', text)
        
        # 最大段落长度（超过则按句号分割）
        MAX_PARAGRAPH_LENGTH = 300
        
        # 每个段落作为一个独立单元，超长段落按句号分割
        sentences = []
        for para in paragraphs:
            # 合并段落内的换行
            para = ' '.join(line.strip() for line in para.split('\n') if line.strip())
            if not para:
                continue
            
            # 如果段落不超过 300 字，保持原样
            if len(para) <= MAX_PARAGRAPH_LENGTH:
                sentences.append(para)
            else:
                # 超长段落：按全角标点（。！？）分割
                # 使用正则保留分隔符
                parts = re.split(r'([。！？])', para)
                
                # 重新组合：把标点符号附加到前面的句子
                current_sentence = ""
                for i, part in enumerate(parts):
                    if part in '。！？':
                        current_sentence += part
                        if current_sentence.strip():
                            sentences.append(current_sentence.strip())
                        current_sentence = ""
                    else:
                        current_sentence += part
                
                # 处理最后一部分（可能没有标点结尾）
                if current_sentence.strip():
                    sentences.append(current_sentence.strip())
        
        # 如果没有段落，返回整个文本
        if not sentences and text.strip():
            sentences = [text.strip()]
        
        # 提取处理后的 HTML 内容（包含正确的图片 URL）
        body = soup.find('body')
        html_content = str(body) if body else str(soup)
        
        return {
            "href": href,
            "text": text,
            "sentences": sentences,
            "html": html_content  # 包含图片的 HTML 内容
        }
