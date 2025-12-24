import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from typing import List, Optional, Dict, Any, Type

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage
from pydantic import create_model, Field, BaseModel

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client

# Load environment variables (simulating agent.py)
os.environ['OPENAI_API_BASE'] = "http://127.0.0.1:9000/v1"
os.environ['OPENAI_API_KEY'] = "123456"

# Configuration file path
MCP_CONFIG_FILE = "mcpserver.json"

async def load_mcp_config():
    if not os.path.exists(MCP_CONFIG_FILE):
        print(f"Config file {MCP_CONFIG_FILE} not found.")
        return {}
    with open(MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

async def convert_mcp_tool_to_langchain_tool(session: ClientSession, tool_info: Any) -> StructuredTool:
    """Converts an MCP tool to a LangChain StructuredTool."""
    
    async def _tool_wrapper(**kwargs):
        # MCP tools expect arguments as a dictionary
        try:
            result = await session.call_tool(tool_info.name, arguments=kwargs)
            # Extract text content from result
            output_text = ""
            if result.content:
                for content in result.content:
                    if content.type == "text":
                        output_text += content.text
                    elif content.type == "image":
                        output_text += "[Image Content]"
                    elif content.type == "resource":
                        output_text += f"[Resource: {content.resource.uri}]"
            
            if result.isError:
                return f"Error: {output_text}"
            return output_text
        except Exception as e:
            return f"Tool execution failed: {str(e)}"

    # Create Pydantic model for args_schema
    fields = {}
    if hasattr(tool_info, "inputSchema") and "properties" in tool_info.inputSchema:
        for prop_name, prop_def in tool_info.inputSchema["properties"].items():
            prop_type = str
            t = prop_def.get("type")
            if t == "integer":
                prop_type = int
            elif t == "number":
                prop_type = float
            elif t == "boolean":
                prop_type = bool
            elif t == "array":
                prop_type = list
            elif t == "object":
                prop_type = dict
            
            description = prop_def.get("description", "")
            # Handle required fields
            if "required" in tool_info.inputSchema and prop_name in tool_info.inputSchema["required"]:
                fields[prop_name] = (prop_type, Field(..., description=description))
            else:
                fields[prop_name] = (Optional[prop_type], Field(None, description=description))
    
    # Ensure valid model name
    model_name = f"{tool_info.name.replace('-', '_').title()}Schema"
    args_schema = create_model(model_name, **fields)

    return StructuredTool.from_function(
        func=None, # We use coroutine
        coroutine=_tool_wrapper,
        name=tool_info.name,
        description=tool_info.description or "",
        args_schema=args_schema
    )

class LangAgent:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.sessions = []
        self.tools = []

    async def initialize(self):
        config = await load_mcp_config()
        servers = config.get("servers", {})

        print(f"Found servers in config: {list(servers.keys())}")

        for server_name, server_config in servers.items():
            try:
                if server_config["type"] == "sse":
                    url = server_config["url"]
                    print(f"Connecting to SSE server: {server_name} at {url}")
                    
                    # Connect to SSE
                    streams = await self.exit_stack.enter_async_context(
                        sse_client(url)
                    )
                    read_stream, write_stream = streams
                    
                    session = await self.exit_stack.enter_async_context(
                        ClientSession(read_stream, write_stream)
                    )
                    
                    await session.initialize()
                    self.sessions.append(session)
                    
                    # List tools
                    mcp_tools_result = await session.list_tools()
                    print(f"  Connected to {server_name}. Found {len(mcp_tools_result.tools)} tools.")
                    for tool_info in mcp_tools_result.tools:
                        lc_tool = await convert_mcp_tool_to_langchain_tool(session, tool_info)
                        self.tools.append(lc_tool)
                        print(f"  - Loaded tool: {tool_info.name}")

                elif server_config["type"] == "stdio":
                    print(f"Connecting to Stdio server: {server_name}")
                    server_params = StdioServerParameters(
                        command=server_config["command"],
                        args=server_config["args"],
                        env=os.environ.copy()
                    )
                    
                    stdio_transport = await self.exit_stack.enter_async_context(
                        stdio_client(server_params)
                    )
                    read_stream, write_stream = stdio_transport
                    
                    session = await self.exit_stack.enter_async_context(
                        ClientSession(read_stream, write_stream)
                    )
                    
                    await session.initialize()
                    self.sessions.append(session)
                    
                    mcp_tools_result = await session.list_tools()
                    print(f"  Connected to {server_name}. Found {len(mcp_tools_result.tools)} tools.")
                    for tool_info in mcp_tools_result.tools:
                        lc_tool = await convert_mcp_tool_to_langchain_tool(session, tool_info)
                        self.tools.append(lc_tool)
                        print(f"  - Loaded tool: {tool_info.name}")

            except Exception as e:
                print(f"Failed to connect to {server_name}: {e}")

    async def run_agent(self, query: str):
        if not self.tools:
            print("No tools available. Agent might not work as expected.")
        
        # Initialize ChatOpenAI with the same model as agent.py
        llm = ChatOpenAI(
            model="openai/gemini-3-flash", 
            temperature=0
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant skilled in using tools. Answer the user's query using the available tools if necessary."),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_openai_tools_agent(llm, self.tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=self.tools, verbose=True)

        print(f"\nProcessing Query: {query}")
        try:
            response = await agent_executor.ainvoke({"input": query})
            print(f"Response: {response['output']}")
        except Exception as e:
            print(f"Error during agent execution: {e}")

    async def cleanup(self):
        await self.exit_stack.aclose()

async def main():
    agent = LangAgent()
    try:
        await agent.initialize()
        
        # Default query if none provided
        query = "台灣的張文 最近是有甚麼事情嗎?，越詳細越好"
        if len(sys.argv) > 1:
            query = sys.argv[1]
            
        await agent.run_agent(query)
        
    finally:
        await agent.cleanup()

if __name__ == "__main__":
    asyncio.run(main())