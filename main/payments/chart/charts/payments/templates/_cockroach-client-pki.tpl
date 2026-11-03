{{/*
Per-instance CockroachDB client certificates (openbao.database.mtls.instances).
Helpers taking a context expect (dict "root" $ "p" <payments entry>).
*/}}

{{/* Instance key of a payments entry: "tab-payments" -> "tab". */}}
{{- define "payments.instance" -}}
{{- trimSuffix "-payments" .name -}}
{{- end }}

{{- define "payments.cockroachClient.name" -}}
{{- printf "%s-cockroach-client" (include "payments.instance" .p) -}}
{{- end }}

{{- define "payments.cockroachClient.serviceAccount" -}}
{{- printf "%s-certificates" (include "payments.instance" .p) -}}
{{- end }}

{{- define "payments.cockroachClient.trustName" -}}
{{- printf "%s-cockroach-trust" (include "payments.instance" .p) -}}
{{- end }}

{{/* The instance's phase switches as YAML ({} when unlisted); fails on an inconsistent phase order. */}}
{{- define "payments.cockroachClient.settings" -}}
{{- $instance := include "payments.instance" .p -}}
{{- $settings := get (.root.Values.openbao.database.mtls.instances | default dict) $instance | default dict -}}
{{- if and $settings.mounts (not $settings.stage) -}}
{{- fail (printf "openbao.database.mtls.instances.%s.mounts needs stage (the client Secret would not exist)" $instance) -}}
{{- end -}}
{{- if and $settings.application (not $settings.mounts) -}}
{{- fail (printf "openbao.database.mtls.instances.%s.application needs mounts (the certificate files would be missing)" $instance) -}}
{{- end -}}
{{- if and $settings.application (not .root.Values.openbao.database.enabled) -}}
{{- fail (printf "openbao.database.mtls.instances.%s.application needs openbao.database.enabled (the OPENBAO__DB__ master switch)" $instance) -}}
{{- end -}}
{{- toYaml $settings -}}
{{- end }}

{{/* "true" when the phase is on for this instance, "" otherwise. */}}
{{- define "payments.cockroachClient.stage" -}}
{{- if (fromYaml (include "payments.cockroachClient.settings" .)).stage }}true{{ end -}}
{{- end }}

{{- define "payments.cockroachClient.mounts" -}}
{{- if (fromYaml (include "payments.cockroachClient.settings" .)).mounts }}true{{ end -}}
{{- end }}

{{- define "payments.cockroachClient.application" -}}
{{- if (fromYaml (include "payments.cockroachClient.settings" .)).application }}true{{ end -}}
{{- end }}

{{/* Fails when an enabled instance key matches no payments entry (e.g. a typo such as "tab-payments"). */}}
{{- define "payments.cockroachClient.validateInstances" -}}
{{- $known := list -}}
{{- range .Values.payments -}}
{{- $known = append $known (include "payments.instance" .) -}}
{{- end -}}
{{- range $instance, $settings := .Values.openbao.database.mtls.instances | default dict -}}
{{- if and (or $settings.stage $settings.mounts $settings.application) (not (has $instance $known)) -}}
{{- fail (printf "openbao.database.mtls.instances.%s is enabled but there is no payments entry %s-payments" $instance $instance) -}}
{{- end -}}
{{- end -}}
{{- end }}

{{/* Pod securityContext; adds fsGroup when mounted so the 0440 client key is readable by the app group. */}}
{{- define "payments.podSecurityContext" -}}
{{- $securityContext := deepCopy (.root.Values.podSecurityContext | default dict) -}}
{{- if include "payments.cockroachClient.mounts" . -}}
{{- $fsGroup := .root.Values.openbao.database.mtls.clientPki.fsGroup | int64 -}}
{{- $_ := set $securityContext "fsGroup" ($securityContext.fsGroup | default $fsGroup) -}}
{{- end -}}
{{- toYaml $securityContext -}}
{{- end }}
