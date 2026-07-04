# Advanced Voice Agent: Harry Potter Impersonator

A real-time voice AI assistant powered by [Moss](https://moss.dev) that speaks as **Harry Potter**. You talk to it and it responds in first person as Harry, answering questions about his background, skills, education, adventures, and contact details by searching a semantic knowledge base built from a PDF (e.g. a Harry Potter-themed resume).

The agent uses Moss to retrieve relevant context before every answer, so it never guesses. It only speaks from what's in the document. Swap the PDF and update the system prompt to impersonate anyone else.

## Setup

**Requirements**: Python, [uv](https://github.com/astral-sh/uv), a running LiveKit server

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure environment

Copy each `.env.example` to `.env` in the same folder:

```bash
cp agent/.env.example agent/.env
cp moss-utils/.env.example moss-utils/.env
```

Fill in your keys in `agent/.env`:

```env
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret

MOSS_PROJECT_ID=your-moss-project-id
MOSS_PROJECT_KEY=your-moss-project-key

DEEPGRAM_API_KEY=your-deepgram-key
GOOGLE_API_KEY=your-google-key
CARTESIA_API_KEY=your-cartesia-key
```

And your Moss credentials in `moss-utils/.env`:

```env
MOSS_PROJECT_ID=your-moss-project-id
MOSS_PROJECT_KEY=your-moss-project-key
```

### 3. Parse your PDF and build the index

Place your PDF in the `moss-utils/` folder, then update `PDF_PATH` and `INDEX_NAME` in [moss-utils/create_index.py](moss-utils/create_index.py) to match.

```bash
cd moss-utils
uv run create_index.py
```

This uses the Moss parse pipeline to chunk the PDF into searchable documents and create a named index. The index name must match `MOSS_INDEX_NAME` in your `.env` (defaults to `Harry-Potter-Persona`).

### 4. Run the agent

```bash
cd agent
uv run agent.py dev
```

Connect to your LiveKit room and start talking.

### 5. Add a UI (optional)

Use [agent-starter-react](https://github.com/livekit-examples/agent-starter-react) as a ready-made frontend:

```bash
git clone https://github.com/livekit-examples/agent-starter-react
cd agent-starter-react
cp .env.example .env.local
```

Fill in `.env.local` with the same LiveKit credentials you used for the agent:

```env
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
```

Then run the dev server:

```bash
npm install
npm run dev
```

Open `http://localhost:3000`, click **Connect**, and start talking to Harry Potter.

## Customizing the persona

Edit the `instructions` in [agent/agent.py](agent/agent.py) to change who the agent speaks as. Update the `search_knowledge` tool docstring to reflect what the new knowledge base contains.

## Project structure

```text
agent/
  agent.py          # Voice agent, LiveKit session, Moss tool
moss-utils/
  create_index.py   # Parse PDF and create Moss index
```
