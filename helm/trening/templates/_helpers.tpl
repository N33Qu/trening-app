{{- define "trening.labels" -}}
app.kubernetes.io/part-of: trening
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}
