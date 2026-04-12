import cloudinary
import cloudinary.uploader
from flask import current_app


ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
DEFAULT_AVATAR_FOLDER = "tickethub/avatars"
DEFAULT_EVENT_IMAGE_FOLDER = "tickethub/events"


class CloudinaryService:
    def is_configured(self):
        config = cloudinary.config()
        return bool(config.cloud_name and config.api_key and config.api_secret)

    def _upload_image(self, file_storage, folder, invalid_type_message, upload_failed_message):
        if file_storage is None or not getattr(file_storage, "filename", ""):
            return None, None

        if (file_storage.mimetype or "").lower() not in ALLOWED_IMAGE_MIME_TYPES:
            return None, invalid_type_message

        if not self.is_configured():
            return None, (
                "Cloudinary chua duoc cau hinh. Hay them vao .env mot trong hai cach: "
                "(1) CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET "
                "hoac (2) CLOUDINARY_URL."
            )

        try:
            response = cloudinary.uploader.upload(
                file_storage,
                folder=folder,
                resource_type="image",
            )
        except Exception:
            current_app.logger.exception("Cloudinary image upload failed")
            return None, upload_failed_message

        return {
            "url": response.get("secure_url"),
            "public_id": response.get("public_id"),
        }, None

    def upload_avatar(self, file_storage, folder=DEFAULT_AVATAR_FOLDER):
        return self._upload_image(
            file_storage=file_storage,
            folder=folder,
            invalid_type_message="Anh dai dien chi chap nhan JPG, PNG hoac WEBP.",
            upload_failed_message="Khong the tai anh dai dien len Cloudinary. Vui long thu lai.",
        )

    def upload_event_image(self, file_storage, folder=DEFAULT_EVENT_IMAGE_FOLDER):
        return self._upload_image(
            file_storage=file_storage,
            folder=folder,
            invalid_type_message="Anh su kien chi chap nhan JPG, PNG hoac WEBP.",
            upload_failed_message="Khong the tai anh su kien len Cloudinary. Vui long thu lai.",
        )


cloudinary_service = CloudinaryService()