try:
    from langgraph.prebuilt import create_react_agent
    print("SUCCESS: from langgraph.prebuilt import create_react_agent")
except ImportError:
    print("FAIL: from langgraph.prebuilt import create_react_agent")

try:
    from langchain_openai import ChatOpenAI
    print("SUCCESS: from langchain_openai import ChatOpenAI")
except ImportError:
    print("FAIL: from langchain_openai import ChatOpenAI")

import langchain
print(f"LangChain version: {langchain.__version__}")