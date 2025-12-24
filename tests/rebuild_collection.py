"""
重建 Qdrant Collection（修正維度）
執行: python tests/rebuild_collection.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
from config import QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION, VECTOR_DIMENSION

print("=" * 50)
print("   重建 Qdrant Collection")
print("=" * 50)

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# 刪除舊的 collection
print(f"\n刪除舊 collection: {QDRANT_COLLECTION}")
try:
    client.delete_collection(QDRANT_COLLECTION)
    print("  ✓ 已刪除")
except Exception as e:
    print(f"  ⚠ {e}")

# 創建新的 collection
print(f"\n創建新 collection (維度={VECTOR_DIMENSION})...")
client.create_collection(
    collection_name=QDRANT_COLLECTION,
    vectors_config=VectorParams(
        size=VECTOR_DIMENSION,
        distance=Distance.COSINE
    )
)
print("  ✓ 已創建")

# 確認
info = client.get_collection(QDRANT_COLLECTION)
print(f"\nCollection 資訊:")
print(f"  status: {info.status}")
print(f"  points_count: {info.points_count}")
print(f"  vector_size: {info.config.params.vectors.size}")

print("\n" + "=" * 50)
print("   完成！現在可以重新執行測試")
print("=" * 50)
