import cloudinary.uploader

class CloudinaryService:
    def upload(self, file, folder="uploads"):
        try:
            response = cloudinary.uploader.upload(
                file,
                folder=folder,
                resource_type="image"
            )
            return {
            "url": response["secure_url"],
            "public_id": response["public_id"]
            }
        except Exception as e:
            print("Upload failed:", e)
            return None