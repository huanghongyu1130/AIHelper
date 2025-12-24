import pkgutil
import langchain
import langchain_community
import langchain_openai
import langchain_core

def find_class(package, class_name):
    print(f"Searching in {package.__name__}...")
    for importer, modname, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        try:
            # Skip some problematic modules
            if "notebook" in modname or "cli" in modname:
                continue
            
            module = __import__(modname, fromlist="dummy")
            if hasattr(module, class_name):
                print(f"FOUND {class_name} in {modname}")
                return
        except Exception as e:
            # print(f"Error importing {modname}: {e}")
            pass

print("Searching for AgentExecutor...")
find_class(langchain, "AgentExecutor")

print("\nSearching for create_openai_tools_agent...")
find_class(langchain, "create_openai_tools_agent")