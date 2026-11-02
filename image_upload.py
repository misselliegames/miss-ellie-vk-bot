"""Single-image VkUpload adapter with safe, stage-specific diagnostics."""
import re

import vk_api


def log_upload_error(stage, exc, secrets=()):
    # ApiError.__str__ may include request data. Only use its error message.
    error = getattr(exc, "error", None)
    message = str(error.get("error_msg", "VK API error")) if isinstance(error, dict) else str(exc)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    message = re.sub(r"https?://[^\s\"'<>]+", "[URL REDACTED]", message, flags=re.I)
    message = re.sub(r"(?i)(access_token|token|access_key|hash|photo|file|sig|secret)([\s\"']*[:=][\s\"']*)[^\s,;&}]+", r"\1\2[REDACTED]", message)
    message = message.replace("\n", " ").replace("\r", " ")[:600]
    print(f"IMAGE_UPLOAD_FAILED stage={stage} type={type(exc).__name__} message={message}", flush=True)


class MessagePhotoUpload(vk_api.VkUpload):
    """The vk_api 11.10.0 photo_messages protocol for one local image.

    Keep its multipart field/filename conventions, but expose the failing stage
    and reject empty upload responses before calling saveMessagesPhoto.
    """

    def __init__(self, session, secrets=()):
        super().__init__(session)
        self.secrets = secrets

    def photo_messages(self, photos, peer_id=None):
        stage = "get upload server"
        try:
            url = self.vk.photos.getMessagesUploadServer(peer_id=peer_id)["upload_url"]
            stage = "POST image"
            with open(photos, "rb") as image:
                extension = str(photos).rsplit(".", 1)[-1]
                response = self.http.post(
                    url, files=[("file0", (f"file0.{extension}", image))], timeout=45,
                )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("photo") or payload["photo"] == "[]":
                raise ValueError("VK upload returned empty photo (HTTP POST succeeded)")
            stage = "saveMessagesPhoto"
            result = self.vk.photos.saveMessagesPhoto(**payload)
            if not result:
                raise ValueError("VK returned no saved photo")
            return result
        except Exception as exc:
            log_upload_error(stage, exc, self.secrets)
            raise

    def document_message(self, doc, title=None, tags=None, peer_id=None):
        stage = "get upload server (document)"
        try:
            url = self.vk.docs.getMessagesUploadServer(peer_id=peer_id)["upload_url"]
            stage = "POST image (document)"
            with open(doc, "rb") as image:
                extension = str(doc).rsplit(".", 1)[-1]
                response = self.http.post(
                    url, files=[("file", (f"file0.{extension}", image))], timeout=45,
                )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("file"):
                raise ValueError("VK document upload returned no file")
            stage = "docs.save"
            result = self.vk.docs.save(**payload, title=title, tags=tags)
            if result.get("type") != "doc" or not result.get("doc", {}).get("id"):
                raise ValueError("VK returned no saved document")
            return result
        except Exception as exc:
            log_upload_error(stage, exc, self.secrets)
            raise
