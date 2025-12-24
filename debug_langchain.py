import langchain
import langchain.agents
import os

print(f"LangChain version: {langchain.__version__}")
print(f"LangChain path: {langchain.__path__}")
print(f"LangChain agents path: {langchain.agents.__path__}")
print(f"LangChain agents file: {langchain.agents.__file__}")

try:
    from langchain.agents import AgentExecutor
    print("SUCCESS: from langchain.agents import AgentExecutor")
except ImportError as e:
    print(f"FAIL: {e}")

try:
    from langchain.agents.agent_executor import AgentExecutor
    print("SUCCESS: from langchain.agents.agent_executor import AgentExecutor")
except ImportError as e:
    print(f"FAIL: {e}")

try:
    from langchain.agents import create_openai_tools_agent
    print("SUCCESS: from langchain.agents import create_openai_tools_agent")
except ImportError as e:
    print(f"FAIL: {e}")

# List files in agents directory
agents_dir = langchain.agents.__path__[0]
print(f"Files in {agents_dir}:")
for f in os.listdir(agents_dir):
    print(f" - {f}")