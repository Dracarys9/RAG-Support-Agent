# Local setup

Open PowerShell in the project folder.

## Create a virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run the project commands without activating the environment by using `.venv\Scripts\python.exe` directly. Do not change the Windows execution policy just for this project unless you understand the setting.

## Install the project and test tools

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Run tests and evaluations

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe evaluation\run_visible.py
```

The current expected results are **38 passing tests**, **15/15 visible cases**, and **5/5 original cases**.

## Run the local deterministic chat

```powershell
.\.venv\Scripts\python.exe -m rag_support_agent.cli
```

Type `quit` to stop. Use `--debug` to print the safe trace:

```powershell
.\.venv\Scripts\python.exe -m rag_support_agent.cli --debug
```

## Use the real LLM-backed RAG path

Local mode is the default and needs no key. To use the optional OpenAI-compatible model path, copy the environment template:

```powershell
Copy-Item .env.example .env
```

Open `.env` and set:

```text
MODEL_PROVIDER=llm
MODEL_NAME=gpt-5-mini
OPENAI_API_KEY=your-real-key-here
```

If your provider uses a custom OpenAI-compatible address, also set `OPENAI_API_BASE`. Never commit `.env` or a real key. The model receives only selected knowledge passages or the sanitized result of one order lookup. If the provider is unavailable, the program uses the local deterministic answer path instead.
