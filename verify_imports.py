import sys
import importlib

def check_import(module_name):
    try:
        importlib.import_module(module_name)
        print(f"[OK] {module_name}")
        return True
    except ImportError as e:
        print(f"[FAIL] {module_name}: {e}")
        return False

modules_to_check = [
    "PyQt6",
    "speech_recognition",
    "pyaudio",
    "pyautogui",
    "pandas",
    "requests",
    "openpyxl",
    "sympy",
    "litellm",
    "mcp",
    "fastmcp",
    "pydantic",
    "duckduckgo_search", # package name is duckduckgo-search but module is duckduckgo_search usually, or ddgs
    "bs4",
    "playwright",
    "trafilatura",
    "readabilipy",
    "markdownify",
    "google.genai",
    # Critical check for agent.py dependencies
    "google.adk" 
]

print(f"Python executable: {sys.executable}")
print("Checking imports...")

failed = []
for module in modules_to_check:
    if module == "duckduckgo_search":
        # Special handling for ddgs
        try:
            import ddgs
            print(f"[OK] ddgs (duckduckgo_search)")
        except ImportError:
            if not check_import("duckduckgo_search"):
                failed.append(module)
    else:
        if not check_import(module):
            failed.append(module)

if failed:
    print("\nSome modules failed to import:")
    for m in failed:
        print(f"- {m}")
    sys.exit(1)
else:
    print("\nAll checks passed!")
    sys.exit(0)