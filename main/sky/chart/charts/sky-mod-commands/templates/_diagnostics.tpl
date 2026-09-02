{{- define "sky-mod-commands.diagnosticsAppEnv" -}}
{{- if .Values.diagnostics.enabled }}
- name: DOTNET_DiagnosticPorts
  value: /diag/dotnet-monitor.sock,nosuspend
{{- end }}
{{- end }}

{{- define "sky-mod-commands.diagnosticsAppVolumeMount" -}}
{{- if .Values.diagnostics.enabled }}
- name: dotnet-diagnostics
  mountPath: /diag
{{- end }}
{{- end }}

{{- define "sky-mod-commands.diagnosticsContainer" -}}
{{- if .Values.diagnostics.enabled }}
- name: dotnet-monitor
  image: {{ .Values.diagnostics.image.repository }}:{{ .Values.diagnostics.image.tag }}
  imagePullPolicy: {{ .Values.diagnostics.image.pullPolicy }}
  args: ["collect", "--temp-apikey", "--no-http-egress"]
  securityContext:
    allowPrivilegeEscalation: false
    privileged: false
    readOnlyRootFilesystem: true
    runAsNonRoot: true
    capabilities:
      drop:
        - ALL
    seccompProfile:
      type: RuntimeDefault
  env:
    - name: DOTNETMONITOR_DiagnosticPort__ConnectionMode
      value: Listen
    - name: DOTNETMONITOR_Storage__DefaultSharedPath
      value: /diag
    - name: DOTNETMONITOR_Urls
      value: http://127.0.0.1:52323
    - name: DOTNETMONITOR_Metrics__Enabled
      value: "false"
    - name: DOTNETMONITOR_Egress__FileSystem__artifacts__DirectoryPath
      value: /diag/artifacts
    - name: DOTNETMONITOR_Egress__FileSystem__artifacts__IntermediateDirectoryPath
      value: /diag/intermediate
    - name: DOTNETMONITOR_CollectionRules__HighMemory__Trigger__Type
      value: EventCounter
    - name: DOTNETMONITOR_CollectionRules__HighMemory__Trigger__Settings__ProviderName
      value: System.Runtime
    - name: DOTNETMONITOR_CollectionRules__HighMemory__Trigger__Settings__CounterName
      value: working-set
    - name: DOTNETMONITOR_CollectionRules__HighMemory__Trigger__Settings__GreaterThan
      value: {{ .Values.diagnostics.workingSetThresholdMb | quote }}
    - name: DOTNETMONITOR_CollectionRules__HighMemory__Trigger__Settings__SlidingWindowDuration
      value: "00:00:15"
    - name: DOTNETMONITOR_CollectionRules__HighMemory__Actions__0__Type
      value: CollectDump
    - name: DOTNETMONITOR_CollectionRules__HighMemory__Actions__0__Settings__Type
      value: Full
    - name: DOTNETMONITOR_CollectionRules__HighMemory__Actions__0__Settings__Egress
      value: artifacts
    - name: DOTNETMONITOR_CollectionRules__HighMemory__Actions__1__Type
      value: CollectGCDump
    - name: DOTNETMONITOR_CollectionRules__HighMemory__Actions__1__Settings__Egress
      value: artifacts
    - name: DOTNETMONITOR_CollectionRules__HighMemory__Limits__ActionCount
      value: "1"
  resources:
    {{- toYaml .Values.diagnostics.resources | nindent 4 }}
  volumeMounts:
    - name: dotnet-diagnostics
      mountPath: /diag
    - name: dotnet-monitor-tmp
      mountPath: /tmp
{{- end }}
{{- end }}

{{- define "sky-mod-commands.diagnosticsVolumes" -}}
{{- if .Values.diagnostics.enabled }}
- name: dotnet-diagnostics
  emptyDir:
    sizeLimit: {{ .Values.diagnostics.artifactsSizeLimit }}
- name: dotnet-monitor-tmp
  emptyDir:
    sizeLimit: 128Mi
{{- end }}
{{- end }}
