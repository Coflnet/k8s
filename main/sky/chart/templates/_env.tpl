{{- define "coflnet.envVars" -}}
{{- $root := .root -}}
{{- $env := .env | default list -}}
{{- $filtered := list -}}
{{- range $item := $env -}}
{{- $valueFrom := get $item "valueFrom" | default dict -}}
{{- $drop := hasKey $valueFrom "secretKeyRef" -}}
{{- if not $drop -}}
{{- $filtered = append $filtered $item -}}
{{- end -}}
{{- end -}}
{{- if $filtered -}}
{{- toYaml $filtered -}}
{{- end -}}
{{- end -}}