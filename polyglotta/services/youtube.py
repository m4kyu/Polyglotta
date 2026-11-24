"""Read video metadata from the public YouTube watch page."""
import json
import re
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.request import Request, urlopen


class MetadataUnavailable(Exception):
    pass


class WatchPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = None
        self.seconds = None
        self.live = False

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        attrs = dict(attrs)
        content = attrs.get("content") or ""
        if attrs.get("property") == "og:title":
            self.title = content.strip()
        if attrs.get("itemprop") == "duration":
            match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", content)
            if match:
                h, m, s = (int(unit or 0) for unit in match.groups())
                self.seconds = h * 3600 + m * 60 + s

    def handle_data(self, data):
        match = re.search(r"\bytInitialPlayerResponse\s*=\s*(?=\{)", data)
        if not match:
            return
        try:
            response, _ = json.JSONDecoder().raw_decode(data, match.end())
        except ValueError:
            return
        details = response.get("videoDetails") or {}
        self.live = bool(details.get("isLive"))
        self.title = details.get("title") or self.title
        duration = details.get("lengthSeconds")
        if duration and str(duration).isdigit():
            self.seconds = int(duration)


def video_metadata(video_id: str):
    request = Request(f"https://www.youtube.com/watch?v={video_id}",
                      headers={"Accept-Language": "en", "User-Agent": "Mozilla/5.0"})
    page = WatchPage()
    try:
        with urlopen(request, timeout=8) as response:
            page.feed(response.read(4 * 1024 * 1024).decode("utf-8", errors="replace"))
    except (OSError, URLError) as error:
        raise MetadataUnavailable from error
    if not page.title or page.title == "YouTube":
        raise MetadataUnavailable
    return {"title": page.title, "duration_seconds": None if page.live else page.seconds or None}
