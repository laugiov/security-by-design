# Guide de Demonstration SkyLink

> **Duree estimee** : 10-15 minutes
> **Prerequis** : Docker, curl, jq (optionnel)

---

## Preparation

### 1. Cloner et Configurer

```bash
# Cloner le projet
git clone <repo-url> SkyLink
cd SkyLink

# Copier le template d'environnement
cp .env.example .env

# Generer les cles RSA (si pas deja fait)
openssl genrsa -out /tmp/private.pem 2048
openssl rsa -in /tmp/private.pem -pubout -out /tmp/public.pem

# Ajouter les cles au .env
echo "PRIVATE_KEY_PEM=\"$(cat /tmp/private.pem)\"" >> .env
echo "PUBLIC_KEY_PEM=\"$(cat /tmp/public.pem)\"" >> .env
```

### 2. Demarrer la Stack

```bash
# Construire et demarrer (premiere fois)
make build && make up

# Ou simplement
docker compose up -d

# Verifier que tout est UP
make status
```

**Resultat attendu** :
```
NAME          STATUS    PORTS
gateway       Up        0.0.0.0:8000->8000/tcp
telemetry     Up        8001/tcp
weather       Up        8002/tcp
contacts      Up        8003/tcp
db            Up        5432/tcp
```

### 3. Verifier la Sante

```bash
make health
```

**Resultat attendu** :
```
Gateway:    healthy
Telemetry:  healthy
Weather:    healthy
Contacts:   healthy
PostgreSQL: UP
```

---

## Demo 1 : Authentification JWT

### Etape 1.1 : Obtenir un Token

```bash
# Generer un UUID pour le vehicule
VEHICLE_ID=$(uuidgen || echo "550e8400-e29b-41d4-a716-446655440000")

# Obtenir un token JWT
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"vehicle_id\": \"$VEHICLE_ID\"}" | jq
```

**Resultat attendu** :
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

### Etape 1.2 : Sauvegarder le Token

```bash
# Extraire et sauvegarder le token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"vehicle_id\": \"$VEHICLE_ID\"}" | jq -r '.access_token')

echo "Token obtenu : ${TOKEN:0:50}..."
```

### Etape 1.3 : Decoder le Token (Debug)

```bash
# Decoder le payload (base64)
echo $TOKEN | cut -d'.' -f2 | base64 -d 2>/dev/null | jq
```

**Resultat attendu** :
```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "aud": "skylink",
  "iat": 1734600000,
  "exp": 1734600900
}
```

---

## Demo 2 : Telemetrie avec Idempotence

### Etape 2.1 : Envoyer un Evenement (201 Created)

```bash
EVENT_ID=$(uuidgen)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

curl -s -X POST http://localhost:8000/telemetry/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"vehicle_id\": \"$VEHICLE_ID\",
    \"event_id\": \"$EVENT_ID\",
    \"ts\": \"$TS\",
    \"metrics\": {
      \"speed\": 45.5,
      \"gps\": {\"lat\": 48.8566, \"lon\": 2.3522}
    }
  }" -w "\nHTTP Status: %{http_code}\n"
```

**Resultat attendu** :
```json
{
  "status": "created",
  "event_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
HTTP Status: 201
```

### Etape 2.2 : Renvoyer le Meme Evenement (200 OK - Idempotence)

```bash
# Meme requete = meme resultat (idempotence)
curl -s -X POST http://localhost:8000/telemetry/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"vehicle_id\": \"$VEHICLE_ID\",
    \"event_id\": \"$EVENT_ID\",
    \"ts\": \"$TS\",
    \"metrics\": {
      \"speed\": 45.5,
      \"gps\": {\"lat\": 48.8566, \"lon\": 2.3522}
    }
  }" -w "\nHTTP Status: %{http_code}\n"
```

**Resultat attendu** :
```json
{
  "status": "duplicate",
  "event_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
HTTP Status: 200
```

### Etape 2.3 : Conflit d'Idempotence (409 Conflict)

```bash
# Meme event_id mais donnees differentes = conflit
curl -s -X POST http://localhost:8000/telemetry/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"vehicle_id\": \"$VEHICLE_ID\",
    \"event_id\": \"$EVENT_ID\",
    \"ts\": \"$TS\",
    \"metrics\": {
      \"speed\": 120.0,
      \"gps\": {\"lat\": 48.8566, \"lon\": 2.3522}
    }
  }" -w "\nHTTP Status: %{http_code}\n"
```

**Resultat attendu** :
```json
{
  "detail": {
    "code": "TELEMETRY_CONFLICT",
    "message": "Event with same event_id but different payload already exists."
  }
}
HTTP Status: 409
```

---

## Demo 3 : Rate Limiting

> **Note** : Le rate limiting est configure sur `/weather/current` (60 req/min par vehicle_id).

### Etape 3.1 : Generer un Burst de Requetes

```bash
# Envoyer 70 requetes rapidement (limite = 60/min)
for i in $(seq 1 70); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://localhost:8000/weather/current?lat=48.8566&lon=2.3522" \
    -H "Authorization: Bearer $TOKEN")

  if [ "$STATUS" = "429" ]; then
    echo "Rate limit atteint a la requete $i (HTTP 429)"
    break
  fi

  # Afficher progression
  if [ $i -le 5 ] || [ $i -ge 58 ]; then
    echo "Request $i: HTTP $STATUS"
  elif [ $i -eq 6 ]; then
    echo "..."
  fi
done
```

**Resultat attendu** :
```
Request 1: HTTP 200
Request 2: HTTP 200
...
Request 58: HTTP 200
Request 59: HTTP 200
Request 60: HTTP 200
Rate limit atteint a la requete 61 (HTTP 429)
```

### Etape 3.2 : Verifier la Reponse 429

```bash
# La prochaine requete devrait etre limitee
curl -s "http://localhost:8000/weather/current?lat=48.8566&lon=2.3522" \
  -H "Authorization: Bearer $TOKEN" -w "\nHTTP Status: %{http_code}\n"
```

**Resultat attendu** :
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded: 60 per 1 minute"
  }
}
HTTP Status: 429
```

---

## Demo 4 : Metriques Prometheus

### Etape 4.1 : Acceder aux Metriques

```bash
curl -s http://localhost:8000/metrics | grep -E "^(http_|rate_)" | head -20
```

**Resultat attendu** :
```
# HELP http_requests_total Total number of requests by method, status and handler.
# TYPE http_requests_total counter
http_requests_total{handler="/health",method="GET",status="200"} 5.0
http_requests_total{handler="/auth/token",method="POST",status="200"} 2.0
http_requests_total{handler="/weather/current",method="GET",status="200"} 60.0

# HELP rate_limit_exceeded_total Total number of rate limit exceeded responses (429)
# TYPE rate_limit_exceeded_total counter
rate_limit_exceeded_total 10.0
```

### Etape 4.2 : Filtrer les Metriques

```bash
# Compteur de requetes par status
curl -s http://localhost:8000/metrics | grep "http_requests_total"

# Compteur rate-limit
curl -s http://localhost:8000/metrics | grep "rate_limit_exceeded"

# Latences
curl -s http://localhost:8000/metrics | grep "http_request_duration_seconds"
```

---

## Demo 5 : Security Headers

### Etape 5.1 : Verifier les Headers

```bash
# Utiliser -D - pour afficher les headers (GET request)
curl -s -D - http://localhost:8000/health -o /dev/null
```

**Resultat attendu** :
```
HTTP/1.1 200 OK
content-type: application/json
x-trace-id: f6b40f74-bdd5-4865-9568-9cd2567eecf9
x-content-type-options: nosniff
x-frame-options: DENY
cache-control: no-store, no-cache, must-revalidate, max-age=0
pragma: no-cache
cross-origin-opener-policy: same-origin
cross-origin-embedder-policy: require-corp
referrer-policy: no-referrer
permissions-policy: geolocation=(), microphone=(), camera=()
```

### Etape 5.2 : Verifier la Tracabilite

```bash
# Envoyer un trace_id personnalise
curl -s -D - http://localhost:8000/health \
  -H "X-Trace-Id: my-custom-trace-123" -o /dev/null | grep -i trace
```

**Resultat attendu** :
```
x-trace-id: my-custom-trace-123
```

---

## Demo 6 : Validation Stricte

### Etape 6.1 : Champ Inconnu Rejete

```bash
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "vehicle_id": "550e8400-e29b-41d4-a716-446655440000",
    "unknown_field": "malicious"
  }' | jq
```

**Resultat attendu** :
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "fields": [
        {
          "field": "unknown_field",
          "issue": "extra_forbidden",
          "message": "Extra inputs are not permitted"
        }
      ]
    }
  }
}
```

### Etape 6.2 : UUID Invalide Rejete

```bash
curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"vehicle_id": "not-a-valid-uuid"}' | jq
```

**Resultat attendu** :
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "fields": [
        {
          "field": "vehicle_id",
          "issue": "uuid_parsing",
          "message": "Input should be a valid UUID"
        }
      ]
    }
  }
}
```

---

## Demo 7 : Service Weather

```bash
# Obtenir la meteo (necessite lat/lon en query params)
curl -s "http://localhost:8000/weather/current?lat=48.8566&lon=2.3522" \
  -H "Authorization: Bearer $TOKEN" | jq '.location.name, .current.temp_c, .current.condition.text'
```

**Resultat attendu** (mode demo fixtures Paris) :
```json
"Paris"
15
"Partly cloudy"
```

> **Note** : La reponse complete inclut `location` (details ville) et `current` (temperature, conditions, vent, humidite, qualite air).

---

## Demo 8 : Service Contacts

```bash
# Liste des contacts (format Google People API)
curl -s "http://localhost:8000/contacts/?person_fields=names,emailAddresses" \
  -H "Authorization: Bearer $TOKEN" | jq '.items | length, .items[0].names[0].displayName'
```

**Resultat attendu** (mode demo avec fixtures) :
```json
5
"Alice Dupont"
```

> **Note** : Les contacts utilisent le format Google People API. En mode demo, 5 contacts fictifs sont disponibles.

---

## Demo 9 : Supply Chain Security (cosign)

> **Prerequis** : Cette demo fonctionne apres que le pipeline CI ait signe l'image.
> En local, vous pouvez simuler la verification avec une image signee.

### Etape 9.1 : Installer cosign (si necessaire)

```bash
# macOS
brew install cosign

# Linux (via Go)
go install github.com/sigstore/cosign/v2/cmd/cosign@latest

# Ou via Docker
alias cosign='docker run --rm gcr.io/projectsigstore/cosign:latest'
```

### Etape 9.2 : Verifier la Signature de l'Image

```bash
# Remplacer par votre registry GitLab
REGISTRY="registry.gitlab.com/votre-groupe/skylink"
IMAGE_TAG="latest"

# Verifier avec la cle publique
cosign verify --key cosign.pub "$REGISTRY:$IMAGE_TAG"
```

**Resultat attendu** :
```
Verification for registry.gitlab.com/votre-groupe/skylink:latest --
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key

[{"critical":{"identity":{"docker-reference":"registry.gitlab.com/..."},...}]
```

### Etape 9.3 : Verifier l'Attestation SBOM

```bash
# Verifier que le SBOM CycloneDX est attache
cosign verify-attestation \
  --key cosign.pub \
  --type cyclonedx \
  "$REGISTRY:$IMAGE_TAG"
```

**Resultat attendu** :
```
Verification for registry.gitlab.com/votre-groupe/skylink:latest --
The following checks were performed on each of these signatures:
  - The cosign claims were validated
  - The signatures were verified against the specified public key

{"payloadType":"application/vnd.in-toto+json","payload":"..."}
```

### Etape 9.4 : Extraire le SBOM de l'Attestation

```bash
# Telecharger et decoder l'attestation SBOM
cosign verify-attestation \
  --key cosign.pub \
  --type cyclonedx \
  "$REGISTRY:$IMAGE_TAG" 2>/dev/null \
  | jq -r '.payload' \
  | base64 -d \
  | jq '.predicate'
```

**Resultat attendu** (extrait) :
```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.4",
  "version": 1,
  "components": [
    {"name": "fastapi", "version": "0.109.0", "type": "library"},
    {"name": "pydantic", "version": "2.5.0", "type": "library"},
    ...
  ]
}
```

### Etape 9.5 : Verification en Mode CI (sans cle)

```bash
# Dans le pipeline GitLab, la cle publique est en variable CI
# La verification est automatique apres attest_sbom

# Pour simuler localement avec la variable CI:
echo "$COSIGN_PUBLIC_KEY" > /tmp/cosign.pub
cosign verify --key /tmp/cosign.pub "$REGISTRY:$IMAGE_TAG"
rm /tmp/cosign.pub
```

---

## Nettoyage

```bash
# Arreter les services
make down

# Supprimer tout (containers, volumes, images)
make clean
```

---

## Captures CI/CD

### Pipeline GitLab

```
Stages: lint -> test -> build -> scan -> sbom -> security-scan -> sign

Jobs:
- lint:ruff            : OK (0 errors)
- lint:black           : OK (formatted)
- lint:bandit          : OK (0 HIGH)
- test:pytest          : OK (307 tests, 81% coverage)
- build:docker         : OK (4 images)
- scan:trivy           : OK (0 CRITICAL)
- scan:gitleaks        : OK (0 secrets)
- scan:pip-audit       : OK (0 vulns)
- sbom:cyclonedx       : OK (artefact genere)
- dast:zap             : OK (baseline)
- sign:sign_image      : OK (image signee cosign)
- sign:attest_sbom     : OK (SBOM attache)
- sign:verify_signature: OK (signature verifiee)
```

### Artefacts CI

| Artefact | Description |
|----------|-------------|
| `sbom.json` | Software Bill of Materials (CycloneDX) |
| `trivy-report.json` | Scan vulnerabilites images |
| `zap-report.html` | Rapport DAST ZAP |
| `coverage.xml` | Rapport coverage pytest |

---

## Resume des Codes HTTP

| Code | Demo | Signification |
|------|------|---------------|
| 200 | Token, Doublon | Succes |
| 201 | Telemetrie | Ressource creee |
| 400 | Validation | Champ invalide |
| 401 | Token expire | Non authentifie |
| 409 | Conflit | Idempotence violee |
| 429 | Rate limit | Trop de requetes |

---

## Checklist Demo

- [ ] Stack demarre (`make up`)
- [ ] Health check OK (`make health`)
- [ ] Token JWT obtenu
- [ ] Telemetrie 201 Created
- [ ] Idempotence 200 OK (doublon)
- [ ] Conflit 409 (donnees differentes)
- [ ] Rate limit 429
- [ ] Metriques /metrics
- [ ] Security headers presents
- [ ] Validation stricte (champs extra rejetes)
- [ ] Signature image verifiee (cosign verify)
- [ ] Attestation SBOM verifiee (cosign verify-attestation)

---

**Guide de demonstration SkyLink - v1.1.0** (avec Supply Chain Security)
