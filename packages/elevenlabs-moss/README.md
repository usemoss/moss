# ElevenLabs Moss Integration

Moss delivers sub-10ms semantic retrieval, giving your ElevenLabs Conversational AI agents instant access to a knowledge base during live voice conversations.

## Installation

```bash
pip install elevenlabs-moss
```

## Prerequisites

- Moss project ID and project key (get them from [Moss Portal](https://portal.usemoss.dev))
- ElevenLabs API key and a Conversational AI agent ID (get them from [ElevenLabs](https://elevenlabs.io))

## Usage

```python
import asyncio
import os

from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import ClientTools, Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from elevenlabs_moss import MossClientTool

async def main():
    # Create and load the Moss tool
    moss_tool = MossClientTool(
        project_id=os.getenv("MOSS_PROJECT_ID"),
        project_key=os.getenv("MOSS_PROJECT_KEY"),
        index_name=os.getenv("MOSS_INDEX_NAME"),
    )
    await moss_tool.load_index()

    # Register with ElevenLabs ClientTools
    client_tools = ClientTools()
    moss_tool.register(client_tools)

    # Start the conversation
    conversation = Conversation(
        client=ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY")),
        agent_id=os.getenv("ELEVENLABS_AGENT_ID"),
        requires_auth=False,
        audio_interface=DefaultAudioInterface(),
        client_tools=client_tools,
    )
    conversation.start_session()
    await asyncio.to_thread(conversation.wait_for_session_end)

asyncio.run(main())
```

For a complete voice agent demo, see [`apps/elevenlabs-moss/`](../../apps/elevenlabs-moss/).

## ElevenLabs Dashboard Setup

Your ElevenLabs agent must have a client tool configured that matches the tool name used in code. In the ElevenLabs dashboard:

1. Open your agent's settings
2. Go to **Tools** and add a new **Client** tool
3. Set **Tool name** to `search_knowledge_base` (case-sensitive)
4. Add a parameter: **name** = `query`, **type** = `string`, **required** = `true`
5. Set the parameter description to: "The user's question to search the knowledge base for"
6. Enable **Wait for response** so the tool output is fed back into the conversation

To use a different tool name, pass `tool_name="your_name"` to `MossClientTool` and update the dashboard to match.

## Configuration Options

### MossClientTool

| Parameter | Default | Description |
|-----------|---------|-------------|
| `project_id` | `MOSS_PROJECT_ID` env var | Moss project ID |
| `project_key` | `MOSS_PROJECT_KEY` env var | Moss project key |
| `index_name` | (required) | Name of the Moss index to query |
| `tool_name` | `search_knowledge_base` | Tool name (must match ElevenLabs dashboard) |
| `top_k` | `5` | Number of results to retrieve per query |
| `alpha` | `0.8` | Blend: 1.0 = semantic only, 0.0 = keyword only |
| `result_prefix` | `Relevant knowledge base results:\n\n` | Prefix for formatted results |

### Methods

| Method | Description |
|--------|-------------|
| `load_index()` | Async. Pre-load the Moss index before starting a conversation |
| `search(query)` | Async. Query Moss and return formatted results as a string |
| `register(client_tools)` | Register the tool with an ElevenLabs `ClientTools` instance |

## License

This integration is provided under the [BSD 2-Clause License](LICENSE).

## Support

- [Moss Docs](https://docs.moss.dev)
- [Moss Discord](https://discord.com/invite/eMXExuafBR)
- [ElevenLabs Docs](https://elevenlabs.io/docs)
