import base64
import binascii
import json
import os
import tempfile

import numpy as np
from flask import current_app
from deepface import DeepFace


# Model mặc định để trích xuất đặc trưng khuôn mặt
# Facenet512: trích xuất vector 512 chiều đặc trưng khuôn mặt
DEFAULT_FACE_MODEL = "Facenet512"

# Backend để phát hiện khuôn mặt trong ảnh
DEFAULT_DETECTOR_BACKEND = "opencv"


def _strip_data_url_prefix(value: str) -> str:
    """
    Lấy phần dữ liệu base64 từ định dạng data URL.
    
    Ví dụ input: "data:image/jpeg;base64,/9j/4AAQSkZJRgABA..."
    Output: "/9j/4AAQSkZJRgABA..."
    """
    text = str(value or "").strip()
    # Kiểm tra xem có dấu "," và bắt đầu bằng "data:image" không
    if "," in text and text.lower().startswith("data:image"):
        # Tách phần sau dấu "," (phần base64 thực tế)
        return text.split(",", 1)[1]
    return text


def decode_base64_image(face_image_base64: str) -> bytes:
    """
    Giải mã chuỗi base64 thành bytes của ảnh.
    
    Input: "data:image/jpeg;base64,/9j/4AAQSkZIRgABA..."
    Output: bytes của ảnh (b'\xff\xd8\xff\xe0...')
    
    Raises:
        ValueError: Nếu không có dữ liệu hoặc base64 không hợp lệ
    """
    # Lấy phần base64 sạch (không có prefix "data:image/...;base64,")
    raw = _strip_data_url_prefix(face_image_base64)
    if not raw:
        raise ValueError("Không có dữ liệu ảnh khuôn mặt.")

    try:
        # Giải mã base64 thành bytes
        return base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Ảnh khuôn mặt không đúng định dạng base64.")


def extract_face_embedding_from_base64(
    face_image_base64: str,
    model_name: str | None = None,
    detector_backend: str | None = None,
) -> str:
    """
    Trích xuất đặc trưng khuôn mặt (face embedding) từ ảnh base64.
    
    Hàm này sử dụng DeepFace để phát hiện và trích xuất vector đặc trưng
    từ ảnh khuôn mặt. Vector này dùng để so sánh khuôn mặt.
    
    Args:
        face_image_base64: Ảnh base64 của khuôn mặt
        model_name: Tên model (mặc định: Facenet512)
        detector_backend: Backend phát hiện (mặc định: opencv)
    
    Returns:
        Chuỗi JSON chứa vector 512 chiều
        Ví dụ: "[0.123, -0.456, 0.789, ..., 0.234]"
    
    Raises:
        ValueError: Nếu ảnh không hợp lệ hoặc không phát hiện được khuôn mặt
    """
    # Bước 1: Giải mã ảnh base64 thành bytes
    image_bytes = decode_base64_image(face_image_base64)

    # Bước 2: Lấy cấu hình model từ Flask config (hoặc dùng giá trị mặc định)
    model_name = model_name or current_app.config.get("FACE_MODEL_NAME", DEFAULT_FACE_MODEL)
    detector_backend = detector_backend or current_app.config.get(
        "FACE_DETECTOR_BACKEND",
        DEFAULT_DETECTOR_BACKEND,
    )

    temp_path = None
    try:
        # Bước 3: Tạo file tạm lưu bytes ảnh (DeepFace yêu cầu đường dẫn file)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(image_bytes)
            temp_path = tmp.name

        # Bước 4: Gọi DeepFace để trích xuất embedding (vector đặc trưng)
        result = DeepFace.represent(
            img_path=temp_path,
            model_name=model_name,
            detector_backend=detector_backend,
            enforce_detection=True,  # Bắt buộc phải phát hiện được khuôn mặt
        )

        # Kiểm tra kết quả
        if not result:
            raise ValueError("Không phát hiện được khuôn mặt trong ảnh.")

        # Lấy khuôn mặt đầu tiên (nếu có nhiều khuôn mặt)
        first_face = result[0] if isinstance(result, list) else result
        # Lấy vector embedding từ kết quả
        embedding = first_face.get("embedding") if isinstance(first_face, dict) else None

        if not embedding:
            raise ValueError("Không trích xuất được đặc trưng khuôn mặt.")

        # Bước 5: Chuyển vector thành chuỗi JSON để lưu vào database
        return json.dumps([float(x) for x in embedding], ensure_ascii=False)

    except ValueError:
        # Re-raise lỗi validation
        raise
    except Exception as exc:
        # Log lỗi và raise lỗi user-friendly
        current_app.logger.exception("DeepFace represent failed")
        raise ValueError(f"Không thể xử lý ảnh khuôn mặt: {exc}")
    finally:
        # Bước 6: Dọn dẹp - xóa file tạm
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def load_embedding_vector(raw_embedding: str | None):
    """
    Chuyển đổi vector lưu trong database (dạng JSON chuỗi) 
    thành numpy array để tính toán.
    
    Input: "[0.123, -0.456, 0.789, ...]"
    Output: np.array([0.123, -0.456, 0.789, ...], dtype=float32)
    
    Args:
        raw_embedding: Chuỗi JSON chứa vector embedding
    
    Returns:
        numpy array float32 hoặc None nếu dữ liệu không hợp lệ
    """
    if not raw_embedding:
        return None

    try:
        # Parse JSON string thành list
        parsed = json.loads(raw_embedding)
        # Kiểm tra là list không rỗng
        if not isinstance(parsed, list) or not parsed:
            return None
        # Convert thành numpy array kiểu float32 để tính toán nhanh hơn
        return np.array(parsed, dtype=np.float32)
    except Exception:
        # Nếu parse lỗi (JSON không hợp lệ), trả về None
        return None


def cosine_distance(vec1, vec2) -> float:
    """
    Tính khoảng cách cosine giữa 2 vector khuôn mặt.
    
    Công thức: distance = 1 - (vec1 · vec2) / (||vec1|| * ||vec2||)
    - Kết quả 0.0 = hai khuôn mặt giống nhau
    - Kết quả 1.0 = hai khuôn mặt hoàn toàn khác
    
    Args:
        vec1: Vector embedding khuôn mặt 1
        vec2: Vector embedding khuôn mặt 2
    
    Returns:
        float: Khoảng cách (0.0 - 1.0)
    """
    # Nếu bất kỳ vector nào None, coi là khác hoàn toàn
    if vec1 is None or vec2 is None:
        return 1.0

    # Tính độ lớn (norm) của từng vector
    denom = float(np.linalg.norm(vec1) * np.linalg.norm(vec2))
    
    # Tránh chia cho 0
    if denom == 0:
        return 1.0

    # Tính similarity bằng tích vô hướng chia cho tích độ lớn
    similarity = float(np.dot(vec1, vec2) / denom)
    
    # Giới hạn similarity trong [-1, 1] (tránh lỗi làm tròn)
    similarity = max(-1.0, min(1.0, similarity))
    
    # Distance = 1 - similarity
    return 1.0 - similarity


def confidence_from_distance(distance: float) -> float:
    """
    Chuyển đổi khoảng cách cosine thành độ tin cậy phần trăm.
    
    - distance 0.2 → confidence 80% (giống nhau 80%)
    - distance 0.8 → confidence 20% (giống nhau 20%)
    
    Công thức: confidence = (1.0 - distance) * 100
    
    Args:
        distance: Khoảng cách cosine (0.0 - 1.0)
    
    Returns:
        float: Độ tin cậy (0.0 - 100.0) làm tròn 2 chữ số thập phân
    """
    # Chuyển đổi distance thành percentage
    score = (1.0 - float(distance)) * 100.0
    
    # Giới hạn trong [0, 100] và làm tròn 2 chữ số thập phân
    return round(max(0.0, min(100.0, score)), 2)