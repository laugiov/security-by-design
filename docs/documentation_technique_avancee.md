# Documentation technique

---

## 1. Vue d'Ensemble

### 1.1 Contexte et Objectifs

SkyLink est une plateforme de services pour vehicules connectes implementee selon les principes **Security by Design** et **Contract-First**. L'architecture microservices permet la scalabilite horizontale et l'isolation des domaines metier.

**Objectifs cles** :
- Collecter et traiter les donnees de telemetrie vehicule en temps reel
- Fournir des services meteo contextualises pour l'aide a la conduite
- Gerer les contacts d'urgence avec integration OAuth Google
- Garantir la securite des donnees (PII minimization, chiffrement, auditabilite)

### 1.2 Architecture Globale

```
                              Internet
                                 |
                    [Reverse Proxy / Load Balancer]
                                 |
                                 v
+-----------------------------------------------------------------------+
|                           API GATEWAY (:8000)                          |
|  +------------------+  +-------------------+  +--------------------+   |
|  | Security Headers |  | Rate Limiting     |  | JWT RS256 Auth     |   |
|  | (OWASP)          |  | (60 req/min/sub)  |  | (sign + verify)    |   |
|  +------------------+  +-------------------+  +--------------------+   |
|  +------------------+  +-------------------+  +--------------------+   |
|  | Payload Limit    |  | JSON Logging      |  | mTLS Extraction    |   |
|  | (64 KB max)      |  | (trace_id W3C)    |  | (CN validation)    |   |
|  +------------------+  +-------------------+  +--------------------+   |
+-----------------------------------------------------------------------+
         |                      |                      |
         v                      v                      v
+----------------+    +------------------+    +------------------+
| TELEMETRY      |    | WEATHER          |    | CONTACTS         |
| Service        |    | Service          |    | Service          |
| :8001          |    | :8002            |    | :8003            |
+----------------+    +------------------+    +------------------+
| - Idempotence  |    | - Mode demo      |    | - OAuth Google   |
| - GPS rounding |    | - Fixtures Paris |    | - PostgreSQL     |
| - 201/200/409  |    | - Cache ready    |    | - CRUD contacts  |
+----------------+    +------------------+    +------------------+
                                                    |
                                                    v
                                            +----------------+
                                            | PostgreSQL     |
                                            | :5432          |
                                            +----------------+
```

---

## 2. Composants et Responsabilites

### 2.1 API Gateway (Port 8000)

Point d'entree unique de la plateforme. Centralise l'authentification, la validation et le routage.

| Composant | Responsabilite | Implementation |
|-----------|----------------|----------------|
| **Auth JWT RS256** | Emission et verification tokens | PyJWT, cles RSA 2048 bits |
| **Rate Limiting** | Protection contre les abus | slowapi, 60 req/min par vehicle_id |
| **Security Headers** | Protection OWASP | X-Content-Type-Options, X-Frame-Options, CSP |
| **Payload Limit** | Protection DoS | 64 KB max par requete |
| **JSON Logging** | Observabilite | Logs structures, trace_id W3C |
| **mTLS** | Auth mutuelle (optionnel) | Cross-validation CN <-> JWT sub |
| **Prometheus /metrics** | Metriques | prometheus-fastapi-instrumentator |

### 2.2 Service Telemetry (Port 8001)

Collecte et stockage des donnees de telemetrie vehicule avec garantie d'idempotence.

| Fonctionnalite | Description | Code HTTP |
|----------------|-------------|-----------|
| Creation evenement | Nouvel event_id | 201 Created |
| Doublon exact | Meme (vehicle_id, event_id) | 200 OK |
| Conflit | event_id reutilise, donnees differentes | 409 Conflict |

**Minimisation PII** : Coordonnees GPS arrondies a 4 decimales (~11m de precision).

### 2.3 Service Weather (Port 8002)

Service meteo pour l'aide a la conduite. Mode demo avec fixtures Paris.

**Endpoints** :
- `GET /weather/current` : Conditions actuelles

### 2.4 Service Contacts (Port 8003)

Gestion des contacts d'urgence avec authentification OAuth Google.

**Caracteristiques** :
- Integration Google OAuth 2.0
- Stockage PostgreSQL
- CRUD complet des contacts

---

## 3. Securite (Security by Design)

### 3.1 Authentification Multi-Niveaux

```
Niveau 1: Transport (mTLS)
+---------------------------+
| Certificat client X.509   |
| Signe par CA SkyLink    |
| CN = vehicle_id           |
+---------------------------+
            |
            v
Niveau 2: Application (JWT RS256)
+---------------------------+
| Token JWT signe RS256     |
| sub = vehicle_id          |
| exp = 15 minutes max      |
| aud = "skylink"         |
+---------------------------+
            |
            v
Niveau 3: Cross-Validation
+---------------------------+
| CN certificat == sub JWT  |
| Verification automatique  |
+---------------------------+
```

### 3.2 Protection des Donnees (PII)

| Mesure | Implementation | Justification |
|--------|----------------|---------------|
| GPS Rounding | 4 decimales (~11m) | Anonymisation position |
| Payload Limit | 64 KB max | Protection DoS |
| Logs sans PII | trace_id uniquement | RGPD compliance |
| Schemas stricts | `additionalProperties: false` | Injection prevention |
| Pydantic strict | `extra: "forbid"` | Rejet champs inconnus |

### 3.3 Rate Limiting

```
Configuration slowapi:
- Par vehicle_id : 60 requetes/minute
- Global : 10 requetes/seconde
- Response : 429 Too Many Requests
- Counter Prometheus : rate_limit_exceeded_total
```

### 3.4 Headers de Securite (OWASP)

| Header | Valeur | Protection |
|--------|--------|------------|
| X-Content-Type-Options | nosniff | MIME sniffing |
| X-Frame-Options | DENY | Clickjacking |
| Cache-Control | no-store, no-cache | Cache poisoning |
| Cross-Origin-Opener-Policy | same-origin | Spectre/Meltdown |
| Cross-Origin-Embedder-Policy | require-corp | Isolation |
| Referrer-Policy | no-referrer | Fuite referrer |
| Permissions-Policy | geolocation=(), camera=() | API restrictions |

---

## 4. Infrastructure et Deploiement

### 4.1 Stack Docker

```yaml
# docker-compose.yml (resume)
services:
  gateway:      # python:3.12-slim, port 8000
  telemetry:    # python:3.12-slim, port 8001
  weather:      # python:3.12-slim, port 8002
  contacts:     # python:3.12-slim, port 8003
  db:           # postgres:16-alpine, port 5432
```

**Caracteristiques Dockerfiles** :
- Multi-stage build (builder + runtime)
- Image de base : `python:3.12-slim`
- User non-root : `skylink:1000`
- Health checks integres
- Variables d'environnement securisees

### 4.2 Makefile

| Commande | Description |
|----------|-------------|
| `make build` | Construit toutes les images |
| `make up` | Demarre la stack |
| `make down` | Arrete la stack |
| `make logs` | Affiche les logs (follow) |
| `make health` | Verifie sante des services |
| `make test` | Lance les tests |
| `make clean` | Supprime containers/images |

### 4.3 Reseau Docker

```
skylink-net (bridge)
+-----------------------------------------------+
|                                               |
|  gateway:8000  <----> telemetry:8001          |
|       |        <----> weather:8002            |
|       |        <----> contacts:8003 --> db    |
|       |                                       |
+-----------------------------------------------+
        |
        | Port expose : 8000
        v
    Internet
```

---

## 5. Pipeline CI/CD

### 5.1 Stages GitLab CI

```
lint ──> test ──> build ──> scan ──> sbom ──> security-scan ──> sign
```

| Stage | Outils | Objectif |
|-------|--------|----------|
| **lint** | ruff, black, bandit | Qualite code, securite statique |
| **test** | pytest, coverage | Tests unitaires (307 tests, 81% coverage) |
| **build** | kaniko | Construction images (rootless) |
| **scan** | trivy, pip-audit, gitleaks | Vulnerabilites images, SCA, secrets |
| **sbom** | cyclonedx-bom | Nomenclature composants (CycloneDX) |
| **security-scan** | ZAP baseline | Tests securite dynamiques (DAST) |
| **sign** | cosign | Signature images + attestation SBOM |

### 5.2 Supply Chain Security (cosign)

La signature d'images garantit l'integrite et la provenance du code deploye.

```
Pipeline de signature:

build_image ──> trivy_image ──> sign_image ──> attest_sbom ──> verify_signature
     │                              │              │                │
     v                              v              v                v
  Image Docker              Signature cosign   SBOM attache    Verification
  registry:tag              .sig dans registry  in-toto pred.   cle publique
```

**Jobs de signature** :

| Job | Description | Declencheur |
|-----|-------------|-------------|
| `sign_image` | Signe l'image avec cle privee cosign | master, tags |
| `attest_sbom` | Attache le SBOM CycloneDX comme attestation | master, tags |
| `verify_signature` | Verifie signature et attestation | master, tags |

**Verification manuelle** :

```bash
# Verifier la signature d'une image
cosign verify --key cosign.pub registry.gitlab.com/skylink:latest

# Verifier l'attestation SBOM
cosign verify-attestation --key cosign.pub --type cyclonedx registry.gitlab.com/skylink:latest
```

### 5.3 Variables CI Securisees

| Variable | Type | Protected | Usage |
|----------|------|-----------|-------|
| PRIVATE_KEY_PEM | Variable | Oui | Signature JWT |
| PUBLIC_KEY_PEM | Variable | Oui | Verification JWT |
| COSIGN_PRIVATE_KEY | **File** | Oui + Masked | Signature images Docker |
| COSIGN_PASSWORD | Variable | Oui + Masked | Mot de passe cle cosign |
| COSIGN_PUBLIC_KEY | **File** | Oui | Verification signatures |

> **Note importante** : Les variables `COSIGN_PRIVATE_KEY` et `COSIGN_PUBLIC_KEY` doivent etre de type **File** (et non Variable) pour que cosign puisse lire le fichier PEM correctement.

---

## 6. Observabilite

### 6.1 Metriques Prometheus

Endpoint : `GET /metrics`

| Metrique | Type | Description |
|----------|------|-------------|
| http_requests_total | Counter | Requetes par handler/method/status |
| http_request_duration_seconds | Histogram | Latences (buckets) |
| http_requests_inprogress | Gauge | Requetes en cours |
| rate_limit_exceeded_total | Counter | Rate limits declenches (429) |

### 6.2 Logging Structure

```json
{
  "timestamp": "2025-12-19T10:00:00.000Z",
  "service": "gateway",
  "trace_id": "abc-123-def",
  "method": "POST",
  "path": "/telemetry",
  "status": 201,
  "duration_ms": 12.5
}
```

**Caracteristiques** :
- Format JSON sur stdout
- Tracabilite W3C (trace_id)
- Pas de PII dans les logs
- Compatible ELK/CloudWatch

---

## 7. Conformite RRA (Rapid Risk Assessment)

Cette section detaille la conformite du projet par rapport aux recommandations du document **SkyLink-RRA.pdf** (Fast Car Connect Risk Assessment).

### 7.1 Recommandations RRA et Implementation

| Impact | Recommandation RRA | Status | Implementation |
|--------|-------------------|--------|----------------|
| **MAXIMUM** | Utiliser mTLS pour l'identification vehicule-service | ✅ Fait | Module `skylink/mtls.py`, scripts PKI dans `scripts/`, cross-validation CN <-> JWT |
| **MAXIMUM** | Utiliser OAuth avec moindres privileges | ✅ Fait | Service Contacts avec Google OAuth 2.0, scope `read-only` pour contacts |
| **MAXIMUM** | Gerer les secrets avec KMS/Vault | ✅ MVP | Variables CI protegees + `.env` local (voir note 7.6) |
| **HIGH** | Minimisation des donnees (Geohash localisation) | ✅ Fait | GPS arrondi 4 decimales (~11m), pas de persistance contacts par defaut |
| **HIGH** | Securisation API (JWT + rate limiting) | ✅ Fait | JWT RS256 (15min exp), slowapi 60 req/min par vehicle_id |
| **HIGH** | Logs sans PII, tracage, metriques | ✅ Fait | JSON logging avec trace_id, `/metrics` Prometheus, logs sans PII |
| **HIGH** | Supply chain CI/CD (SBOM, SCA, SAST/DAST) | ✅ Fait | Pipeline GitLab: bandit, trivy, cyclonedx-bom, ZAP DAST |

### 7.2 Scenarios de Menace et Controles

| Scenario (RRA) | Impact | Controle Implemente | Preuve |
|----------------|--------|---------------------|--------|
| **Fuites de donnees** (tokens OAuth, GPS, logs bavards) | MAXIMUM | Logs sans PII, schemas stricts, variables CI protegees | Tests validation, .gitignore |
| **Alteration systeme conduite** | MAXIMUM | mTLS obligatoire, JWT signe RS256, validation stricte | Tests auth, tests mTLS |
| **Spoofing vehicule** (absence mTLS) | HIGH | mTLS avec cross-validation CN == JWT sub | Tests `test_mtls_auth_integration.py` |
| **Replay attacks** (absence nonce) | MEDIUM | Idempotence `(vehicle_id, event_id)` unique | Tests 201/200/409 |
| **Supply-chain** (image/dependance compromise) | MAXIMUM | SBOM CycloneDX, Trivy scan, Bandit SAST | Artefacts CI pipeline |
| **DDoS/API flood** | HIGH | Rate-limit slowapi, reponse 429 | Tests rate-limit, metrique `rate_limit_exceeded_total` |
| **Quota/Outage vendors** | MEDIUM | Mode demo fixtures (Weather), circuit-breaker cible | Service Weather mode demo |
| **Incidents CI/CD** | MAXIMUM | Pipeline multi-stage, tests automatises, health checks | 307 tests, 81% coverage |

### 7.3 Dictionnaire de Donnees et Protection

| Donnee (RRA) | Classification | Controle Implemente |
|--------------|----------------|---------------------|
| UUID vehicule | Interne | Validation UUID strict (Pydantic) |
| Telemetrie (vitesse, carburant, etc.) | Confidentiel | Schemas `additionalProperties: false`, logs sans donnees |
| Position GPS | Confidentiel (PII) | **Arrondi 4 decimales** (~11m precision) |
| Contacts Google | Confidentiel (PII) | OAuth read-only, pas de persistance par defaut |
| Tokens auth Google | Restreint | Variables CI protegees, stockage PostgreSQL securise |
| Logs (requetes, metriques) | Restreint | **Logs JSON sans PII**, trace_id uniquement |
| Metadonnees reseau | Interne | Non loggees (pas d'IP/user-agent dans logs) |

### 7.4 Matrice Risques et Preuves

| Risque (RRA) | Controle | Fichier/Test | Status |
|--------------|----------|--------------|--------|
| Flood API / DDoS | Rate-limit slowapi (429) | `tests/test_rate_limit.py` | ✅ |
| Replay / doublons | Idempotence (vehicle_id, event_id) | `tests/test_telemetry.py` (201/200/409) | ✅ |
| Exposition PII | Schemas stricts + logs sans PII | `tests/test_middlewares.py` | ✅ |
| Dependances vulnerables | SCA/SAST + SBOM | `.gitlab-ci.yml` (trivy, bandit, sbom) | ✅ |
| Secrets en clair | Vars CI protegees/masquees | GitLab Settings CI/CD | ✅ |
| Usurpation vehicule | mTLS + cross-validation CN<->JWT | `tests/test_mtls*.py` | ✅ |
| Injection / XSS | Schemas stricts + Pydantic | `tests/test_error_handlers.py` | ✅ |

### 7.5 Elements Cibles (Non MVP)

| Element RRA | Status MVP | Cible Production |
|-------------|------------|------------------|
| HSM pour cles vehicules | Non implemente | HSM materiel + PKI automatisee |
| SIEM centralise | Logs stdout | ELK Stack / Splunk |
| Attestation SLSA >= L3 | SBOM genere | cosign + attestation provenance |
| Circuit-breaker vendors | Mode demo | Resilience4j / Hystrix pattern |

### 7.6 Note sur la Gestion des Secrets (MVP)

**Contexte RRA** : La recommandation "Gerer les secrets avec KMS/Vault" vise a proteger les secrets cryptographiques (cles RSA, tokens OAuth) contre les fuites et acces non autorises.

**Implementation MVP** :

| Environnement | Mecanisme | Securite |
|---------------|-----------|----------|
| **Developpement local** | Fichier `.env` | `.env` dans `.gitignore`, jamais commite |
| **CI/CD GitLab** | Variables protegees | Protected + scope branches protegees |
| **Docker Compose** | Variables d'environnement | Injectees au runtime, pas dans les images |

**Controles en place** :

1. **Pas de secrets hardcodes** : Aucun secret dans le code source
   ```python
   # skylink/config.py
   private_key_pem: Optional[str] = None  # Charge depuis env
   ```

2. **`.gitignore` strict** :
   ```
   .env
   *.pem
   certs/
   ```

3. **Variables CI protegees** :
   - `PRIVATE_KEY_PEM` : Protected, accessible uniquement sur branches protegees
   - `PUBLIC_KEY_PEM` : Protected, accessible uniquement sur branches protegees

4. **Rotation possible** : Les cles peuvent etre changees sans modification du code

**Justification MVP** :

Cette approche est conforme aux **12-Factor App** (Config in Environment) et suffisante pour un MVP car :
- Les secrets ne sont jamais exposes dans les logs ou le code
- L'acces CI est restreint aux branches protegees
- Le mecanisme est identique a celui utilise avec un Vault (variables d'environnement)

**Evolution Production** :

Pour la production, l'architecture permet une migration transparente vers HashiCorp Vault :
- Modifier uniquement `skylink/config.py` pour lire depuis Vault API
- Aucun changement dans le reste du code (meme interface `settings.get_private_key()`)

---

## 8. Specifications Techniques

### 8.1 Stack Technologique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Langage | Python | 3.12 |
| Framework | FastAPI | ^0.115 |
| ASGI Server | Uvicorn | ^0.32 |
| JWT | PyJWT | ^2.10 |
| Validation | Pydantic | ^2.10 |
| Rate Limiting | slowapi | ^0.1.9 |
| Metriques | prometheus-fastapi-instrumentator | ^7.0 |
| Base de donnees | PostgreSQL | 16 |
| Conteneurs | Docker | 24+ |
| CI/CD | GitLab CI | - |

### 8.2 Contract-First (OpenAPI)

Specifications dans `openapi/*.yaml` :
- `common.yaml` : Schemas partages (Error, Pagination)
- `gateway.yaml` : API Gateway
- `telemetry.yaml` : Service Telemetry
- `weather.yaml` : Service Weather
- `contacts.yaml` : Service Contacts

**Validation** :
- Schemas avec `additionalProperties: false`
- Pydantic avec `extra: "forbid"`
- CI lint OpenAPI (openapi-generator-cli)

---

## 9. Annexes

### 9.1 Structure du Projet

```
SkyLink/
|-- openapi/                 # Specifications OpenAPI
|-- skylink/               # Gateway (port 8000)
|   |-- main.py              # Application FastAPI
|   |-- auth.py              # JWT RS256
|   |-- mtls.py              # mTLS configuration
|   |-- middlewares.py       # Security, logging
|   |-- rate_limit.py        # Rate limiting
|   |-- config.py            # Configuration
|   |-- routers/             # Endpoints
|   +-- models/              # Pydantic models
|-- telemetry/               # Service Telemetry (port 8001)
|-- weather/                 # Service Weather (port 8002)
|-- contacts/                # Service Contacts (port 8003)
|-- scripts/                 # Scripts PKI
|-- tests/                   # Tests (307 tests)
|-- docs/                    # Documentation
|-- Dockerfile.gateway       # Image Gateway
|-- Dockerfile.telemetry     # Image Telemetry
|-- Dockerfile.weather       # Image Weather
|-- Dockerfile.contacts      # Image Contacts
|-- docker-compose.yml       # Orchestration
|-- Makefile                 # Commandes utilitaires
|-- pyproject.toml           # Dependencies Python
+-- .gitlab-ci.yml           # Pipeline CI/CD
```

### 9.2 Endpoints API

| Methode | Endpoint | Service | Description |
|---------|----------|---------|-------------|
| GET | / | Gateway | Entrypoint API |
| GET | /health | Gateway | Health check |
| GET | /metrics | Gateway | Prometheus metrics |
| POST | /auth/token | Gateway | Obtention JWT |
| POST | /telemetry/ingest | Gateway | Ingestion telemetrie (proxy → Telemetry) |
| GET | /telemetry/health | Telemetry | Health check |
| GET | /weather/current | Gateway | Meteo actuelle |
| GET | /contacts/ | Gateway | Liste contacts |
| GET | /contacts/health | Contacts | Health check |

### 9.3 Codes HTTP Standards

| Code | Signification | Usage |
|------|---------------|-------|
| 200 | OK | Succes, doublon idempotent |
| 201 | Created | Ressource creee |
| 400 | Bad Request | Validation echouee |
| 401 | Unauthorized | JWT invalide/expire |
| 403 | Forbidden | mTLS CN != JWT sub |
| 409 | Conflict | Idempotence violee |
| 422 | Unprocessable | Schema invalide |
| 429 | Too Many Requests | Rate limit |
| 500 | Internal Error | Erreur serveur |

---

