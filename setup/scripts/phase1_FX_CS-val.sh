# STEP 1 – Build and deploy lightweight API (baseline function)

# Build local image
docker build -t light-api:phase1 ./functions/light-api

# Tag and push to ACR
ACR_LOGIN_SERVER=$(az acr show --name "<ACR_NAME>" --query loginServer -o tsv)
docker tag light-api:phase1 "${ACR_LOGIN_SERVER}/light-api:phase1"
az acr login --name "<ACR_NAME>"
docker push "${ACR_LOGIN_SERVER}/light-api:phase1"

# Deploy as a Knative Service on kind
cat << EOF | kubectl apply -f -
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: light-api
  namespace: default
spec:
  template:
    spec:
      containers:
      - image: ${ACR_LOGIN_SERVER}/light-api:phase1
        env:
        - name: SERVICE_NAME
          value: "light-api"
      imagePullSecrets:
      - name: acr-pull-secret
EOF

kubectl wait kservice light-api --for=condition=Ready --timeout=300s
kubectl get kservice light-api

# STEP 2 – Build and deploy data-processor (pandas ETL analogue)

# Build image
docker build -t data-processor:phase1 ./functions/data-processor

# Tag and push to ACR
ACR_LOGIN_SERVER=$(az acr show --name "<ACR_NAME>" --query loginServer -o tsv)
docker tag data-processor:phase1 "${ACR_LOGIN_SERVER}/data-processor:phase1"
az acr login --name "<ACR_NAME>"
docker push "${ACR_LOGIN_SERVER}/data-processor:phase1"

# Deploy as a Knative Service on kind
cat << EOF | kubectl apply -f -
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: data-processor
  namespace: default
spec:
  template:
    spec:
      containers:
      - image: ${ACR_LOGIN_SERVER}/data-processor:phase1
        env:
        - name: SERVICE_NAME
          value: "data-processor"
      imagePullSecrets:
      - name: acr-pull-secret
EOF

kubectl wait kservice data-processor --for=condition=Ready --timeout=300s
kubectl get kservice data-processor

# STEP 3 – Build and deploy ml-inference (PyTorch inference analogue)

# Build image
docker build -t ml-inference:phase1 ./functions/ml-inference

# Tag and push to ACR
ACR_LOGIN_SERVER=$(az acr show --name "<ACR_NAME>" --query loginServer -o tsv)
docker tag ml-inference:phase1 "${ACR_LOGIN_SERVER}/ml-inference:phase1"
az acr login --name "<ACR_NAME>"
docker push "${ACR_LOGIN_SERVER}/ml-inference:phase1"

# Clean up any previous Knative Service for ml-inference (if present)
kubectl delete kservice ml-inference -n default --ignore-not-found

# Deploy as a Knative Service on kind
cat << EOF | kubectl apply -f -
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ml-inference
  namespace: default
spec:
  template:
    spec:
      containers:
      - image: ${ACR_LOGIN_SERVER}/ml-inference:phase1
        env:
        - name: SERVICE_NAME
          value: "ml-inference"
      imagePullSecrets:
      - name: acr-pull-secret
EOF

kubectl wait kservice ml-inference --for=condition=Ready --timeout=300s
kubectl get kservice ml-inference

# STEP 4 – Build and deploy image-resize (image library workload)


# Build local image
docker build -t image-resize:phase1 ./functions/image-resize


# Tag and push to ACR
ACR_LOGIN_SERVER=$(az acr show --name "<ACR_NAME>" --query loginServer -o tsv)
docker tag image-resize:phase1 "${ACR_LOGIN_SERVER}/image-resize:phase1"
az acr login --name "<ACR_NAME>"
docker push "${ACR_LOGIN_SERVER}/image-resize:phase1"


# Deploy as a Knative Service on kind
cat << EOF | kubectl apply -f -
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: image-resize
  namespace: default
spec:
  template:
    spec:
      containers:
      - image: ${ACR_LOGIN_SERVER}/image-resize:phase1
        env:
        - name: SERVICE_NAME
          value: "image-resize"
      imagePullSecrets:
      - name: acr-pull-secret
EOF


kubectl wait kservice image-resize --for=condition=Ready --timeout=300s
kubectl get kservice image-resize


# STEP 5 – Build and deploy long-task (long-running batch workload)


# Build local image
docker build -t long-task:phase1 ./functions/long-task


# Tag and push to ACR
ACR_LOGIN_SERVER=$(az acr show --name "<ACR_NAME>" --query loginServer -o tsv)
docker tag long-task:phase1 "${ACR_LOGIN_SERVER}/long-task:phase1"
az acr login --name "<ACR_NAME>"
docker push "${ACR_LOGIN_SERVER}/long-task:phase1"


# Deploy as a Knative Service on kind
cat << EOF | kubectl apply -f -
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: long-task
  namespace: default
spec:
  template:
    spec:
      containers:
      - image: ${ACR_LOGIN_SERVER}/long-task:phase1
        env:
        - name: SERVICE_NAME
          value: "long-task"
      imagePullSecrets:
      - name: acr-pull-secret
EOF


kubectl wait kservice long-task --for=condition=Ready --timeout=300s
kubectl get kservice long-task