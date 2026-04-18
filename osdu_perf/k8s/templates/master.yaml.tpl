apiVersion: v1
kind: Service
metadata:
  name: ${RUN_NAME}-master
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/managed-by: osdu_perf
    osdu-perf.io/run-id: ${RUN_NAME}
    osdu-perf.io/role: master
spec:
  selector:
    osdu-perf.io/run-id: ${RUN_NAME}
    osdu-perf.io/role: master
  ports:
    - name: rpc
      port: 5557
      targetPort: 5557
      protocol: TCP
    - name: web
      port: 8089
      targetPort: 8089
      protocol: TCP
  clusterIP: None
---
apiVersion: batch/v1
kind: Job
metadata:
  name: ${RUN_NAME}-master
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/managed-by: osdu_perf
    osdu-perf.io/run-id: ${RUN_NAME}
    osdu-perf.io/role: master
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 3600
  template:
    metadata:
      labels:
        app.kubernetes.io/managed-by: osdu_perf
        azure.workload.identity/use: "true"
        osdu-perf.io/run-id: ${RUN_NAME}
        osdu-perf.io/role: master
    spec:
      serviceAccountName: ${SERVICE_ACCOUNT}
      restartPolicy: Never
      containers:
        - name: locust
          image: ${IMAGE}
          imagePullPolicy: Always
          env:
            - name: LOCUST_ROLE
              value: master
          envFrom:
            - configMapRef:
                name: ${RUN_NAME}-env
          ports:
            - containerPort: 5557
              name: rpc
            - containerPort: 8089
              name: web
          resources:
            requests:
              cpu: "6"
              memory: "16Gi"
            limits:
              cpu: "6"
              memory: "16Gi"
