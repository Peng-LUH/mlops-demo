Unten ist die Erweiterung zum letzten `kind`-Tutorial. Sie fügt zwei neue Teile hinzu:

```text
Teil A: Projekt als GitHub Repository aufsetzen
Teil B: GitHub Actions Workflows einrichten
```

Der lokale `kind`-Teil bleibt weiterhin wichtig: GitHub Actions baut und veröffentlicht dein Image, aber dein lokaler `kind`-Cluster wird nicht automatisch aus GitHub heraus erreicht. Für den Lernpfad ist deshalb diese Trennung sinnvoll:

```text
Lokal:
  kind Cluster
  kubectl apply
  kind load docker-image

GitHub Actions:
  Code prüfen
  Tests ausführen
  Docker Image bauen
  Image zu GHCR pushen
```

GitHub Actions Workflows sind YAML-Dateien, die in `.github/workflows/` liegen. Ein Workflow besteht aus Jobs und Steps und wird z. B. durch `push` oder `pull_request` ausgelöst. ([GitHub Docs][1]) Für Container Images kann GitHub Actions Images bauen und zu GitHub Container Registry, also `ghcr.io`, veröffentlichen. ([GitHub Docs][2])

---

# Erweiterung: GitHub Repository und GitHub Actions

## Neue Zielstruktur

Am Ende sieht dein Projekt so aus:

```text
mlops-kind-demo/
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
├── Dockerfile
├── kind-config.yaml
├── .gitignore
└── README.md
```

---

# Teil A: Projekt als GitHub Repository aufsetzen

## 1. `.gitignore` erstellen

Im Projektroot:

```bash
cat > .gitignore <<'EOF'
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.env

# Test / coverage
.pytest_cache/
.coverage
htmlcov/

# IDE
.vscode/
.idea/

# OS
.DS_Store

# Local files
*.log
EOF
```

Wichtig: `.venv` wird nicht committed. Virtuelle Umgebungen gehören nicht ins Repository.

---

## 2. README erstellen

````bash
cat > README.md <<'EOF'
# MLOps kind Demo

This project demonstrates how to deploy a simple FastAPI + PyTorch MLOps API to a local Kubernetes kind cluster.

## Stack

- Python
- FastAPI
- PyTorch
- Docker
- Kubernetes
- kind
- GitHub Actions
- GitHub Container Registry

## Local run

```bash
cd app
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn ml_api.main:app --host 0.0.0.0 --port 8000
````

## Build container image

```bash
docker build -t ml-api:0.1.0 .
```

## Create kind cluster

```bash
kind create cluster --config kind-config.yaml
```

## Load image into kind

```bash
kind load docker-image ml-api:0.1.0 --name mlops-demo
```

## Deploy to Kubernetes

```bash
kubectl apply -f k8s/
```

## Test

```bash
curl http://localhost:8080/
curl http://localhost:8080/health/ready
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [1.0, 2.0, 3.0]}'
```

EOF

````

---

## 3. Git lokal initialisieren

Falls noch nicht geschehen:

```bash
git init
````

Status prüfen:

```bash
git status
```

Dateien hinzufügen:

```bash
git add .
```

Ersten Commit erstellen:

```bash
git commit -m "Initial MLOps kind demo"
```

Branch auf `main` setzen:

```bash
git branch -M main
```

---

## 4. Repository auf GitHub erstellen

Auf GitHub:

```text
1. GitHub öffnen
2. New repository wählen
3. Repository-Name: mlops-kind-demo
4. Public oder Private wählen
5. Kein README hinzufügen, weil du lokal schon eins hast
6. Repository erstellen
```

Danach zeigt GitHub dir ungefähr diesen Befehl:

```bash
git remote add origin https://github.com/<github-user>/mlops-kind-demo.git
git push -u origin main
```

Beispiel:

```bash
git remote add origin https://github.com/shen/mlops-kind-demo.git
git push -u origin main
```

Prüfen:

```bash
git remote -v
```

---

# Teil B: Tests ergänzen

Bevor wir GitHub Actions bauen, brauchen wir mindestens einen Test.

## 1. Test-Abhängigkeiten ergänzen

Passe `app/pyproject.toml` an:

```toml
[project]
name = "ml-api"
version = "0.1.0"
description = "Simple MLOps API for Kubernetes kind demo"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "torch>=2.3.0",
    "prometheus-client>=0.20.0",
    "pydantic>=2.7.0"
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "httpx>=0.27.0",
    "ruff>=0.6.0"
]

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"
```

---

## 2. Testdatei erstellen

```bash
mkdir -p tests
```

```bash
cat > tests/test_api.py <<'EOF'
from fastapi.testclient import TestClient
from ml_api.main import app


client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "MLOps API is running"


def test_liveness():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness():
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_predict():
    response = client.post(
        "/predict",
        json={"features": [1.0, 2.0, 3.0]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "prediction" in data
    assert "model_version" in data


def test_predict_invalid_input():
    response = client.post(
        "/predict",
        json={"features": [1.0, 2.0]},
    )
    assert response.status_code == 500
EOF
```

Hinweis: Der letzte Test erwartet aktuell `500`, weil unser Code bei falscher Feature-Anzahl eine `ValueError` auslöst, die FastAPI nicht sauber als `400 Bad Request` behandelt. Für ein Lernprojekt ist das sogar nützlich, weil du später Error Handling verbessern kannst.

---

## 3. Tests lokal ausführen

Vom Projektroot:

```bash
cd app
source .venv/bin/activate
pip install -e ".[dev]"
cd ..
PYTHONPATH=app/src pytest tests
```

Alternativ ohne `PYTHONPATH`, wenn das Paket installiert ist:

```bash
cd app
pip install -e ".[dev]"
cd ..
pytest tests
```

---

## 4. Linting lokal ausführen

```bash
ruff check app/src tests
```

Optional Auto-Fix:

```bash
ruff check app/src tests --fix
```

Commit:

```bash
git add .
git commit -m "Add tests and development dependencies"
git push
```

---

# Teil C: GitHub Actions CI Workflow

Dieser Workflow prüft bei jedem Push und Pull Request:

```text
1. Repository auschecken
2. Python installieren
3. Paket mit Dev-Abhängigkeiten installieren
4. Ruff Linting ausführen
5. Pytest ausführen
```

GitHub beschreibt einen Workflow als konfigurierbaren automatisierten Prozess, der durch eine YAML-Datei definiert wird. ([GitHub Docs][1])

## 1. Workflow-Ordner erstellen

```bash
mkdir -p .github/workflows
```

## 2. `ci.yaml` erstellen

```bash
cat > .github/workflows/ci.yaml <<'EOF'
name: CI

on:
  push:
    branches:
      - main
  pull_request:

jobs:
  test:
    name: Lint and test Python app
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install package
        run: |
          python -m pip install --upgrade pip
          pip install -e "app[dev]"

      - name: Run Ruff
        run: |
          ruff check app/src tests

      - name: Run tests
        run: |
          pytest tests
EOF
```

Commit und Push:

```bash
git add .github/workflows/ci.yaml
git commit -m "Add CI workflow"
git push
```

Danach auf GitHub:

```text
Repository öffnen
→ Actions
→ CI
→ Workflow Run ansehen
```

---

# Teil D: Docker Build Workflow ohne Push

Bevor wir Images veröffentlichen, bauen wir nur das Docker Image. Das prüft, ob das Dockerfile korrekt ist.

## 1. `docker-build.yaml`

```bash
cat > .github/workflows/docker-build.yaml <<'EOF'
name: Docker Build

on:
  push:
    branches:
      - main
  pull_request:

jobs:
  docker-build:
    name: Build Docker image
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Build image
        run: |
          docker build -t ml-api:${{ github.sha }} .
EOF
```

Commit:

```bash
git add .github/workflows/docker-build.yaml
git commit -m "Add Docker build workflow"
git push
```

Dieser Workflow veröffentlicht noch nichts. Er prüft nur:

```text
Kann das Image auf einem frischen GitHub Runner gebaut werden?
```

Das ist ein wichtiger Unterschied:

```text
Build prüfen  → gut für Pull Requests
Image pushen  → eher für main branch oder Tags
```

---

# Teil E: Docker Image nach GHCR pushen

Jetzt kommt die eigentliche Publishing-Pipeline.

GitHub Container Registry unterstützt OCI-kompatible Container Images. ([GitHub Docs][3]) Für GitHub Packages kann ein Workflow `GITHUB_TOKEN` verwenden, ohne dass du manuell einen Personal Access Token speichern musst. ([GitHub Docs][4]) Der Token ist auf das Repository begrenzt, in dem der Workflow läuft. ([GitHub Docs][5])

## 1. Workflow: `docker-publish.yaml`

```bash
cat > .github/workflows/docker-publish.yaml <<'EOF'
name: Docker Publish

on:
  push:
    branches:
      - main
    tags:
      - "v*.*.*"

permissions:
  contents: read
  packages: write

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  docker-publish:
    name: Build and publish Docker image
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha
            type=raw,value=latest,enable={{is_default_branch}}
            type=ref,event=tag

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and push image
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
EOF
```

Das Docker `build-push-action` baut und pusht Images mit Buildx und unterstützt u. a. BuildKit-Funktionen, Multi-Platform-Builds und Caching. ([GitHub][6])

Commit:

```bash
git add .github/workflows/docker-publish.yaml
git commit -m "Add Docker publish workflow"
git push
```

---

## 2. Was passiert jetzt?

Bei Push auf `main` baut GitHub Actions ein Image und pusht es nach:

```text
ghcr.io/<github-user>/<repo-name>:latest
ghcr.io/<github-user>/<repo-name>:sha-<commit-sha>
```

Beispiel:

```text
ghcr.io/shen/mlops-kind-demo:latest
ghcr.io/shen/mlops-kind-demo:sha-a1b2c3d
```

Wichtig: `github.repository` enthält automatisch:

```text
<owner>/<repository>
```

Also wird daraus:

```text
ghcr.io/<owner>/<repository>
```

---

## 3. Package auf GitHub finden

Auf GitHub:

```text
Repository öffnen
→ rechte Seitenleiste
→ Packages
→ Container Image öffnen
```

Oder in deinem Profil:

```text
GitHub Profile
→ Packages
```

Falls das Image private ist, musst du die Sichtbarkeit eventuell anpassen:

```text
Package
→ Package settings
→ Change visibility
```

---

# Teil F: Lokales kind-Deployment auf GHCR-Image umstellen

Bisher verwendet dein Deployment:

```yaml
image: ml-api:0.1.0
imagePullPolicy: IfNotPresent
```

Das ist für `kind load docker-image` gut.

Jetzt kannst du stattdessen GHCR verwenden:

```yaml
image: ghcr.io/<github-user>/mlops-kind-demo:latest
imagePullPolicy: Always
```

In `k8s/deployment.yaml`:

```yaml
containers:
  - name: ml-api
    image: ghcr.io/<github-user>/mlops-kind-demo:latest
    imagePullPolicy: Always
```

Anwenden:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl rollout status deployment/ml-api
```

Wenn dein GHCR Package öffentlich ist, sollte kind das Image direkt ziehen können.

---

# Teil G: Private GHCR Images mit Kubernetes Secret verwenden

Falls dein GHCR Image privat ist, braucht Kubernetes ein Pull Secret.

## 1. GitHub Personal Access Token erstellen

Für private Images brauchst du lokal einen Token mit mindestens:

```text
read:packages
```

Bei klassischem PAT:

```text
GitHub
→ Settings
→ Developer settings
→ Personal access tokens
→ Tokens
→ Generate token
```

## 2. Kubernetes Image Pull Secret erstellen

```bash
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=<github-user> \
  --docker-password=<github-token> \
  --docker-email=<your-email>
```

## 3. Deployment anpassen

In `k8s/deployment.yaml`:

```yaml
spec:
  imagePullSecrets:
    - name: ghcr-secret
  containers:
    - name: ml-api
      image: ghcr.io/<github-user>/mlops-kind-demo:latest
```

Achte auf die korrekte Position. Vollständiger Ausschnitt:

```yaml
spec:
  template:
    spec:
      imagePullSecrets:
        - name: ghcr-secret
      containers:
        - name: ml-api
          image: ghcr.io/<github-user>/mlops-kind-demo:latest
          imagePullPolicy: Always
```

Dann:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl rollout restart deployment/ml-api
kubectl rollout status deployment/ml-api
```

Debugging bei Image-Problemen:

```bash
kubectl describe pod <pod-name>
```

Typische Fehler:

```text
ImagePullBackOff
ErrImagePull
unauthorized
manifest unknown
```

---

# Teil H: Versionierte Releases mit Git Tags

Bisher pusht der Workflow auf `main` automatisch `latest` und `sha-*`.

Für Releases verwendest du Git Tags:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Der Workflow erzeugt dann zusätzlich ein Image mit Tag:

```text
ghcr.io/<github-user>/mlops-kind-demo:v0.1.0
```

Deployment stabiler machen:

```yaml
image: ghcr.io/<github-user>/mlops-kind-demo:v0.1.0
```

Warum besser als `latest`?

```text
latest   → bewegliches Ziel, schwer reproduzierbar
v0.1.0   → konkrete Version
sha-*    → exakte Commit-Version
```

Für produktionsnahe Deployments solltest du nicht `latest` verwenden, sondern konkrete Versionen oder Commit-SHAs.

---

# Teil I: Empfohlene Workflow-Struktur

Für dieses Lernprojekt empfehle ich drei Workflows:

```text
ci.yaml
  → Linting und Tests

docker-build.yaml
  → Docker Build für Pull Requests und main

docker-publish.yaml
  → Docker Build + Push nach GHCR für main und Tags
```

Du kannst später `docker-build.yaml` entfernen, weil `docker-publish.yaml` auch baut. Für Lernzwecke ist die Trennung aber gut:

```text
CI beantwortet:
  Ist der Code korrekt?

Docker Build beantwortet:
  Kann das Image gebaut werden?

Docker Publish beantwortet:
  Kann das Image veröffentlicht werden?
```

---

# Teil J: Lokaler Entwicklungszyklus danach

Dein typischer Ablauf sieht jetzt so aus:

```bash
# Code ändern
git status

# Lokal testen
cd app
source .venv/bin/activate
pip install -e ".[dev]"
cd ..
pytest tests
ruff check app/src tests

# Lokal Image bauen
docker build -t ml-api:0.1.1 .

# Lokal in kind laden
kind load docker-image ml-api:0.1.1 --name mlops-demo

# Deployment lokal auf neue Version setzen
kubectl set image deployment/ml-api ml-api=ml-api:0.1.1
kubectl rollout status deployment/ml-api

# Commit und Push
git add .
git commit -m "Improve API"
git push
```

GitHub Actions läuft danach automatisch.

---

# Teil K: Zusammenhang mit kind

Es gibt zwei sinnvolle Wege:

## Variante 1: Lokales Image direkt in kind laden

```text
docker build -t ml-api:0.1.0 .
kind load docker-image ml-api:0.1.0 --name mlops-demo
kubectl apply -f k8s/
```

Vorteil:

```text
schnell
kein Registry-Login
sehr gut zum Lernen
```

Nachteil:

```text
funktioniert nur lokal
nicht reproduzierbar über andere Maschinen
```

## Variante 2: Image aus GHCR ziehen

```text
git push
GitHub Actions baut Image
GitHub Actions pusht nach GHCR
kind zieht Image aus GHCR
kubectl apply -f k8s/
```

Vorteil:

```text
realistischer
besser reproduzierbar
näher an OpenShift/Production
```

Nachteil:

```text
Registry-Zugriff nötig
bei privaten Images Pull Secret nötig
mehr bewegliche Teile
```

Für deinen Lernpfad:

```text
Zuerst Variante 1.
Danach Variante 2.
Dann OpenShift.
```

---

# Teil L: Commit-Stand sichern

Nachdem alle Workflows erstellt sind:

```bash
git status
git add .
git commit -m "Add GitHub Actions workflows"
git push
```

Danach prüfe auf GitHub:

```text
Repository
→ Actions
→ CI
→ Docker Build
→ Docker Publish
```

Alle Workflows sollten grün sein.

---

# Teil M: Häufige Fehler

## Fehler 1: `ModuleNotFoundError: No module named 'ml_api'`

Ursache:

```text
Paket wurde im Workflow nicht installiert
```

Lösung:

```yaml
- name: Install package
  run: |
    python -m pip install --upgrade pip
    pip install -e "app[dev]"
```

---

## Fehler 2: Docker Build findet `pyproject.toml` nicht

Prüfe, ob dein Dockerfile zum Projektlayout passt:

```dockerfile
COPY app/pyproject.toml ./pyproject.toml
COPY app/src ./src
```

Wenn dein Dockerfile im Root liegt und `app/` darunter liegt, ist das korrekt.

---

## Fehler 3: `denied: permission_denied` beim Push nach GHCR

Prüfe im Workflow:

```yaml
permissions:
  contents: read
  packages: write
```

Prüfe außerdem:

```yaml
password: ${{ secrets.GITHUB_TOKEN }}
```

Der `GITHUB_TOKEN` kann für GitHub Packages verwendet werden, ohne dass du einen eigenen PAT als Secret speichern musst. ([GitHub Docs][4])

---

## Fehler 4: kind kann GHCR Image nicht ziehen

Bei öffentlichem Image:

```bash
kubectl describe pod <pod-name>
```

Bei privatem Image:

```text
Pull Secret fehlt oder ist falsch.
```

Lösung:

```bash
kubectl create secret docker-registry ghcr-secret ...
```

und im Deployment:

```yaml
imagePullSecrets:
  - name: ghcr-secret
```

---

## Fehler 5: Workflow läuft nicht

Prüfe:

```text
Liegt die Datei unter .github/workflows/?
Endet die Datei auf .yaml oder .yml?
Ist YAML korrekt eingerückt?
Wurde auf den richtigen Branch gepusht?
Passt der Trigger?
```

Beispiel-Trigger:

```yaml
on:
  push:
    branches:
      - main
  pull_request:
```

---

# Teil N: Neuer Lernpfad

Mit GitHub und GitHub Actions sieht dein Lernpfad jetzt so aus:

```text
Phase 1: Lokale App
- FastAPI starten
- Endpunkte testen
- Tests schreiben

Phase 2: Container
- Dockerfile verstehen
- Image bauen
- Container starten

Phase 3: Kubernetes mit kind
- kind Cluster erstellen
- Image in kind laden
- Deployment, Service, ConfigMap, Secret anwenden
- Probes, Ressourcen, Rollout, HPA testen

Phase 4: GitHub Repository
- Git initialisieren
- Remote Repository verbinden
- README und .gitignore erstellen
- Code pushen

Phase 5: GitHub Actions CI
- Linting
- Tests
- Docker Build

Phase 6: Container Registry
- Image nach GHCR pushen
- Kubernetes Deployment auf GHCR Image umstellen
- Optional Pull Secret für private Images

Phase 7: OpenShift-Transfer
- kind Namespace → OpenShift Project
- Kubernetes Service/Ingress → OpenShift Service/Route
- GHCR Image → OpenShift Deployment
- GitHub Actions/GHCR → spätere CI/CD- oder GitOps-Basis
```

Die zentrale Lernidee bleibt:

```text
GitHub Repository ist die Source of Truth.
GitHub Actions prüft und baut automatisiert.
GHCR speichert das Container Image.
Kubernetes zieht und betreibt das Image.
```

Das ist die direkte Vorstufe zu einem OpenShift-Setup mit CI/CD oder GitOps.

[1]: https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions?utm_source=chatgpt.com "Workflow syntax for GitHub Actions"
[2]: https://docs.github.com/actions/guides/publishing-docker-images?utm_source=chatgpt.com "Publishing Docker images"
[3]: https://docs.github.com/packages/working-with-a-github-packages-registry/working-with-the-container-registry?utm_source=chatgpt.com "Working with the Container registry"
[4]: https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages?utm_source=chatgpt.com "About permissions for GitHub Packages"
[5]: https://docs.github.com/actions/concepts/security/github_token?utm_source=chatgpt.com "GITHUB_TOKEN"
[6]: https://github.com/docker/build-push-action?utm_source=chatgpt.com "GitHub Action to build and push Docker images with Buildx"
