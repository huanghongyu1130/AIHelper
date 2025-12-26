"""
配置文件
集中管理 API Keys 和服務連線設定
"""
import os
from dotenv import load_dotenv

# 載入 .env 文件
load_dotenv()

# ===== Embedding 服務配置 =====
# 選擇使用的 Embedding 服務: "gemini" 或 "voyage"
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "gemini")

# ===== Google Gemini 配置 =====
# 從環境變數讀取，避免金鑰外洩
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004")

# ===== Voyage AI 配置（備用）=====
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")
VOYAGE_MODEL = os.getenv("VOYAGE_MODEL", "voyage-large-2")

# ===== Qdrant 配置 =====
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "knowledge_vectors")

# ===== 向量配置 =====
# Gemini text-embedding-004: 768 維度
# Voyage large-2: 1536 維度
VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "768"))
SEARCH_TOP_K = int(os.getenv("SEARCH_TOP_K", "5"))

# ===== 文件路徑 =====
UPLOADS_DIR = os.getenv("UPLOADS_DIR", "uploads")

# ===== 檢查必要的 API 金鑰 =====
if not GEMINI_API_KEY and EMBEDDING_PROVIDER == "gemini":
    print("⚠️ 警告: GEMINI_API_KEY 未設定！請在 .env 文件中設定。")
if not VOYAGE_API_KEY and EMBEDDING_PROVIDER == "voyage":
    print("⚠️ 警告: VOYAGE_API_KEY 未設定！請在 .env 文件中設定。")
