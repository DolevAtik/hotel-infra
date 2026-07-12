<div align="center">

# 🏨 Hotel Platform — GitOps Infrastructure

**Declarative, self-healing delivery of a 3-tier microservices app to Kubernetes — powered by Argo CD & GitHub Actions.**

Every commit flows from `git push` to a running Pod with **zero manual `kubectl apply`**. Git is the single source of truth; the cluster continuously reconciles itself to match it.

<br/>

![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)
![Argo CD](https://img.shields.io/badge/Argo%20CD-EF7B4D?style=for-the-badge&logo=argo&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Kustomize](https://img.shields.io/badge/Kustomize-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)

![Python](https://img.shields.io/badge/Flask%20%2B%20Gunicorn-000000?style=for-the-badge&logo=flask&logoColor=white)
![React](https://img.shields.io/badge/React%20SPA-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![NGINX](https://img.shields.io/badge/NGINX%20Ingress-009639?style=for-the-badge&logo=nginx&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)

</div>

---

## 📌 What this project demonstrates

This repository is the **infrastructure & delivery layer** for a hotel-booking application. It is deliberately built to showcase production-minded DevOps practices end to end:

- **GitOps with Argo CD** — the cluster's desired state lives in Git; Argo CD reconciles automatically with `selfHeal` (drift correction) and `prune` (garbage collection).
- **Fully automated CI/CD** — application repos build, test, push immutable images, and open a Pull Request against *this* repo. Merge = deploy.
- **Immutable, traceable image tags** — every image is tagged with the **Git commit SHA**, so any running Pod is traceable back to an exact source commit (`:latest` kept only for convenience).
- **Declarative Kubernetes with Kustomize** — one `kustomization.yaml` composes the whole stack; a single Argo CD `Application` owns it.
- **12-Factor runtime configuration** — the frontend image is built once and configured **at runtime** via a mounted `config.js` (ConfigMap), so the same artifact ships to every environment.
- **Operational hygiene** — readiness/liveness probes, CPU/memory requests & limits, a persistent volume for stateful data, and an **idempotent** database seed Job.
- **Single-origin ingress** — one host serves the SPA and proxies the API under `/api`, eliminating CORS and simplifying the browser's trust model.

---

## 🏗️ Architecture

### Runtime topology (inside the cluster)

```mermaid
flowchart TD
    User([Browser]) -->|hotel.local| ING[NGINX Ingress]

    ING -->|"/"| FE["frontend: React SPA + NGINX<br/>5 replicas - port 80"]
    ING -->|"/api -> rewrite"| BE["backend: Flask + Gunicorn<br/>port 3000"]

    BE --> DB[("mongodb<br/>mongo:7.0 - port 27017")]
    DB --- PVC[("PersistentVolume<br/>/data/db")]

    SEED["seed Job<br/>idempotent"] -.->|"waits for + seeds"| DB
    CM["ConfigMap<br/>config.js"] -.->|runtime API base| FE
    SEC["Secret<br/>mongodb-secret"] -.->|MONGO_URI| BE

    classDef svc fill:#326CE5,stroke:#1b3a7a,color:#fff;
    classDef data fill:#47A248,stroke:#2d6a2f,color:#fff;
    class FE,BE svc;
    class DB,PVC data;
```

| Component | Role | Tech | Port | Exposure | Notes |
|-----------|------|------|------|----------|-------|
| **frontend** | User interface | React SPA served by NGINX | 80 | ClusterIP | 5 replicas · runtime config via ConfigMap · probes · resource limits |
| **backend** | REST API | Python 3.12 · Flask · Gunicorn | 3000 | ClusterIP | `/health` probes · `MONGO_URI` from Secret · resource limits |
| **mongodb** | Database | mongo:7.0 | 27017 | ClusterIP | Backed by a PVC to survive Pod restarts |
| **seed** | Data bootstrap | mongo:7.0 (`mongosh`) | — | Job | Waits for DB, then seeds hotels idempotently |
| **ingress** | Edge routing | NGINX Ingress | — | LB/Host | `/` → frontend, `/api(/\|$)(.*)` → `backend:3000` with prefix rewrite |

> The browser only ever talks to **one origin**. `/` serves the SPA; `/api/hotels` is rewritten to `/hotels` on `backend:3000`. Two `Ingress` objects are used intentionally so the API rewrite annotation is isolated from the SPA path.

---

## 🔄 The GitOps delivery pipeline

The core of the project. A developer never touches the cluster — they just push code.

```mermaid
flowchart LR
    DEV([git push - app repo dev]) --> GHA

    subgraph CI["GitHub Actions - app repo"]
        GHA["Build & Test"] --> IMG["Build image<br/>tag = git SHA"]
        IMG --> HUB[(Docker Hub)]
        HUB --> PR[Open PR to<br/>hotel-infra]
    end

    PR --> MERGE([Merge PR to main])

    subgraph CD["Argo CD (in-cluster)"]
        MERGE --> SYNC[Detect drift<br/>OutOfSync]
        SYNC --> APPLY["Auto-sync<br/>selfHeal + prune"]
    end

    APPLY --> K8S([Kubernetes<br/>rolling update])
```

**How it works, step by step:**

1. A developer pushes to `dev` in an **application** repo (`hotel-backend` / `hotel-frontend`).
2. **GitHub Actions** builds the app, runs a smoke test, and builds a Docker image tagged with the **commit SHA** (+ `:latest`), pushing both to **Docker Hub**.
3. A second job checks out **this repo** and bumps the image tag in `k8s/<component>/deployment.yaml`, then opens a **Pull Request** (`peter-evans/create-pull-request`).
4. A human **reviews and merges** the PR into `main` — the only manual gate, and the audit trail.
5. **Argo CD** (tracking `main`, path `k8s`) detects the change, shows `OutOfSync`, and **auto-syncs**.
6. Kubernetes performs a **rolling update**; Argo CD reports `Synced / Healthy`.

> ✅ **Validated end-to-end.** A backend commit was traced from `git push` all the way to the live Deployment image flipping from `:3` to its full commit SHA, with Argo CD reconciling automatically — no manual `kubectl` in the path.

---

## 📂 Repository structure

```
hotel-infra
├── argocd/
│   └── hotel-app.yaml          # Single Argo CD Application → path k8s/ (owns the whole stack)
├── k8s/
│   ├── kustomization.yaml      # Composes every manifest below
│   ├── namespace.yaml          # namespace: hotel
│   ├── mongodb/                # Secret + PVC + Deployment + Service
│   ├── backend/                # Deployment + Service (ClusterIP :3000)
│   ├── frontend/               # Deployment + Service + ConfigMap (config.js) + Ingress (/, /api)
│   └── seed/                   # Idempotent seed Job + ConfigMap (seed script)
├── scripts/
│   ├── seed_hotels.js          # Source of truth for demo hotel data
│   └── smoke_test.py           # Backend ↔ MongoDB smoke test
├── docs/
│   └── VALIDATION.md           # End-to-end test & validation report (incident log + raw output)
├── docker-compose.yml          # Full local stack (adds mongo-express)
├── .env.example                # Environment template
└── README.md
```

---

## 🚀 Deploy via Argo CD (GitOps — recommended)

A **single** Argo CD `Application` owns the entire stack (namespace, DB, backend, frontend, seed) via Kustomize:

```bash
kubectl apply -f argocd/hotel-app.yaml
```

```yaml
# argocd/hotel-app.yaml (excerpt)
source:
  repoURL: https://github.com/DolevAtik/hotel-infra.git
  targetRevision: main
  path: k8s
syncPolicy:
  automated:
    prune: true       # delete resources removed from Git
    selfHeal: true    # revert manual cluster drift back to Git
  syncOptions:
    - CreateNamespace=true
```

From here on, **Git is the deploy button** — merge to `main` and the cluster follows.

---

## ⚙️ Deploy manually with Kustomize (no Argo CD)

The same manifests apply directly, in dependency order (namespace → storage/secret → workloads → seed):

```bash
kubectl apply -k k8s/
```

---

## 💻 Run locally (Docker Compose)

Great for developing without a cluster. Copy `.env.example` → `.env` and fill in credentials:

```env
MONGO_ROOT_USERNAME=admin
MONGO_ROOT_PASSWORD=change-me
ME_USERNAME=admin
ME_PASSWORD=change-me
```

```bash
docker compose up -d --build
```

| Service        | URL                          |
|----------------|------------------------------|
| Frontend       | http://localhost:8080        |
| Backend API    | http://localhost:3000        |
| mongo-express  | http://localhost:8081        |
| MongoDB        | mongodb://localhost:27017    |

```bash
docker compose down       # stop, keep data
docker compose down -v    # stop, wipe the data volume
```

---

## ✅ Verify a deployment

```bash
# Argo CD application health & sync state
kubectl get applications -n argocd
# → hotel   Synced   Healthy

# Everything in the app namespace
kubectl get all -n hotel

# Prove the running image matches the merged commit SHA
kubectl get deployment backend -n hotel \
  -o=jsonpath="{.spec.template.spec.containers[0].image}"
# → dolevatik/hotel-backend:<git-sha>

# Seed Job output (inserted / already-exists + total)
kubectl logs -n hotel job/hotel-seed
```

> 📄 A full, reproducible validation run — the nine checks above with **real output**, plus an honest **incident log** of the failures hit and fixed along the way — is documented in **[docs/VALIDATION.md](docs/VALIDATION.md)**.

---

## 🔒 Security notes

- `k8s/mongodb/secret.yaml` ships **sample credentials only**. Replace them and never commit real secrets — use [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) or [External Secrets Operator](https://external-secrets.io/) for production.
- Docker Hub and GitHub credentials (`DOCKER_USERNAME`, `DOCKER_PASSWORD`, `PAT`) live in **GitHub Actions secrets**, never in the repo.
- Merging to `main` is the intentional human gate on every deploy — the change history is the audit log.

---

## 🗺️ Roadmap

Honest next steps toward a production-grade platform:

- [ ] **Sealed Secrets / External Secrets** to remove plaintext credentials from Git
- [ ] **Observability** — Prometheus + Grafana dashboards and alerting
- [ ] **Progressive delivery** — Argo Rollouts (canary / blue-green) instead of rolling updates
- [ ] **App-of-Apps** pattern to scale to multiple environments (dev / staging / prod)
- [ ] **Policy & supply chain** — image scanning (Trivy) and admission policy (Kyverno/OPA)
- [ ] **TLS** at the ingress via cert-manager + Let's Encrypt

---

<div align="center">

**Built by [Dolev Atik](https://github.com/DolevAtik)** · DevOps Engineer

*Companion application repos: [`hotel-backend`](https://github.com/DolevAtik/hotel-backend) · [`hotel-frontend`](https://github.com/DolevAtik/hotel-frontend)*

</div>
