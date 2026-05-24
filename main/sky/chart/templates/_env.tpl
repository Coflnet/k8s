{{- define "coflnet.envVars" -}}
{{- $root := .root -}}
{{- $env := .env | default list -}}
{{- if $env -}}
{{- toYaml $env -}}
{{- end -}}
{{- end -}}