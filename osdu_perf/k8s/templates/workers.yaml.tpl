apiVersion: batch/v1
kind: Job
metadata:
  name: ${RUN_NAME}-workers
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/managed-by: osdu_perf
    osdu-perf.io/run-id: ${RUN_NAME}
    osdu-perf.io/role: worker
spec:
  parallelism: ${WORKER_COUNT}
  completions: ${WORKER_COUNT}
  backoffLimit: 0
  ttlSecondsAfterFinished: 3600
  template:
    metadata:
      labels:
        app.kubernetes.io/managed-by: osdu_perf
        azure.workload.identity/use: "true"
        osdu-perf.io/run-id: ${RUN_NAME}
        osdu-perf.io/role: worker
    spec:
      serviceAccountName: ${SERVICE_ACCOUNT}
      restartPolicy: Never
      containers:
        - name: locust
          image: ${IMAGE}
          imagePullPolicy: Always
          env:
            - name: LOCUST_ROLE
              value: worker
            - name: LOCUST_MASTER_HOST
              value: ${RUN_NAME}-master.${NAMESPACE}.svc.cluster.local
          envFrom:
            - configMapRef:
                name: ${RUN_NAME}-env
          resources:
            requests:
              cpu: "6"
              memory: "16Gi"
            limits:
              cpu: "6"
              memory: "16Gi"
