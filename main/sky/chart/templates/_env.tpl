{{- define "coflnet.envVars" -}}
{{- $root := .root -}}
{{- $env := .env | default list -}}
{{- range $item := $env -}}
{{- toYaml $item -}}
{{- end -}}
{{- end -}}