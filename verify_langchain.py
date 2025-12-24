import sys
import importlib

modules = [
    "langchain",
    "langchain_openai",
    "langchain_core",
    "mcp"
]

failed = []
for m in modules:
    try:
        importlib.import_module(m)
        print(f"[OK] {m}")
    except ImportError as e:
        print(f"[FAIL] {m}: {e}")
        failed.append(m)

if failed:
    sys.exit(1)