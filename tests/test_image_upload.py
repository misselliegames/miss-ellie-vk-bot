import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.fake_vk import install

install()
import bot
from image_upload import EmptyPhotoUpload, MessagePhotoUpload, log_upload_error
from PIL import Image


class ImageUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "image.png"
        Image.new("RGBA", (4, 4), (0, 0, 0, 0)).save(self.path)
        bot.PHOTO_CACHE.clear()

    def uploader(self):
        uploader = object.__new__(MessagePhotoUpload)
        uploader.secrets = ("secret-token",)
        uploader.vk = SimpleNamespace(photos=Mock())
        uploader.vk.photos.getMessagesUploadServer.return_value = {"upload_url": "https://upload.invalid/?token=secret-token"}
        uploader.vk.photos.saveMessagesPhoto.return_value = [{"owner_id": 1, "id": 2}]
        uploader.http = Mock()
        uploader.http.post.return_value.json.return_value = {"photo": "payload", "server": 1, "hash": "secret-hash"}
        return uploader

    def test_peer_and_protocol(self):
        uploader = self.uploader()
        result = uploader.photo_messages(str(self.path), peer_id=123)
        self.assertEqual(2, result[0]["id"])
        uploader.vk.photos.getMessagesUploadServer.assert_called_once_with(peer_id=123)
        uploader.vk.photos.saveMessagesPhoto.assert_called_once_with(photo="payload", server=1, hash="secret-hash")
        file = uploader.http.post.call_args.kwargs["files"][0]
        self.assertEqual("file0", file[0])
        self.assertTrue(file[1][1].closed)

    def test_failure_stages_and_empty_response(self):
        for stage in ("get upload server", "POST image", "saveMessagesPhoto", "empty"):
            with self.subTest(stage=stage):
                uploader = self.uploader()
                if stage == "get upload server":
                    uploader.vk.photos.getMessagesUploadServer.side_effect = RuntimeError("failed")
                elif stage == "POST image":
                    uploader.http.post.side_effect = RuntimeError("failed")
                elif stage == "saveMessagesPhoto":
                    uploader.vk.photos.saveMessagesPhoto.side_effect = RuntimeError("failed")
                else:
                    uploader.http.post.return_value.json.return_value = {"photo": "[]"}
                output = io.StringIO()
                expected_error = EmptyPhotoUpload if stage == "empty" else RuntimeError
                with contextlib.redirect_stdout(output), self.assertRaises(expected_error):
                    uploader.photo_messages(str(self.path), peer_id=123)
                self.assertIn("stage=" + ("POST image" if stage == "empty" else stage), output.getvalue())
                if stage == "empty":
                    uploader.vk.photos.saveMessagesPhoto.assert_not_called()

    def test_redacts_exception_details(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            log_upload_error("POST image", RuntimeError("secret-token https://host/?key=secret-url hash=secret-hash"), ("secret-token",))
        for secret in ("secret-token", "secret-url", "secret-hash"):
            self.assertNotIn(secret, output.getvalue())
        self.assertIn("RuntimeError", output.getvalue())

    def test_shared_jpeg_fallback_peer_cache_access_key_and_cleanup(self):
        paths = []
        def upload(photos, peer_id):
            self.assertIn(peer_id, (123, 456))
            paths.append(Path(photos))
            if photos.endswith(".png"):
                raise ValueError("empty photo")
            with Image.open(photos) as image:
                self.assertEqual("JPEG", image.format)
                self.assertEqual((255, 255, 255), image.getpixel((0, 0)))
            return [{"owner_id": 1, "id": peer_id, "access_key": "key"}]
        with patch.object(bot.upload, "photo_messages", side_effect=upload) as method, patch.object(bot.time, "sleep"):
            self.assertEqual("photo1_123_key", bot.upload_photo(self.path, 123))
            calls = method.call_count
            self.assertEqual("photo1_123_key", bot.upload_photo(self.path, 123))
            self.assertEqual(calls, method.call_count)
            self.assertEqual("photo1_456_key", bot.upload_photo(self.path, 456))
        self.assertTrue(all(not path.exists() for path in paths if path.suffix == ".jpg"))

    def test_failed_upload_is_not_cached(self):
        with patch.object(bot.upload, "photo_messages", side_effect=RuntimeError("failed")), patch.object(bot.upload, "document_message", side_effect=RuntimeError("failed")), patch.object(bot.time, "sleep"):
            with self.assertRaises(RuntimeError):
                bot.upload_photo(self.path, 123)
        self.assertEqual({}, bot.PHOTO_CACHE)

    def test_document_fallback_attachment_peer_and_cache(self):
        result = {"type": "doc", "doc": {"owner_id": 1, "id": 2, "access_key": "key"}}
        with patch.object(bot.upload, "photo_messages", side_effect=ValueError("empty photo")), patch.object(bot.upload, "document_message", return_value=result) as document, patch.object(bot.time, "sleep"):
            self.assertEqual("doc1_2_key", bot.upload_photo(self.path, 123))
            self.assertEqual("doc1_2_key", bot.upload_photo(self.path, 123))
            document.assert_called_once_with(doc=str(self.path), peer_id=123)

    def test_document_upload_protocol_and_stages(self):
        uploader = self.uploader()
        uploader.vk.docs = Mock()
        uploader.vk.docs.getMessagesUploadServer.return_value = {"upload_url": "https://upload.invalid/"}
        uploader.http.post.return_value.json.return_value = {"file": "secret-file"}
        result = {"type": "doc", "doc": {"owner_id": 1, "id": 2}}
        uploader.vk.docs.save.return_value = result
        self.assertEqual(result, uploader.document_message(str(self.path), peer_id=123))
        uploader.vk.docs.getMessagesUploadServer.assert_called_once_with(peer_id=123)
        uploader.vk.docs.save.assert_called_once_with(file="secret-file", title=None, tags=None)
        self.assertEqual("file", uploader.http.post.call_args.kwargs["files"][0][0])
        uploader.vk.docs.save.side_effect = RuntimeError("failed")
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(RuntimeError):
            uploader.document_message(str(self.path), peer_id=123)
        self.assertIn("stage=docs.save", output.getvalue())

    def test_existing_jpeg_is_also_reencoded(self):
        original = Path(self.temp.name) / "original.jpg"
        Image.new("RGB", (4, 4), "white").save(original)
        def upload(photos, peer_id):
            self.assertEqual(123, peer_id)
            if Path(photos) == original:
                raise ValueError("empty photo")
            with Image.open(photos) as image:
                self.assertEqual("JPEG", image.format)
            return [{"owner_id": 1, "id": 2}]
        with patch.object(bot.upload, "photo_messages", side_effect=upload), patch.object(bot.time, "sleep"):
            self.assertEqual("photo1_2", bot.upload_photo(original, 123))

    def test_empty_original_skips_retries_and_immediately_uses_jpeg(self):
        with patch.object(bot.upload, "photo_messages", side_effect=[
            EmptyPhotoUpload("empty photo"), [{"owner_id": 1, "id": 2}],
        ]) as photo, patch.object(bot.time, "sleep") as sleep:
            self.assertEqual("photo1_2", bot.upload_photo(self.path, 123))
            self.assertEqual(2, photo.call_count)
            self.assertEqual(str(self.path), photo.call_args_list[0].kwargs["photos"])
            self.assertTrue(photo.call_args_list[1].kwargs["photos"].endswith(".jpg"))
            sleep.assert_not_called()

    def test_empty_original_and_jpeg_immediately_use_document(self):
        result = {"type": "doc", "doc": {"owner_id": 1, "id": 2}}
        with patch.object(bot.upload, "photo_messages", side_effect=EmptyPhotoUpload("empty photo")) as photo, patch.object(bot.upload, "document_message", return_value=result) as document, patch.object(bot.time, "sleep") as sleep:
            self.assertEqual("doc1_2", bot.upload_photo(self.path, 123))
            self.assertEqual(2, photo.call_count)
            document.assert_called_once_with(doc=str(self.path), peer_id=123)
            sleep.assert_not_called()

    def test_other_upload_errors_still_retry(self):
        with patch.object(bot.upload, "photo_messages", side_effect=[
            RuntimeError("temporary failure"), [{"owner_id": 1, "id": 2}],
        ]) as photo, patch.object(bot.time, "sleep") as sleep:
            self.assertEqual("photo1_2", bot.upload_photo(self.path, 123))
            self.assertEqual(2, photo.call_count)
            self.assertEqual(photo.call_args_list[0], photo.call_args_list[1])
            sleep.assert_called_once_with(0.6)
