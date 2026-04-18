{{/*
Common labels and selectors for the osdu-perf release.
*/}}

{{- define "osdu-perf.name" -}}
{{ required "runName is required" .Values.runName }}
{{- end -}}

{{- define "osdu-perf.labels" -}}
app.kubernetes.io/managed-by: osdu_perf
app.kubernetes.io/instance: {{ include "osdu-perf.name" . }}
osdu-perf.io/run-id: {{ include "osdu-perf.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "osdu-perf.masterSelector" -}}
osdu-perf.io/run-id: {{ include "osdu-perf.name" . }}
osdu-perf.io/role: master
{{- end -}}

{{- define "osdu-perf.workerSelector" -}}
osdu-perf.io/run-id: {{ include "osdu-perf.name" . }}
osdu-perf.io/role: worker
{{- end -}}

{{- define "osdu-perf.image" -}}
{{- $repo := required "image.repository is required" .Values.image.repository -}}
{{- $tag := required "image.tag is required" .Values.image.tag -}}
{{ $repo }}:{{ $tag }}
{{- end -}}

{{- define "osdu-perf.isWebUi" -}}
{{- eq (lower (default "headless" .Values.mode)) "webui" -}}
{{- end -}}
