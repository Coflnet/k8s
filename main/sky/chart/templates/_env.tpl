{{- define "coflnet.envVars" -}}
{{- $root := .root -}}
{{- $env := .env | default list -}}
{{- $excludeNames := .excludeNames | default list -}}
{{- $filtered := list -}}
{{- range $item := $env -}}
{{- if not (has $item.name $excludeNames) -}}
{{- $filtered = append $filtered $item -}}
{{- end -}}
{{- end -}}
{{- if $filtered -}}
{{ toYaml $filtered -}}
{{- end -}}
{{- end -}}
