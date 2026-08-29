def select_material(items, book_name):
    target = str(book_name or "").strip()
    names = [(item, str(item.get("filename") or item.get("name") or "").rsplit(".", 1)[0].strip()) for item in items]
    exact = [item for item, name in names if name == target]
    candidates = exact or [item for item, name in names if target in name]
    if not candidates: return None
    from .qianchuan_client import material_created_key
    return max(candidates, key=material_created_key)


def parse_program_fields(program_link, start_page):
    text = str(program_link or "").strip()
    fallback = str(start_page or "").strip()
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]
    if "\t" in text:
        path, params = text.split("\t", 1)
        return path.strip(), params.strip()
    if len(lines) >= 2:
        return lines[0], lines[1]
    if "?" in text:
        path, params = text.split("?", 1)
        return path.strip(), params.strip()
    if text == "pages/novel_plugin/index" and fallback:
        if "?" in fallback:
            _, params = fallback.split("?", 1)
            return text, params.strip()
        if "=" in fallback:
            return text, fallback
    if text.startswith("book_id=") or text.startswith("bookId="):
        return "pages/novel_plugin/index", text
    raise ValueError(f"unsupported program link format: {text}")


def cover_id(video):
    value = str(video.get("video_cover_id") or video.get("cover_id") or "")
    if value:
        return value
    from urllib.parse import urlparse
    path = urlparse(str(video.get("poster_url") or "")).path.lstrip("/").split("~", 1)[0]
    return path


def posted_time(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")
