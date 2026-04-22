import os
DEEPFACE_CACHE_DIR = r"D:\deepface_cache"
os.makedirs(DEEPFACE_CACHE_DIR, exist_ok=True)
os.environ["DEEPFACE_HOME"] = DEEPFACE_CACHE_DIR

from app import create_app
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)