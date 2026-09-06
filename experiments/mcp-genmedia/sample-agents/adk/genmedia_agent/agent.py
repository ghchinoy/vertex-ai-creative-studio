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

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StdioConnectionParams,
    StdioServerParameters,
)

load_dotenv()

project_id = os.getenv("GOOGLE_CLOUD_PROJECT")

# Model for the agent. gemini-3.8-flash runs in the GLOBAL region, so set
# GOOGLE_CLOUD_LOCATION="global" in your .env (see README).
MODEL = "gemini-3.8-flash"

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

nanobanana = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="mcp-nanobanana-go",
            env=dict(os.environ, PROJECT_ID=project_id),
        ),
        timeout=60,
    ),
    tool_filter=["nanobanana_image_generation"],
)

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
    model=MODEL,
    name='genmedia_agent',
        instruction="""You're a creative assistant that can help users with creating audio, images, and video via your generative media tools. You also have the ability to composit these using your available tools.
        Feel free to be helpful in your suggestions, based on the information you know or can retrieve from your tools.
        If you're asked to translate into other languages, please do.
        """,
    tools=[
       nanobanana, chirp3, veo, avtool,
    ],
)
