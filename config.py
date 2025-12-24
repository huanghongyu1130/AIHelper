"""
配置文件
集中管理 API Keys 和服務連線設定
"""

# ===== Embedding 服務配置 =====
# 選擇使用的 Embedding 服務: "gemini" 或 "voyage"
EMBEDDING_PROVIDER = "gemini"

# ===== Google Gemini 配置 =====
GEMINI_API_KEY = "AIzaSyCHOU3QLLC1SyfqF_xZ3iNvhvvhDs-IIUc"
GEMINI_EMBEDDING_MODEL = "text-embedding-004"  # 或 "embedding-001"

# ===== Voyage AI 配置（備用）=====
VOYAGE_API_KEY = "pa-QAbRHGsYoqhGlJJ2L6x3yXEk9Gro44BSIS2u75pLS44"
VOYAGE_MODEL = "voyage-large-2"

# ===== Qdrant 配置 =====
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
QDRANT_COLLECTION = "knowledge_vectors"

# ===== 向量配置 =====
# Gemini text-embedding-004: 768 維度
# Voyage large-2: 1536 維度
VECTOR_DIMENSION = 768  # Gemini embedding 維度
SEARCH_TOP_K = 5  # 搜尋返回數量

# ===== 文件路徑 =====
UPLOADS_DIR = "uploads"
