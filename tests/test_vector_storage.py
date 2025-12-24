"""
向量存儲模組單元測試（Debug 版本）
執行: python tests/test_vector_storage.py
"""

import sys
from pathlib import Path

# 添加父目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("   向量存儲模組單元測試 (Debug Mode)")
print("=" * 60)

# ===== Test 1: 導入模組 =====
print("\n[Test 1] 導入模組...")
try:
    from vector_storage import VectorStorage, get_vector_storage
    print("  ✓ 成功導入 vector_storage")
except Exception as e:
    print(f"  ✗ 導入失敗: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ===== Test 2: 連接 =====
print("\n[Test 2] 測試連接...")
try:
    storage = get_vector_storage()
    stats = storage.get_stats()
    print(f"  Collection 統計: {stats}")
    if "error" in stats:
        print(f"  ✗ 連接有問題: {stats['error']}")
    else:
        print("  ✓ 連接成功")
except Exception as e:
    print(f"  ✗ 連接失敗: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ===== Test 3: 實體 Embedding =====
print("\n[Test 3] 測試實體 embedding...")
try:
    entity = {
        "name": "機器學習",
        "type": "concept",
        "description": "一種人工智慧的分支，讓機器從數據中學習",
        "document_id": "test_doc_001"
    }
    print(f"  輸入實體: {entity}")
    
    result = storage.embed_entity(entity)
    
    print(f"  Entity ID: {result['id']}")
    print(f"  向量維度: {len(result['vector'])}")
    print(f"  向量前5個值: {result['vector'][:5]}")
    print(f"  Payload type: {result['payload']['type']}")
    print("  ✓ 實體 embedding 成功")
    entity_result = result
except Exception as e:
    print(f"  ✗ 實體 embedding 失敗: {e}")
    import traceback
    traceback.print_exc()
    entity_result = None

# ===== Test 4: 關係 Embedding =====
print("\n[Test 4] 測試關係 embedding...")
try:
    relation = {
        "from": "機器學習",
        "to": "深度學習",
        "relation": "包含",
        "document_id": "test_doc_001"
    }
    print(f"  輸入關係: {relation}")
    
    result = storage.embed_relation(relation)
    
    print(f"  Relation ID: {result['id']}")
    print(f"  向量維度: {len(result['vector'])}")
    print(f"  文本: {result['payload']['text']}")
    print("  ✓ 關係 embedding 成功")
    relation_result = result
except Exception as e:
    print(f"  ✗ 關係 embedding 失敗: {e}")
    import traceback
    traceback.print_exc()
    relation_result = None

# ===== Test 5: 存入向量 =====
print("\n[Test 5] 測試存入向量...")
if entity_result and relation_result:
    try:
        vectors = [entity_result, relation_result]
        print(f"  準備存入 {len(vectors)} 個向量")
        
        success = storage.upsert_vectors(vectors)
        
        if success:
            print("  ✓ 存入成功")
            stats = storage.get_stats()
            print(f"  最新統計: {stats}")
        else:
            print("  ✗ 存入失敗")
    except Exception as e:
        print(f"  ✗ 存入錯誤: {e}")
        import traceback
        traceback.print_exc()
else:
    print("  ⚠ 跳過（前面測試失敗）")

# ===== Test 6: 搜尋 =====
print("\n[Test 6] 測試搜尋...")
try:
    query = "什麼是深度學習和機器學習?"
    print(f"  查詢: {query}")
    
    results = storage.search(query, limit=5)
    
    print(f"  找到 {len(results)} 個結果:")
    for i, r in enumerate(results):
        print(f"    {i+1}. [score={r['score']:.4f}] {r['type']}: {r['text']}")
    print("  ✓ 搜尋成功")
except Exception as e:
    print(f"  ✗ 搜尋失敗: {e}")
    import traceback
    traceback.print_exc()

# ===== Test 7: 過濾搜尋 =====
print("\n[Test 7] 測試過濾搜尋...")
try:
    # 只搜尋實體
    entity_results = storage.search("機器學習", limit=5, filter_type="entity")
    print(f"  實體搜尋: {len(entity_results)} 個結果")
    
    # 只搜尋關係
    relation_results = storage.search("包含", limit=5, filter_type="relation")
    print(f"  關係搜尋: {len(relation_results)} 個結果")
    
    print("  ✓ 過濾搜尋成功")
except Exception as e:
    print(f"  ✗ 過濾搜尋失敗: {e}")
    import traceback
    traceback.print_exc()

# ===== Test 8: 刪除 =====
print("\n[Test 8] 測試刪除...")
try:
    success = storage.delete_by_document("test_doc_001")
    print(f"  刪除結果: {success}")
    
    stats = storage.get_stats()
    print(f"  刪除後統計: {stats}")
    print("  ✓ 刪除測試完成")
except Exception as e:
    print(f"  ✗ 刪除失敗: {e}")
    import traceback
    traceback.print_exc()

# ===== 總結 =====
print("\n" + "=" * 60)
print("   測試完成")
print("=" * 60)
