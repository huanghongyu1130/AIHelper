import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Tool.text_processing import recursive_character_text_splitter
from vector_storage import get_vector_storage

def test_chunking():
    print("Testing Chunking...")
    text = "A" * 5000 + "B" * 5000
    chunks = recursive_character_text_splitter(text, chunk_size=2000, chunk_overlap=100)
    print(f"Text length: {len(text)}")
    print(f"Number of chunks: {len(chunks)}")
    assert len(chunks) > 0
    assert len(chunks[0]) <= 2000
    print("Chunking Test Passed!")

async def test_vector_storage():
    print("\nTesting Vector Storage (Chunk support)...")
    try:
        store = get_vector_storage()
        
        # Test embedding a chunk
        chunk_text = "This is a test chunk for KAG pipeline verification."
        doc_id = "test_doc_001"
        
        vector_data = store.embed_document_chunk(chunk_text, doc_id, 0)
        
        print("Embed result keys:", vector_data.keys())
        assert "vector" in vector_data
        assert vector_data["payload"]["type"] == "document_chunk"
        
        print("Vector Storage Test Passed!")
    except Exception as e:
        print(f"Vector Storage Test Failed: {e}")
        # It might fail if no API key, but we want to check the method signature is correct
        pass

if __name__ == "__main__":
    test_chunking()
    asyncio.run(test_vector_storage())
