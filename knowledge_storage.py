"""
Knowledge Storage Module
使用 SQLite 儲存知識圖譜數據，讓 AI 可以查詢已導入的知識

使用方式:
    from knowledge_storage import KnowledgeStorage
    
    storage = KnowledgeStorage()
    storage.add_document("doc_id", "filename.pdf", "text content")
    storage.add_entity("doc_id", "entity_name", "concept", "description")
    storage.add_relation("doc_id", "entity1", "entity2", "relation")
    
    # AI 查詢知識
    results = storage.search_knowledge("關鍵字")
"""

import sqlite3
import json
import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any


class KnowledgeStorage:
    """知識圖譜 SQLite 存儲"""
    
    def __init__(self, db_path: str = None):
        """
        初始化知識存儲
        
        Args:
            db_path: 資料庫路徑，預設為 knowledge.db
        """
        if db_path is None:
            db_path = Path(__file__).parent / "knowledge.db"
        
        self.db_path = str(db_path)
        self._init_database()
    
    def _init_database(self):
        """初始化資料庫表結構"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 文檔表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                text_content TEXT,
                text_length INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 實體表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id)
            )
        ''')
        
        # 關係表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                from_entity TEXT NOT NULL,
                to_entity TEXT NOT NULL,
                relation_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id)
            )
        ''')
        
        # 建立索引提升查詢效率
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entities_name ON entities (name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entities_doc ON entities (document_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_relations_doc ON relations (document_id)')
        
        conn.commit()
        conn.close()
        print(f"[Knowledge] 知識庫已初始化: {self.db_path}")
    
    def add_document(self, doc_id: str, filename: str, text_content: str = "") -> bool:
        """
        添加文檔
        
        Args:
            doc_id: 文檔 ID
            filename: 文件名
            text_content: 文本內容
            
        Returns:
            是否成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO documents (id, filename, text_content, text_length)
                VALUES (?, ?, ?, ?)
            ''', (doc_id, filename, text_content, len(text_content)))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"添加文檔失敗: {e}")
            return False
    
    def add_entity(self, doc_id: str, name: str, entity_type: str, description: str = "") -> int:
        """
        添加實體
        
        Args:
            doc_id: 所屬文檔 ID
            name: 實體名稱
            entity_type: 實體類型 (concept/entity/tech/model/person/org)
            description: 描述
            
        Returns:
            實體 ID
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO entities (document_id, name, type, description)
                VALUES (?, ?, ?, ?)
            ''', (doc_id, name, entity_type, description))
            
            entity_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return entity_id
        except Exception as e:
            print(f"添加實體失敗: {e}")
            return -1
    
    def add_relation(self, doc_id: str, from_entity: str, to_entity: str, relation_type: str) -> int:
        """
        添加關係
        
        Args:
            doc_id: 所屬文檔 ID
            from_entity: 起始實體名稱
            to_entity: 目標實體名稱
            relation_type: 關係類型
            
        Returns:
            關係 ID
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO relations (document_id, from_entity, to_entity, relation_type)
                VALUES (?, ?, ?, ?)
            ''', (doc_id, from_entity, to_entity, relation_type))
            
            relation_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return relation_id
        except Exception as e:
            print(f"添加關係失敗: {e}")
            return -1
    
    def save_knowledge(self, doc_id: str, filename: str, text: str,
                       entities: List[Dict], relations: List[Dict]) -> bool:
        """
        一次性儲存完整知識
        
        Args:
            doc_id: 文檔 ID
            filename: 文件名
            text: 文本內容
            entities: 實體列表
            relations: 關係列表
            
        Returns:
            是否成功
        """
        try:
            # 儲存文檔
            self.add_document(doc_id, filename, text)
            
            # 儲存實體
            for entity in entities:
                self.add_entity(
                    doc_id,
                    entity.get('name', ''),
                    entity.get('type', 'entity'),
                    entity.get('description', '')
                )
            
            # 儲存關係
            for rel in relations:
                self.add_relation(
                    doc_id,
                    rel.get('from', ''),
                    rel.get('to', ''),
                    rel.get('relation', '')
                )
            
            print(f"[Knowledge] 已儲存知識: {filename} ({len(entities)} 實體, {len(relations)} 關係)")
            return True
        except Exception as e:
            print(f"儲存知識失敗: {e}")
            return False
    
    def search_knowledge(self, keyword: str) -> Dict[str, Any]:
        """
        搜尋知識庫
        
        Args:
            keyword: 搜尋關鍵字
            
        Returns:
            搜尋結果
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 搜尋實體
        cursor.execute('''
            SELECT e.name, e.type, e.description, d.filename
            FROM entities e
            JOIN documents d ON e.document_id = d.id
            WHERE e.name LIKE ? OR e.description LIKE ?
        ''', (f'%{keyword}%', f'%{keyword}%'))
        
        entities = [
            {"name": row[0], "type": row[1], "description": row[2], "source": row[3]}
            for row in cursor.fetchall()
        ]
        
        # 搜尋關係
        cursor.execute('''
            SELECT r.from_entity, r.to_entity, r.relation_type, d.filename
            FROM relations r
            JOIN documents d ON r.document_id = d.id
            WHERE r.from_entity LIKE ? OR r.to_entity LIKE ? OR r.relation_type LIKE ?
        ''', (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'))
        
        relations = [
            {"from": row[0], "to": row[1], "relation": row[2], "source": row[3]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        
        return {
            "keyword": keyword,
            "entities": entities,
            "relations": relations,
            "total": len(entities) + len(relations)
        }
    
    def get_all_knowledge(self) -> Dict[str, Any]:
        """獲取所有知識"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 獲取所有文檔
        cursor.execute('SELECT id, filename, text_length, created_at FROM documents')
        documents = [
            {"id": row[0], "filename": row[1], "text_length": row[2], "created_at": row[3]}
            for row in cursor.fetchall()
        ]
        
        # 獲取所有實體
        cursor.execute('SELECT document_id, name, type, description FROM entities')
        entities = [
            {"document_id": row[0], "name": row[1], "type": row[2], "description": row[3]}
            for row in cursor.fetchall()
        ]
        
        # 獲取所有關係
        cursor.execute('SELECT document_id, from_entity, to_entity, relation_type FROM relations')
        relations = [
            {"document_id": row[0], "from": row[1], "to": row[2], "relation": row[3]}
            for row in cursor.fetchall()
        ]
        
        conn.close()
        
        return {
            "documents": documents,
            "entities": entities,
            "relations": relations
        }
    
    def get_knowledge_for_ai(self) -> str:
        """
        獲取 AI 可讀的知識摘要
        
        Returns:
            格式化的知識文本，可注入到 AI prompt 中
        """
        knowledge = self.get_all_knowledge()
        
        if not knowledge['entities']:
            return "目前知識庫為空。"
        
        lines = ["## 知識庫內容\n"]
        
        # 按文檔分組
        doc_entities = {}
        for entity in knowledge['entities']:
            doc_id = entity['document_id']
            if doc_id not in doc_entities:
                doc_entities[doc_id] = []
            doc_entities[doc_id].append(entity)
        
        for doc in knowledge['documents']:
            lines.append(f"### 來源: {doc['filename']}")
            
            # 列出該文檔的實體
            if doc['id'] in doc_entities:
                for entity in doc_entities[doc['id']]:
                    lines.append(f"- **{entity['name']}** ({entity['type']}): {entity['description']}")
            
            lines.append("")
        
        # 列出關係
        if knowledge['relations']:
            lines.append("### 知識關係")
            for rel in knowledge['relations']:
                lines.append(f"- {rel['from']} → {rel['to']} ({rel['relation']})")
        
        return "\n".join(lines)
    
    def delete_document(self, doc_id: str) -> bool:
        """刪除文檔及相關知識"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM relations WHERE document_id = ?', (doc_id,))
            cursor.execute('DELETE FROM entities WHERE document_id = ?', (doc_id,))
            cursor.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"刪除文檔失敗: {e}")
            return False


# 全局單例
_storage_instance = None

def get_knowledge_storage() -> KnowledgeStorage:
    """獲取知識存儲單例"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = KnowledgeStorage()
    return _storage_instance
