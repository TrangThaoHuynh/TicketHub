"""
Standalone Face Recognition Service
Chạy độc lập trên port 5001
"""
import os
import base64
import json
import tempfile
import logging
from pathlib import Path

# ============ SETUP DEEPFACE CACHE - PHẢI TRƯỚC KHI IMPORT DEEPFACE ============
DEEPFACE_CACHE_DIR = os.environ.get("DEEPFACE_HOME", r"D:\deepface_cache")
os.makedirs(DEEPFACE_CACHE_DIR, exist_ok=True)
os.environ["DEEPFACE_HOME"] = DEEPFACE_CACHE_DIR
print(f"📁 DeepFace cache: {DEEPFACE_CACHE_DIR}")

# ============ IMPORT FLASK & DEEPFACE ============
from flask import Flask, jsonify, request
from deepface import DeepFace

# ============ CONFIG ============
DEFAULT_FACE_MODEL = "Facenet512"
DEFAULT_DETECTOR_BACKEND = "opencv"
FACE_SERVICE_PORT = int(os.environ.get("FACE_SERVICE_PORT", 5001))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ FLASK APP ============
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max


# ============ HELPER FUNCTIONS ============
def _strip_data_url_prefix(value: str) -> str:
    """Lấy phần base64 từ data URL"""
    text = str(value or "").strip()
    if "," in text and text.lower().startswith("data:image"):
        return text.split(",", 1)[1]
    return text


def decode_base64_image(face_image_base64: str) -> bytes:
    """Giải mã base64 thành bytes"""
    raw = _strip_data_url_prefix(face_image_base64)
    if not raw:
        raise ValueError("Không có dữ liệu ảnh khuôn mặt.")
    
    try:
        return base64.b64decode(raw, validate=True)
    except Exception:
        raise ValueError("Ảnh khuôn mặt không đúng định dạng base64.")


# ============ API ENDPOINTS ============
@app.route('/', methods=['GET']) 
def index():
    """Root endpoint - API info"""
    return jsonify({
        "service": "Face Recognition Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "GET /health",
            "extract_embedding": "POST /extract-embedding"
        }
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "service": "face-recognition",
        "model": DEFAULT_FACE_MODEL,
        "backend": DEFAULT_DETECTOR_BACKEND
    }), 200


@app.route('/extract-embedding', methods=['POST'])
def extract_embedding():
    """
    Trích xuất embedding từ ảnh base64
    
    Request JSON:
    {
        "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABA..."
    }
    
    Response JSON:
    {
        "success": true,
        "embedding": "[0.123, -0.456, ...]"
    }
    """
    try:
        # Validate request
        data = request.get_json(force=True)
        if not data or 'image' not in data:
            return jsonify({
                "success": False,
                "error": "Missing image field in request body"
            }), 400

        image_base64 = data['image']
        if not image_base64 or not isinstance(image_base64, str):
            return jsonify({
                "success": False,
                "error": "image must be a non-empty string"
            }), 400

        # Decode image
        try:
            image_bytes = decode_base64_image(image_base64)
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 400

        # Save to temp file
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(image_bytes)
                temp_path = tmp.name

            logger.info(f"Processing image: {temp_path}")

            # Extract embedding using DeepFace
            result = DeepFace.represent(
                img_path=temp_path,
                model_name=DEFAULT_FACE_MODEL,
                detector_backend=DEFAULT_DETECTOR_BACKEND,
                enforce_detection=True,
            )

            if not result:
                return jsonify({
                    "success": False,
                    "error": "Không phát hiện được khuôn mặt trong ảnh"
                }), 400

            # Extract embedding from result
            first_face = result[0] if isinstance(result, list) else result
            embedding = first_face.get('embedding') if isinstance(first_face, dict) else None

            if not embedding:
                return jsonify({
                    "success": False,
                    "error": "Không trích xuất được đặc trưng khuôn mặt"
                }), 400

            # Convert to JSON string
            embedding_json = json.dumps([float(x) for x in embedding], ensure_ascii=False)

            logger.info(f" Embedding extracted successfully")
            return jsonify({
                "success": True,
                "embedding": embedding_json
            }), 200

        finally:
            # Cleanup temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    logger.warning(f"Failed to delete temp file: {temp_path}")

    except Exception as e:
        logger.exception(f"Error processing request: {e}")
        return jsonify({
            "success": False,
            "error": f"Internal server error: {str(e)}"
        }), 500


# ============ ERROR HANDLERS ============
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "success": False,
        "error": "Request payload too large (max 16MB)"
    }), 413


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": f"Endpoint not found: {request.path}"
    }), 404


# ============ MAIN ============
if __name__ == "__main__":
    print("\n" + "="*60)
    print("FACE RECOGNITION SERVICE")
    print("="*60)
    print(f"Port: {FACE_SERVICE_PORT}")
    print(f"Model: {DEFAULT_FACE_MODEL}")
    print(f"Detector: {DEFAULT_DETECTOR_BACKEND}")
    print("\nEndpoints:")
    print(f"   GET  http://0.0.0.0:{FACE_SERVICE_PORT}/health")
    print(f"   POST http://0.0.0.0:{FACE_SERVICE_PORT}/extract-embedding")
    print("\n Loading DeepFace models (first time may take 1-2 minutes)...")
    print("="*60 + "\n")
    
    # Pre-warm models
    try:
        from deepface import DeepFace as DF
        logger.info("Warming up DeepFace models...")
        # This will download models if needed
        DF.build_model(DEFAULT_FACE_MODEL)
        logger.info(" DeepFace models ready!")
    except Exception as e:
        logger.warning(f"Warning during model warmup: {e}")
    
    app.run(host='0.0.0.0', port=FACE_SERVICE_PORT, debug=False, threaded=True)