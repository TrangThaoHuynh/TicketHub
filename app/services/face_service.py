"""
Face Recognition Client Service
Gọi Face Recognition Service qua HTTP API
"""
import requests
import json
import os
from flask import current_app

# ============ CONFIG ============
FACE_SERVICE_URL = os.environ.get(
    "FACE_SERVICE_URL",
    "http://localhost:5001"  # Default cho development
)

# Request timeout (seconds)
FACE_SERVICE_TIMEOUT = int(os.environ.get("FACE_SERVICE_TIMEOUT", "30"))


# ============ HELPER FUNCTIONS ============
def load_embedding_vector(raw_embedding: str | None):
    """
    Chuyển đổi vector lưu trong database (dạng JSON chuỗi) 
    thành numpy array để tính toán.
    
    Input: "[0.123, -0.456, 0.789, ...]"
    Output: np.array([0.123, -0.456, 0.789, ...], dtype=float32)
    """
    import numpy as np
    
    if not raw_embedding:
        return None

    try:
        raw_embedding = str(raw_embedding).strip()  # Đảm bảo là string
        if not raw_embedding or raw_embedding == "None":
            return None
            
        parsed = json.loads(raw_embedding)
        
        # Kiểm tra format
        if not isinstance(parsed, list):
            return None
            
        if not parsed or len(parsed) == 0:
            return None
        
        # ✅ Kiểm tra vector có 512 chiều không
        if len(parsed) != 512:
            import sys
            print(f"⚠️ WARNING: Embedding size mismatch! Expected 512, got {len(parsed)}", file=sys.stderr)
            return None
            
        return np.array(parsed, dtype=np.float32)
    except json.JSONDecodeError:
        return None
    except Exception as e:
        print(f"Error loading embedding: {e}")
        return None

def cosine_distance(vec1, vec2) -> float:
    """Tính khoảng cách cosine giữa 2 vector khuôn mặt"""
    import numpy as np
    
    if vec1 is None or vec2 is None:
        return 1.0

    # ✅ Kiểm tra kích thước vector
    if len(vec1) != len(vec2):
        print(f"⚠️ WARNING: Vector size mismatch! {len(vec1)} vs {len(vec2)}")
        return 1.0
    
    if len(vec1) != 512:
        print(f"⚠️ WARNING: Unexpected vector size: {len(vec1)} (expected 512)")
        return 1.0

    denom = float(np.linalg.norm(vec1) * np.linalg.norm(vec2))
    
    if denom == 0:
        return 1.0

    similarity = float(np.dot(vec1, vec2) / denom)
    similarity = max(-1.0, min(1.0, similarity))
    
    return 1.0 - similarity


def confidence_from_distance(distance: float) -> float:
    """Chuyển đổi khoảng cách cosine thành độ tin cậy phần trăm"""
    score = (1.0 - float(distance)) * 100.0
    return round(max(0.0, min(100.0, score)), 2)


# ============ MAIN FUNCTION ============
def extract_face_embedding_from_base64(
    face_image_base64: str,
    
) -> str:
    """
    Trích xuất đặc trưng khuôn mặt (face embedding) từ ảnh base64.
    
    Gọi Face Recognition Service thay vì xử lý trực tiếp.
    
    Args:
        face_image_base64: Ảnh base64 của khuôn mặt
        
    
    Returns:
        Chuỗi JSON chứa vector 512 chiều
        Ví dụ: "[0.123, -0.456, 0.789, ..., 0.234]"
    
    Raises:
        ValueError: Nếu ảnh không hợp lệ hoặc service không khả dụng
    """
    try:
        # Gọi Face Recognition Service
        response = requests.post(
            f"{FACE_SERVICE_URL}/extract-embedding",
            json={"image": face_image_base64},
            timeout=FACE_SERVICE_TIMEOUT
        )

        # Parse response
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                embedding = result.get('embedding')
                current_app.logger.info(" Face embedding extracted from service")
                return embedding
            else:
                error_msg = result.get('error', 'Unknown error')
                current_app.logger.error(f"Service error: {error_msg}")
                raise ValueError(f"Face service error: {error_msg}")
        
        elif response.status_code == 400:
            result = response.json()
            error_msg = result.get('error', 'Bad request')
            current_app.logger.warning(f"Bad request to face service: {error_msg}")
            raise ValueError(error_msg)
        
        elif response.status_code == 413:
            current_app.logger.error("Image too large for face service")
            raise ValueError("Ảnh quá lớn (tối đa 16MB)")
        
        else:
            current_app.logger.error(f"Face service error {response.status_code}")
            raise ValueError(f"Face service unavailable (HTTP {response.status_code})")

    except requests.exceptions.ConnectionError:
        current_app.logger.error(f" Cannot connect to Face Service at {FACE_SERVICE_URL}")
        raise ValueError(
            "Dịch vụ nhận diện khuôn mặt không sẵn sàng. "
            "Vui lòng kiểm tra cấu hình FACE_SERVICE_URL"
        )
    
    except requests.exceptions.Timeout:
        current_app.logger.error("⏱️ Face Recognition Service timeout")
        raise ValueError(
            "Hết thời gian chờ dịch vụ nhận diện khuôn mặt. "
            f"Thử lại hoặc tăng FACE_SERVICE_TIMEOUT"
        )
    
    except requests.exceptions.RequestException as e:
        current_app.logger.exception(f"Request error to face service: {e}")
        raise ValueError(f"Lỗi kết nối dịch vụ: {str(e)}")
    
    except Exception as e:
        current_app.logger.exception(f"Unexpected error: {e}")
        raise ValueError(f"Lỗi xử lý khuôn mặt: {str(e)}")