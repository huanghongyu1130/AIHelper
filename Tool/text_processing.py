"""
Text Processing Utilities for KAG
提供文本分塊(Chunking)功能
"""

from typing import List

def recursive_character_text_splitter(
    text: str, 
    chunk_size: int = 1000, 
    chunk_overlap: int = 200,
    separators: List[str] = ["\n\n", "\n", " ", ""]
) -> List[str]:
    """
    遞歸字符文本分割器
    模擬 LangChain 的 RecursiveCharacterTextSplitter 行為
    
    Args:
        text: 原始文本
        chunk_size: 每個塊的目標大小
        chunk_overlap: 塊之間的重疊大小
        separators: 分隔符列表，按優先級排序
        
    Returns:
        分割後的文本塊列表
    """
    final_chunks = []
    
    # 基本邊界檢查
    if not text:
        return []
        
    if len(text) <= chunk_size:
        return [text]
        
    # 嘗試使用優先級最高的分隔符切分
    separator = separators[-1]
    for sep in separators:
        if sep in text:
            separator = sep
            break
            
    # 使用選定的分隔符分割
    if separator:
        splits = text.split(separator)
    else:
        # 如果找不到任何分隔符（不常見），則按字符分割
        splits = list(text)
        
    # 重新組合這些分割部分，確保不超過 chunk_size
    current_chunk = []
    current_length = 0
    
    for split in splits:
        # 恢復分隔符（除了最後一個）
        segment = split + (separator if separator else "")
        segment_len = len(segment)
        
        if current_length + segment_len > chunk_size:
            # 當前塊已滿
            if current_chunk:
                doc_chunk = "".join(current_chunk).strip()
                if doc_chunk:
                    final_chunks.append(doc_chunk)
                
                # 處理重疊：保留尾部作為下一個塊的開頭
                # 這裡是一個簡化的重疊邏輯
                overlap_len = 0
                new_start_chunk = []
                for i in range(len(current_chunk)-1, -1, -1):
                    seg = current_chunk[i]
                    if overlap_len + len(seg) < chunk_overlap:
                        new_start_chunk.insert(0, seg)
                        overlap_len += len(seg)
                    else:
                        break
                current_chunk = new_start_chunk
                current_length = overlap_len
            
        current_chunk.append(segment)
        current_length += segment_len
    
    # 處理最後一個塊
    if current_chunk:
        doc_chunk = "".join(current_chunk).strip()
        if doc_chunk:
            final_chunks.append(doc_chunk)
            
    return final_chunks

def simple_chunking(text: str, chunk_size: int = 2000, overlap: int = 200) -> List[str]:
    """
    簡單的固定長度滑動窗口分塊
    （如果遞歸分割過於複雜，可使用此作為備選）
    """
    if not text:
        return []
        
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        
        # 移動窗口
        start = end - overlap
        
        # 防止死循環
        if start >= text_len:
            break
            
    return chunks
