import langchain
import langchain.agents
print(f"LangChain version: {langchain.__version__}")
try:
    from langchain.agents import AgentExecutor
    print("AgentExecutor found in langchain.agents")
except ImportError:
    print("AgentExecutor NOT found in langchain.agents")

try:
    from langchain.agents import create_openai_tools_agent
    print("create_openai_tools_agent found in langchain.agents")
except ImportError:
    print("create_openai_tools_agent NOT found in langchain.agents")
    
# Try to find it
import inspect
print("langchain.agents members:")
for name, obj in inspect.getmembers(langchain.agents):
    if "Executor" in name or "agent" in name:
        print(f"- {name}")