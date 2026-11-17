import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parents[1] / "video-archiver"))

from facebook_publisher import FacebookConfig, FacebookPagePublisher, carregar_legendas  # noqa: E402


class FakeResponse:
    ok = True
    text = ""

    @staticmethod
    def json():
        return {"id": "video-123"}


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        return FakeResponse()


class FacebookPublisherTests(unittest.TestCase):
    def test_carrega_manifesto_json_com_descricao_completa(self):
        with TemporaryDirectory() as directory:
            manifesto = Path(directory) / "DESCRICOES.txt"
            manifesto.write_text('{"video":"a.mp4","description":"linha 1\\nlinha 2"}\n', encoding="utf-8")
            self.assertEqual(carregar_legendas(manifesto)["a.mp4"], "linha 1\nlinha 2")

    def test_agenda_video_sem_expor_token_no_endpoint(self):
        with TemporaryDirectory() as directory:
            video = Path(directory) / "a.mp4"
            video.write_bytes(b"video")
            session = FakeSession()
            publisher = FacebookPagePublisher(FacebookConfig("page-1", "secret-token"), session)
            scheduled = datetime.now(timezone.utc) + timedelta(minutes=30)
            self.assertEqual(publisher.schedule_video(video, "legenda", scheduled), "video-123")
            endpoint, kwargs = session.calls[0]
            self.assertIn("page-1/videos", endpoint)
            self.assertEqual(kwargs["data"]["description"], "legenda")
            self.assertNotIn("secret-token", endpoint)


if __name__ == "__main__":
    unittest.main()
