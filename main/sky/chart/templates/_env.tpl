{{- define "coflnet.envVars" -}}
{{- $root := .root -}}
{{- $env := .env | default list -}}
{{- $excludeNames := .excludeNames | default list -}}
{{- $filtered := list -}}
{{- range $item := $env -}}
{{- $fromSecret := hasKey ($item.valueFrom | default dict) "secretKeyRef" -}}
{{- if and (not (has $item.name $excludeNames)) (not (and ($root.Values.openbaoOnly | default false) $fromSecret)) -}}
{{- $filtered = append $filtered $item -}}
{{- end -}}
{{- end -}}
{{- if $filtered -}}
{{ toYaml $filtered -}}
{{- end -}}
{{- end -}}
