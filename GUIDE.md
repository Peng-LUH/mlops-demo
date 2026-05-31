## Einführung
Dieses Tutorial kombiniert:
1. lokale Python-Entwicklung für Machine Learning mit `uv`
1. FastAPI-/Pytorch-MLOps-Demo-App
1. Tests, Formatting, und Linting mit `pytest` und `ruff`
1. GitHub Repository
1. GitHub Actions CI
1. Container Build und Push nach `GHCR`
1. lokaler Kubernetes-Cluster mit `kind`
1. Deployment auf Kubernetes
1. ConfigMap, Secret, Service, Probes, Resources, Rollout, Rollback
1. HPA, Metrics Server und Lasttest mit `k6`

## Pipeline des Tutorials
```txt
Developer Laptop
  |
  | 1. Code schreiben
  | 2. uv sync / ruff / pytest
  | 3. git push
  v

GitHub Repository
  |
  | GitHub Actions
  | - CI
  | - Docker Build
  | - Push to GHCR
  v

GitHub Container Registry
  |
  | image: ghcr.io/<user>/mlops-kind-demo:<tag>
  v

Local kind Kubernetes Cluster
  |
  | Deployment
  | Service
  | ConfigMap
  | Secret
  | HPA
  v

FastAPI + PyTorch MLOps API
```

Die Anwendung ist bewusst einfach: Eine FastAPI-APP lädt ein kleines PyTorch-Modell und stellt einen /predict -Endpunkt bereit. Zusätzlich gibt es Health- und Metrics-Endpunkte:
```
/health/live
/health/ready
/metrics
/predict
```

Diese Endpunkte sind wichtig, weil K8S damit erkennen kann, ob ein Container lebt, ob er Traffic bekommen darf und welche Metriken 

## Voraussetzung
- 
- [Setup devbox](#devbox_setup.md)
- start devbox
    ```bash
    devbox shell
    ```
- Überprüfung die Installation der folgenden Tools:
  ```bash
  docker --version
  Docker version 29.1.5, build 0e6fee6

  # sudo apt install kubectx
  kubectl verison --client
  Client Version: v1.35.2
  Kustomize Version: v5.7.1

  kind version

  # install uv: curl -LsSf https://astral.sh/uv/install.sh | sh
  uv --version

  python3 --version
  Python 3.12.3
  ```

## Projektstruktur erstellen
- Folgende Directories erstellen:
  ```bash
  mkdir -p app/src/ml_api
  mkdir -p k8s
  mkdir -p loadtest
  ```

Zielstruktur:
```bash
mlops-demo/
  ├── .devbox/
  ├── .venv/
  ├── .github/
  │   └── workflows/
  │       ├── ci.yaml
  │       └── docker-publish.yaml
  ├── app/
  │   ├── pyproject.toml
  │   └── src/
  │       └── ml_api/
  │           ├── __init__.py
  │           ├── main.py
  │           ├── model.py
  │           └── metrics.py
  ├── tests/
  │   └── test_api.py
  ├── k8s/
  │   ├── namespace.yaml
  │   ├── configmap.yaml
  │   ├── secret.yaml
  │   ├── deployment.yaml
  │   ├── service.yaml
  │   └── hpa.yaml
  ├── loadtest/
  │   └── load-test.js
  ├── devbox.json
  ├── devbox.lock
  ├── kind-config.yaml
  ├── Dockerfile
  ├── .gitignore
  └── README.md
```

## 2 Python-Projekt mit uv konfigurieren
### 2.0 Python-Project mit uv initialisieren
```bash
# zu /app navigieren
cd app

# als python package initialisieren
uv init --package
```

.venv erzeugen
```bash
uv sync

# activate the virtual environment
source .venv/bin/activate
```

Danach entsteht ungefähr:
```bash
app/
├── .venv/
├── pyproject.toml
├── README.md
└── src/app/__init__.py
```



Dependencies hinzufügen:
```bash
uv add fastapi "uvicorn[standard]" torch prometheus-client pydantic
```

Devlopment Dependencies
```bash
uv add --dev pytest httpx ruff
```
Dann
```bash
uv sync --all-groups
```

Dadurch 

### 2.1 `pyproject.toml`
```toml
# pyproject.toml file
[project]
name = "ml-api"
version = "0.1.0"
description = "Simple MLOps API for K8S kind demo"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "torch>=2.3.0",
  "prometheus-client>=0.20.0",
  "pydantic>=2.7.0",
]

[dependency-groups]
dev = [
  "pytest>=8.0.0",
  "httpx>=0.27.0",
  "ruff>=0.8.0",
]

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.ruff]
line-length = 88
target-version = "py312"


[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
ignore = []

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["../tests"]
```

## 3 FastAPI-MLOps-App bauen

```python
# mlops-demo/app/src/model.py
import torch
from torch import nn


class SimpleModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(3, 1)

    def forward(self, x):
        return self.linear(x)


class ModelService:
    def __init__(self):
        self.model = SimpleModel()
        self.model.eval()
        self.ready = True

    def predict(self, features: list[float]) -> float:
        if len(features) != 3:
            raise ValueError("Exactly 3 features are required.")

        with torch.no_grad():
            x = torch.tensor([features], dtype=torch.float32)
            y = self.model(x)
            return float(y.item())


```
```python
## app/src/ml-api/metrics.py
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "ml_api_requests_total",
    "Total number of API requests",
    ["endpoint"],
)

PREDICTION_LATENCY = Histogram(
    "ml_api_prediction_latency_seconds",
    "Prediction latency in seconds",
)
```

Das App lokal starten:
```bash
cd app
uv run uvicorn ml_api.main:app --host 0.0.0.0 --port 8000
```

In einem zweiten Terminal:
```bash
curl http://localhost:8000/
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Prediction testen:
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [1.0, 2.0, 3.0]}'
```

Metrics testen
```
curl http://localhost:8000/metrics
```

Das App stoppen:
- Wenn das Terminal noch offen, dann einfach im Terminal Ctrl+C drücken.

- falls das Terminal bereits geschlossen ist:
  ```bash

  lsof -i :8000 
  # PID kopieren
  kill <pid>
  ```

## 5 Tests hinzufügen

```python
# mlops-demo/tests/test_api.py

from fastapi.testclient import TestClient
from ml_api.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "MLOps API is running"


def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_health_ready():
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_predict():
    response = client.post(
        "/predict",
        json={"features": [1.0, 2.0, 3.0]},
    )
    assert response.status_code == 200
    body = response.json()
    assert "prediction" in body
    assert "model_version" in body
```

Tests ausführen:
```bash
cd app
uv run pytest ../tests
cd ..
```

## 6 Formatting und Linting mit Ruff
Format prüfen
```bash
# workdir: mlops-demo/
uv run ruff format --check app/src tests
```

Format anwenden:
```bash
# workdir: mlops-demo/
uv run ruff format app/src tests
```

Linting:
```bash
# workdir: mlops-demo/
uv run ruff check app/src tests
```

Auto-Fix:
```bash
# workdir: mlops-demo/
uv run ruff check app/src tests --fix
```

Empfohlener lokaler Qualitätscheck:
```bash
## Diese Schritte bilden später die CI-Pipeline

cd app # workdir: mlops-demo/app
uv sync --all-groups
uv run format --check src ../tests
uv run ruff check src ../tests
uv run pytest ../tests
cd .. 
```

## 7 Dockerfile mit uv erstellen

```dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

COPY app/pyproject.toml app/uv.lock app/README.md ./
COPY app/src ./src #kopiert den loklen Quellcode-Ordner

RUN pip install --no-cache-dir uv \
  && uv sync --frozen --no-dev

FROM python:3.12-slim

WORKDIR /app 

COPY --from=builder /app/.venv /app/.venv
COPY app/src ./src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

USER 1000

EXPOSE 8000

CMD ["uvicorn", "ml_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Wichtige Punkte:
- uv.lock wird in das Image eingebunden
- uv sync --frozen verhindert ungeplante Dependency-Änderungen
- Dev Dependencies werden nicht installiert
- Container läuft nicht als root
- Secrets werden nicht ins Image eingebaut

Diese Punkte entsprechen den Container-Best-Practices: kleine/reproduzierbare Images, keine Secrets im Image, nicht als root laufen, feste Versionen und regelmäßige Prüfungen.

Image bauen:
```bash
docker build -t ml-api:0.1.0 .
```

Container local testen:
```bash
docker run --rm -p 8000:8000 ml-api:0.1.0
```

Test
```bash
curl http://localhost:8000/
```

## 8 Git Repository vorbereiten

### 8.1 .gitignore
```yaml
# Python-generated files
__pycache__/
*.py[oc]
build/
dist/
wheels/
*.egg-info/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/

# Test / coverage
.pytest_cache/
.coverage
htmlcov/

# OS / IDE
.DS_Store
.vscode/
.idea/

# Virtual environments
.venv
*/.venv
venv/

# devbox
.devbox

# Environment files
.env
.env.*

# Local files
*.log

# k6 output
summary.json

#local kube files
kubeconfig*
```

> Wichtig: app/uv.lock file nicht ignorieren.

### 8.2 Git initialisieren
```bash
git init
git add .
git commit -m "Initial MLOps demo with kubernetes kind"
```

## 9 GitHub Repository erstellen
### 9.1 Variante A: GitHub Web UI

- Login to [GitHub](https://github.com/), und erstell ein neues Repository
- Name: mlops-demo
- Kein README, keine .gitignore, keine License hinzufügen, weil lokal schon Dateien existieren.
- Die Remote verbinden
```
git remote add origin git@github.com:<github-user>/mlops-demo.git
git branch -M main
git push -u orgin main # pushing von main zu origin (main -> origin)
```

### 9.2 Variante B: GitHub CLI
```bash
gh version # github cli tool überprüfen
gh auth login
gh repo create mlops-demo --public --source=. --remote=origin --push
```

Für ein privates Repository
```bash
gh repo create mlops-demo --private --source=. --remote=origin --push
```

## 10 GitHub Actions: CI Workflow

- GitHub Actions Workflows sind YAML-Dateien im Verzeichnis `<root>/.github/workflows/`.

- GitHub beschreibt einen Workflow als konfigurierbaren automatisierten Prozess aus einem oder mehreren **Jobs**.

- Dokumentation: [Worklow Syntax for GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax?utm_source=chatgpt.com)

- Für `uv` empfielt die offizielle Dokumentation die Action `astral-sh/setup-uv`, die uv installiert und optional Caching aktiviert.

```yaml
# .github/workflows/ci.yaml
name: CI

on:
  push:
    branches: [main]
  pull_requests:
    branches: [main]

jobs:
  python-quality:
    name: Python quality checks
    runs-on: ubuntu-latest
    
    defaults:
      run:
        working-directory: app
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v6
      
      - name: Install uv
        ueses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
      
      - name: Setup Python
        run: uv python install 3.12
      
      - name: Install Dependencies
        run: uv sync --all-groups --frozen
      
      - name: Check Formatting
        run: uv run ruff format --check src ../tests
      
      - name: Lint
        run: uv run ruff check src ../tests
      
      - name: Test
        run: uv run pytest ../tests
```

Committen und pushen:
```bash
git add .
git commit -m "Add CI workflow with uv"
git push
```

> The workflow should be running if you navigate to the Actions in GitHub UI.

Der Workflow führt aus:
1. setup workdir -> `working-directory: app`
1. checkout -> `ueses: actions/checkout@v6`
1. install uv -> `uses: astrl-sh/setup-uv@v6`
1. install dependencies -> `uv sync --all-groups --frozen`
1. check format -> `uv run ruff format --check ... ...`
1. check linting -> `uv run ruff check ... ... `
1. testing -> `uv run pytest ...`

## 11 GitHub Actions: Docker Build Workflow

Dieser Worfflow prüft, ob das Docker Image gebaut werden kann.

```yaml
# .github/workflows/docker-build.yaml
name: Docker Build

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  docker-build:
    name: Build Docker Image
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v6

      - name: Build Image
        run: |
          docker build -t ml-api:${{ github.sha }} .
```