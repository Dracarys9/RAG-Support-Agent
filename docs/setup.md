# Local setup

Open PowerShell in the project folder.

## Create a virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run the project commands without activating the environment by using `.venv\Scripts\python.exe` directly, or ask for help before changing the Windows execution policy.

## Install the project and test tools

```powershell
py -m pip install --upgrade pip
py -m pip install -e .
py -m pip install -r requirements-dev.txt
```

## Run the smoke test

```powershell
py -m pytest -q
```

The first milestone should finish with one passing test. The actual retrieval and support-agent behavior will be added in later milestones.
