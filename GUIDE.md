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

Committen und pushen:
```bash
git add .github/workflows/docker-build.yaml
git commit -m "add docker-build.yaml file"
git push
```

#### Wo liegt das Image danch?
- Nur temporär auf dem GitHub-Actions-Runner.
- Also ungefähr:
  ```bash
  GitHub Actions Runner
  └── Docker Engine
      └── Image: ml-api:<commit-sha>
  ```
- Es wird **nicht** automatisch gespeichert und **nicht** automatisch gepusht.

- Nach Ende des Workflow-Laufs wird der Runner verworfen. Damit verschiwindet auch das lokal gebaute Docker Image.

- Dieser Workflow überprüft nur: `Kann das Docker Image erfolgreich gebaut werden?`

- Es veröffentlicht das Image nicht.

- Für build und push wird ein zusätzlicher Workflow `Build und Push nach GHCR` gebaut. Dort passiert:
  ```bash
  docker push "$IMAGE_NAME:${{ github.sha }}"
  docker push "$IMAGE_NAME:latest"
  ```
  Erst dadurch landet das Image in der GitHub Container Resigtry.

## 12 GitHub Actions: Build und Push nach GHCR
```yaml
# .github/workflows/container.yaml
name: Container

on:
  push:
    branches: [main]
  tags:
    - "v*.*.*"

permissions:
  contents: read
  packages: write

jobs:
  build-and-push:
    name: Buid and push container image
    runs-on: ubuntu-latest

    steps:
      - name: checkout repository
        uses: actions/checkout@v6
      
      - name: Login to GHCR
        run: |
          echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io \
            -u "${{ github.actor }}" \
            --password-stdin
      
      - name: set image name
        run: |
          REPO_OWNER=$(echo "${GITHUB_REPOSITORY_OWNER}" | tr '[:upper:]' '[:lower:]')
          echo "IMAGE_NAME=ghcr.io/${REPO_OWNER}/mlops-demo" >> "$GITHUB_ENV"
      
      - name: Build image
        run: |
          docker build \
            -t "$IMAGE_NAME:${{ github.sha }}" \
            -t "$IMAGE_NAME:latest" \
            .

      - name: Push image by commit SHA
        run: |
          docker push "$IMAGE_NAME:${{ github.sha }}"
      
      - name: Push latest image
        if: github.ref == 'refs/heads/main'
        run: |
          docker push "$IMAGE_NAME:latest"
```

Wenn der Workflow erfolgreich durchgeführt ist, kann man das Image unter Packages im GitHub-Profil finden. 

## 13 Kind Cluster erstellen
Dokumentation: [kind](https://kind.sigs.k8s.io/docs/user/configuration/?utm_source=chatgpt.com)

### 13.1 kind-Konfiguration

```yaml
# kind/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: mlops-demo
  - role: control-plane
    extraPortMappings:
      - containerPort: 30080
        hostPort: 8080
        protocol: TCP
  
  - role: worker
    extraPortMappings:
      - containerPort: 30080
        hostPort: 8082
        protocol: TCP
    extraMounts:
      - hostPath: /home/peng-luh/__git/devops_mlops_101/mlops-demo/.mounts/mount_worker_1
      containerPath: /mounts/worker
  
  - role: worker
    extraPortMappings:
      - containerPort: 30080
        hostPort: 8084
        protocol: TCP
    extraMounts:
      - hostPath: /home/peng-luh/__git/devops_mlops_101/mlops-demo/.mounts/mount_worker_2
      containerPath: /mounts/work
```

Cluster erstellen:
```bash
kind create cluster --config kind/kind-config.yaml
```

Kind-Cluster stoppen und löschen:
```
kind get clusters
kind delete cluster --name <cluster-name>
```

Prüfen
```bash
kubectl cluster-info
kubectl get nodes
```

## 14 Lokales Image in Kind laden
Für den ersten Durchlauf nutzen wir das lokal gebaute Image:
```bash
# docker build -t ml-api:0.1.0
kind load docker-image ml-api:0.1.0 --name mlops-demo
```

Das ist notwendig, weil der kind Node ein eigener Container ist. Das lokal gebaute Docker-Image ist für Kubernetes im Kind-Cluster nicht automatisch verfügbar. Die Kind-Dokumentation zeigt dafür `kind load docker-image my-app:latest`; bei benannten Clustern wird `--name <cluster-name>` verwendet.

## 15 Kubernetes-Manifeste erstellen
- `Kubernetes-Manifeste` sind Konfigurationsdateien, in denen du beschreibst, welche Kubernetes-Ressourcen existieren sollen.
- Meinstens sind die Manifeste in YAML geschrieben. Zum Beispiel:
  ```yaml
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: ml-api
  spec:
    replicas: 2
  ```
  > Ein Manifest ist also eine deklarative Beschreibung des gewünschten Zustands.

- Ein Manifest ist eine Datei, die beschreibt, was vorhanden sein soll. In K8S bedeutet das konkret:
  
  1. Diese Ressource soll im Cluster existieren.
  1. So soll sie heißen.
  1. So soll sie konfiguriert sein.
  1. So viele Instanzen sollen laufen.
  1. Welches Image soll verwendet werden.
  1. Welche Ports, Umgebungsvariablen, Volumes, Limits usw. sollen gelten.

- Beispiele für K8S Manifeste
  ```bash
  k8s/
  ├── namespace.yaml
  ├── configmap.yaml
  ├── secret.yaml
  ├── deployment.yaml
  ├── service.yaml
  └── hpa.yaml
  ``` 


### 15.1 Namespace
Ein Namespace ist eine logische Umgebung im Cluster.
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mlops-demo
```
Ein Namespace ist ähnlich wie ein Projektordner im Cluster. Deine Anwendung, Services, Secrets und ConfigMaps können darin gruppiert werden.

### 15.2 ConfigMap
Ein ConfigMap enthält nicht-sensitive Konfiguration.
```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ml-api-config
  namespace: mlops-demo
data:
  MODEL_VERSION: "v1"
  LOG_LEVEL: "INFO"
```

Bedeutungen:
- speichere Konfiguration für die Anwendung
- MODEL_VERSION ist v1.
- LOG_LEVEL ist INFO.

Diese Werte kann Container später als Umgebungsvariablen bekommen.

### 15.3 Secrets
Ein Secret enthält sensitive Werte, zum Beispiel Tokens oder Passwörter.
```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: ml-api-secret
  namespace: mlops-demo
type: Opaque
stringData:
  API_TOKEN: "demo-token-change-me"
```

### 15.4 Deployment
Ein Deployment beschreibt, wie deine Anwendung laufen soll.

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ml-api
  namespace: mlops-demo
  labels:
    app: ml-api
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  selector:
    matchLabel:
      app: ml-api
  template:
    metadata:
      labels:
        app: ml-api
    spec:
      containers:
        - name: ml-api
          image: ml-api:0.1.0
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
      
          env:
            - name: MODEL_VERSION
              valueFrom:
                configMapKeyRef:
                  name: ml-api-config
                  key: MODEL_VERSION
            - name: LOG_LEVEL
              valueFrom:
                configMapKeyRef:
                  name: ml-api-config
                  key: LOG_LEVEL
            - name: API_TOKEN
              valueFrom:
                secretKeyRef:
                  name: ml-api-secret
                  key: API_TOKEN
          
          readinessProbe:
            httpGet:
              path: /health/ready
              port: 8000
            initialDeplaySeconds: 5
            periodSeconds: 10
          
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 15
            periodSecond: 20
          
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1"
              memory: "1Gi"
          
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop:
                - ALL
```

Das Deployment enthält bewusst mehrere Best-Practice-Elemente:
- zwei Replicas
- Rolling Update
- Readiness/Liveness Probe
- Resource Requests/Limits
- ConfigMap/Secret-Integration
- eingeschränkte Container-Rechte.

### 15.5 Service
```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: ml-api
  namespace: mlops-demo
  labels:
    app: ml-api
spec:
  type: NodePort
  selector:
    app: ml-api
  ports:
    - name: http
      port: 80
      targetPort: 8000
      nodePort: 30080
```

### 15.6 HPA (Horizontal Pod Autosaler)

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ml-api-hpa
  namesapce: mlops-demo
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ml-api
  minReplicas: 2
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50
```

## 16 Deployment auf kind-Cluster
- Apply
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

- Status prüfen:
```bash
kubectl get all -n mlops-demo
kubectl get pods -n mlops-demo
kubectl get service -n mlops-demo
```

- Test
```bash
curl http://localhost:8000/
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/live
```

- prediction
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [1.0, 2.0, 3.0]}'
```

- metrics
```bash
curl http://localhost:8000/metrics
```

## 17 Kubernetes-Konzepte prüfen
### 17.1 Deployment, ReplicaSet, Pod
```bash
kubectl get deployment -n mlops-demo
kubectl get replicaset -n mlops-demo
kubectl get pods -n mlops-demo
```

Zusammenhang:

- Deployment -> verwaltet Rollouts und gewünschte Version
- ReplicaSet -> hält gewünschte Anzahl Pods stabil
- Pod -> kleinste auführbare Einheit
- Container -> läuft innerhalb des Pods

### 17.2 Service und Labels
```bash
kubectl get pods -n mlops-demo --show-labels
kubectl describe service ml-api -n mlops-demo
kubectl get endpoints ml-api -n mlops-demo
```

Der Service wählt Pods über diesen Selector aus:
```yaml
selector:
  app: ml-api
```

Wenn der Selector nicht zu den Pod-Labels passt, hat der Service keine Endpoins.

## 18 Debugging-Kommandos
Logs
```bash
kubectl logs deployment/ml-api -n mlops-demo
```

Pod-Details
```bash
kubectl describe pod <pod-name> -n mlops-demo
```

Events:
```bash
kubectl get events -n mlops-demo --sort-by=.metadata.creationTimestamp
```

In den Container gehen:
```bash
kubectl exec -it deployment/ml-api -n mlops-demo -- /bin/sh
```

Empfohlene Debugging-Reihenfolge:
```bash
- kubectl get pods
- kubectl describe pod
- kubectl logs
- kubectl get events
- kubectl describe service
- kubectl get endpoints
```

## Readiness Probe praktisch testen
Ändere in k8s/deployment.yaml testweise:
```yaml
readinessProbe:
  httpGet:
    path: /wrong
    port: 8000
```

Anwenden:
```bash
kubectl apply -f k8s/deployment.yaml
kubectl get pods -n mlops-demo -w
```
Du wirst sehen, dass Pods nicht `Ready` werden.

Zurück ändern:
```yaml
# k8s/deployment.yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
```

Dann wieder anwenden:
```bash
kubectl apply -f k8s/deployment.yaml
kubectl rollout status deployment/ml-api -n mlops-demo
```

Merke:
- `readinessProbe` -> entscheidet, ob ein Pod Traffic bekommt
- `livenessProbe` -> entscheidet, ob ein Container neu gestartet wird
- `startupProbe` -> gitb langsam startenden Apps mehr Zeit

