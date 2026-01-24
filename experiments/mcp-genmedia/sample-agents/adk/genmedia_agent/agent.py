# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os

# as of google-adk==1.3.0, StdioConnectionParams
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)

load_dotenv()

project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

# MCP Client (STDIO)
# assumes you've installed the MCP server on your path
veo = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-veo-go",
            env=dict(os.environ, PROJECT_ID=project_id),
        ),
        timeout=60,
    ),
)

chirp3 = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-chirp3-go",
            env=dict(os.environ, PROJECT_ID=project_id),
        ),
        timeout=60,
    ),
)

imagen = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-imagen-go",
            env=dict(os.environ, PROJECT_ID=project_id),
        ),
        timeout=60,
    ),
)

# MCP Client (SSE)
# assumes you've started the MCP server separately
# e.g. mcp-imagen-go --transport sse
# from google.adk.tools.mcp_tool.mcp_toolset import SseServerParams
# remote_imagen, _ = MCPToolset(
#     connection_params=SseServerParams(url="http://localhost:8080/sse"),
# )

avtool = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-avtool-go",
            env=dict(os.environ, PROJECT_ID=project_id),
        ),
        timeout=240,
    ),
)


root_agent = LlmAgent(
    model="gemini-2.0-flash",
    name="genmedia_agent",
    instruction="""You're a creative assistant that can help users with creating audio, images, and video via your generative media tools. You also have the ability to composit these using your available tools.
        Feel free to be helpful in your suggestions, based on the information you know or can retrieve from your tools.
        If you're asked to translate into other languages, please do.
        """,
    tools=[
        imagen,
        chirp3,
        veo,
        avtool,
    ],
)
