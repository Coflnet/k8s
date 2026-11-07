{{- define "coflnet.envVars" -}}
{{- $root := .root -}}
{{- $env := .env | default list -}}
{{- $excludeNames := .excludeNames | default list -}}
{{- /* Optional "pki": when the app PKI path is on, pki.env wins over same-named entries. */ -}}
{{- $pki := .pki | default dict -}}
{{- if and $pki.enabled $pki.applicationEnabled -}}
{{- $excludeNames = concat $excludeNames (keys ($pki.env | default dict)) -}}
{{- end -}}
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
