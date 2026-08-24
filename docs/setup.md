# Local setup

Open PowerShell in the project folder.

## Create a virtual environment

```
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run the project commands without activating the environment by using `.venv\Scripts\python.exe` directly. Do not change the Windows execution policy just for this project unless you understand the setting.

## Install the project and test tools

```
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Run tests and evaluations

```
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe evaluation\run_visible.py
```

The current expected results are **43 passing tests**, **15/15 visible cases**, and **5/5 original cases**.

## Run the local deterministic chat

```
.\.venv\Scripts\python.exe -m rag_support_agent.cli
```

Type `quit` to stop. Use `--debug` to print the safe trace:

```
.\.venv\Scripts\python.exe -m rag_support_agent.cli --debug
```

## Run the browser chat interface with one command

The easiest way to start the browser chat is:

```
.\run_chat.ps1
```

The launcher installs the project dependencies if needed, opens the browser, and starts the support server. Open `http://127.0.0.1:5000` if the browser does not open automatically. Press `Ctrl+C` in PowerShell to stop the server.

If PowerShell blocks local scripts, use:

```
powershell -ExecutionPolicy Bypass -File .\run_chat.ps1
```

The browser interface uses the same support agent and keeps one conversation session while the server is running. It shows the answer, sources, retrieval details, human-help status, and whether Gemini or local mode produced the response. The API key remains on the server and is never placed in the browser page.

The manual alternative is:

```
.\.venv\Scripts\python.exe -m rag_support_agent.web_app
```

## Use the real LLM-backed RAG path

Local mode is the default and needs no key. To use the optional OpenAI-compatible model path, copy the environment template:

```
Copy-Item .env.example .env
```

Open `.env` and set:

```
MODEL_PROVIDER=llm
MODEL_NAME=gpt-5-mini
OPENAI_API_KEY=your-real-key-here
```

If your provider uses a custom OpenAI-compatible address, also set `OPENAI_API_BASE`. Never commit `.env` or a real key. The model receives only selected knowledge passages or the sanitized result of one order lookup. If the provider is unavailable, the program uses the local deterministic answer path instead.