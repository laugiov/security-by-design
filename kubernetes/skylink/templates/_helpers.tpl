{{/*
Expand the name of the chart.
*/}}
{{- define "skylink.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "skylink.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "skylink.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "skylink.labels" -}}
helm.sh/chart: {{ include "skylink.chart" . }}
{{ include "skylink.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "skylink.selectorLabels" -}}
app.kubernetes.io/name: {{ include "skylink.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "skylink.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "skylink.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Pod Security Context - Restricted profile
Following Kubernetes Pod Security Standards (restricted)
*/}}
{{- define "skylink.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 1000
runAsGroup: 1000
fsGroup: 1000
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Container Security Context - Restricted profile
*/}}
{{- define "skylink.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop:
    - ALL
{{- end }}

{{/*
Common environment variables from ConfigMap
*/}}
{{- define "skylink.commonEnv" -}}
- name: JWT_AUDIENCE
  valueFrom:
    configMapKeyRef:
      name: {{ include "skylink.fullname" . }}-config
      key: JWT_AUDIENCE
- name: JWT_EXPIRY
  valueFrom:
    configMapKeyRef:
      name: {{ include "skylink.fullname" . }}-config
      key: JWT_EXPIRY
- name: RATE_LIMIT
  valueFrom:
    configMapKeyRef:
      name: {{ include "skylink.fullname" . }}-config
      key: RATE_LIMIT
- name: LOG_LEVEL
  valueFrom:
    configMapKeyRef:
      name: {{ include "skylink.fullname" . }}-config
      key: LOG_LEVEL
{{- end }}

{{/*
Secret environment variables
*/}}
{{- define "skylink.secretEnv" -}}
- name: PRIVATE_KEY_PEM
  valueFrom:
    secretKeyRef:
      name: {{ include "skylink.fullname" . }}-secrets
      key: JWT_PRIVATE_KEY
- name: PUBLIC_KEY_PEM
  valueFrom:
    secretKeyRef:
      name: {{ include "skylink.fullname" . }}-secrets
      key: JWT_PUBLIC_KEY
- name: ENCRYPTION_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "skylink.fullname" . }}-secrets
      key: ENCRYPTION_KEY
{{- end }}

{{/*
Standard liveness probe for HTTP services
*/}}
{{- define "skylink.livenessProbe" -}}
livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
{{- end }}

{{/*
Standard readiness probe for HTTP services
*/}}
{{- define "skylink.readinessProbe" -}}
readinessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
{{- end }}

{{/*
Pod anti-affinity for high availability
*/}}
{{- define "skylink.podAntiAffinity" -}}
podAntiAffinity:
  preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchLabels:
            {{- include "skylink.selectorLabels" . | nindent 12 }}
            app.kubernetes.io/component: {{ .component }}
        topologyKey: kubernetes.io/hostname
{{- end }}

{{/*
Common volume mounts for read-only filesystem
*/}}
{{- define "skylink.volumeMounts" -}}
- name: tmp
  mountPath: /tmp
- name: cache
  mountPath: /var/cache
{{- end }}

{{/*
Common volumes for read-only filesystem
*/}}
{{- define "skylink.volumes" -}}
- name: tmp
  emptyDir: {}
- name: cache
  emptyDir: {}
{{- end }}
