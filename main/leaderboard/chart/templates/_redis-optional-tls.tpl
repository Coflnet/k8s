{{- define "coflnet.redisOptionalTls.args" -}}
- --tls-port
- "6380"
- --tls-cert-file
- /optional-tls/tls.crt
- --tls-key-file
- /optional-tls/tls.key
- --tls-ca-cert-file
- /optional-tls/ca.crt
- --tls-auth-clients
- optional
{{- end -}}

{{- define "coflnet.redisOptionalTls.mount" -}}
- name: redis-optional-tls
  mountPath: /optional-tls
  readOnly: true
{{- end -}}

{{- define "coflnet.redisOptionalTls.volume" -}}
- name: redis-optional-tls
  projected:
    defaultMode: 0440
    sources:
    - secret:
        name: {{ .name }}-shared-tls
    - configMap:
        name: {{ required "global.redisOptionalTls.trustBundleConfigMap is required" .config.trustBundleConfigMap }}
        items:
        - key: ca.crt
          path: ca.crt
- name: redis-tls-reloader
  configMap:
    name: redis-tls-reloader
{{- end -}}

{{- define "coflnet.redisOptionalTls.reloader" -}}
- name: redis-tls-reloader
  image: python:3.13-alpine@sha256:8bcfa47b04b853a17aaf909362b847b2112fd6ec4105ea553ef9a43bafbb5916
  command: [python3, -B, /reload/reloader.py]
  securityContext:
    runAsNonRoot: true
    runAsUser: 999
    allowPrivilegeEscalation: false
    readOnlyRootFilesystem: true
    capabilities:
      drop: [ALL]
    seccompProfile:
      type: RuntimeDefault
  {{- with .passwordSecret }}
  env:
  - name: REDIS_PASSWORD
    valueFrom:
      secretKeyRef:
        name: {{ .name }}
        key: {{ .key | default "password" }}
  {{- end }}
  resources:
    requests: {cpu: 5m, memory: 16Mi}
    limits: {cpu: 100m, memory: 32Mi}
  volumeMounts:
  {{- include "coflnet.redisOptionalTls.mount" . | nindent 2 }}
  - name: redis-tls-reloader
    mountPath: /reload
    readOnly: true
{{- end -}}
