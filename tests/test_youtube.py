import io
import unittest
from unittest.mock import patch

from polyglotta.services.youtube import MetadataUnavailable, video_metadata


class VideoMetadataTests(unittest.TestCase):
    def lookup(self, html):
        with patch("polyglotta.services.youtube.urlopen", return_value=io.BytesIO(html.encode())):
            return video_metadata("jNQXAC9IVRw")

    def test_watch_page(self):
        data = self.lookup('<script>var ytInitialPlayerResponse = {"videoDetails":'
                           '{"title":"A short film","lengthSeconds":"91"}};</script>')
        self.assertEqual(data, {"title": "A short film", "duration_seconds": 91})

    def test_metadata_tags(self):
        data = self.lookup('<meta property="og:title" content="Tea &amp; coffee">'
                           '<meta itemprop="duration" content="PT1H2M3S">')
        self.assertEqual(data, {"title": "Tea & coffee", "duration_seconds": 3723})

    def test_live_video(self):
        data = self.lookup('<script>var ytInitialPlayerResponse = {"videoDetails":'
                           '{"title":"Live stream","isLive":true,"lengthSeconds":"120"}};</script>')
        self.assertIsNone(data["duration_seconds"])

    def test_unavailable_page(self):
        with self.assertRaises(MetadataUnavailable):
            self.lookup("<title>Consent required</title>")
