#!/usr/bin/env bash
set -euo pipefail

# Phase 0 – Local environment/bootstrap for Knative on kind
# Host OS: Ubuntu 24.04.3 LTS
# Goal: Provide a reproducible script to create a local Knative+Kourier environment on kind.

# STEP 0: Docker Engine installation (performed manually once).
#   - See phase0_local-env-log.md for narrative and troubleshooting notes.
#   - Commands used (recorded for reproducibility; usually run once per host):

# sudo apt update
# sudo apt install ca-certificates curl apt-transport-https software-properties-common -y
# sudo install -m 0755 -d /etc/apt/keyrings
# curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
# echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
# sudo apt update
# sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
# sudo systemctl enable --now docker

# STEP 1: Basic Docker verification
#   - docker run hello-world
#   - If credential helper error appears, remove or edit ~/.docker/config.json (remove 'credsStore': 'desktop').

# STEP 2: Install kubectl and kind, then create a cluster with port mappings for 80 and 443.

# Install kubectl (client only)
# Using snap for simplicity on Ubuntu.
sudo snap install kubectl --classic

# Verify kubectl client installation
kubectl version --client

# Install kind (Linux, automatic arch detection for x86_64/ARM64)
if [ "$(uname -m)" = "x86_64" ]; then
  curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.31.0/kind-linux-amd64
elif [ "$(uname -m)" = "aarch64" ]; then
  curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.31.0/kind-linux-arm64
else
  echo "Unsupported CPU architecture for automated kind install"; exit 1
fi

chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind

# Verify kind installation
kind --version

# Create kind cluster configuration with extraPortMappings for 80 and 443.
cat <<EOF > kind-knative.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 31080
    hostPort: 80
    protocol: TCP
  - containerPort: 31443
    hostPort: 443
    protocol: TCP
EOF

# Create the cluster
kind create cluster --name knative --config kind-knative.yaml

# Verify cluster information
kubectl cluster-info --context kind-knative

# STEP 3: Install Knative Serving and Kourier, configure ingress, and deploy hello-world.

# Choose Knative versions (aligned with kind-supported Kubernetes versions).
export KNATIVE_VERSION="knative-v1.10.2"
export KNATIVE_NET_KOURIER_VERSION="knative-v1.10.0"

# Install Knative Serving CRDs and core components
kubectl apply -f https://github.com/knative/serving/releases/download/${KNATIVE_VERSION}/serving-crds.yaml
kubectl apply -f https://github.com/knative/serving/releases/download/${KNATIVE_VERSION}/serving-core.yaml

# Wait for Knative Serving control plane to become Available
kubectl wait deployment --all --for=condition=Available -n knative-serving --timeout=300s

# Install Kourier as the networking layer for Knative
kubectl apply -f https://github.com/knative/net-kourier/releases/download/${KNATIVE_NET_KOURIER_VERSION}/kourier.yaml

# Wait for Kourier components
kubectl wait deployment --all --for=condition=Available -n kourier-system --timeout=300s

# Configure Knative to use Kourier as the ingress class
kubectl patch configmap/config-network \
  -n knative-serving \
  --type merge \
  -p '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}'

# Configure a magic domain using sslip.io for local DNS
kubectl patch configmap -n knative-serving config-domain \
  -p '{"data": {"127.0.0.1.sslip.io": ""}}'

# Expose the Kourier ingress via NodePort that matches kind extraPortMappings (80/443).
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: kourier-ingress
  namespace: kourier-system
spec:
  type: NodePort
  selector:
    app: 3scale-kourier-gateway
  ports:
  - name: http2
    nodePort: 31080
    port: 80
    targetPort: 8080
  - name: https
    nodePort: 31443
    port: 443
    targetPort: 8443
EOF

# STEP 4: Deploy a Knative hello-world service and verify via curl.

# Deploy the helloworld-go Knative Service
cat <<EOF > hello.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: helloworld-go
  namespace: default
spec:
  template:
    spec:
      containers:
      - image: gcr.io/knative-samples/helloworld-go
        env:
        - name: TARGET
          value: "World"
EOF

kubectl apply -f hello.yaml

# Wait until the Knative Service reports Ready
kubectl wait kservice helloworld-go --for=condition=Ready --timeout=300s

# Retrieve the URL assigned to the service
SERVICE_URL=$(kubectl get kservice helloworld-go -o jsonpath='{.status.url}')
echo "Knative Service URL: ${SERVICE_URL}"

# Verify end-to-end local path with curl
curl -v "${SERVICE_URL}"

# STEP 5: Azure Container Registry (ACR) integration with kind

# Assumes:
# - Azure CLI installed and logged in (az login)
# - Subscription selected (az account set --subscription "<SUBSCRIPTION>")
# - Resource group and ACR already created with SKU Basic in your chosen region
# - Test image built and pushed as ${ACR_LOGIN_SERVER}/acr-test:latest

# Retrieve ACR login server and credentials
ACR_LOGIN_SERVER=$(az acr show --name "<ACR_NAME>" --query loginServer -o tsv)
ACR_USERNAME=$(az acr credential show --name "<ACR_NAME>" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "<ACR_NAME>" --query "passwords[0].value" -o tsv)

# Create Kubernetes docker-registry secret for ACR in the default namespace
kubectl create secret docker-registry acr-pull-secret \
  --namespace default \
  --docker-server="${ACR_LOGIN_SERVER}" \
  --docker-username="${ACR_USERNAME}" \
  --docker-password="${ACR_PASSWORD}" \
  --docker-email="example@example.com"

# Deploy a test pod that pulls from ACR using the imagePullSecret
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: acr-test-pod
  namespace: default
spec:
  containers:
  - name: acr-test
    image: ${ACR_LOGIN_SERVER}/acr-test:latest
    imagePullPolicy: Always
  imagePullSecrets:
  - name: acr-pull-secret
EOF

# Wait for the pod to become Ready
kubectl wait pod acr-test-pod --for=condition=Ready --timeout=120s -n default
kubectl get pod acr-test-pod -n default

# STEP 6: Install Prometheus and Grafana via Helm and validate observability

# 6.1 Install Helm (if not already installed)
# Note: This uses the official Helm install script.
if ! command -v helm >/dev/null 2>&1; then
  curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

helm version

# 6.2 Add Helm repositories for Prometheus and Grafana
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# 6.3 Install Prometheus into the 'monitoring' namespace
helm install prometheus prometheus-community/prometheus \
  --namespace monitoring \
  --create-namespace

# 6.4 Install Grafana into the 'monitoring' namespace
helm install grafana grafana/grafana \
  --namespace monitoring

# 6.5 Verify Prometheus and Grafana pods are running
kubectl get pods -n monitoring

# 6.6 Port-forward Prometheus and Grafana services to localhost
# (Run these in separate terminals when needed)
# kubectl port-forward svc/prometheus-server -n monitoring 9090:80
# kubectl port-forward svc/grafana -n monitoring 3000:80

# 6.7 Retrieve Grafana admin password
kubectl get secret grafana \
  -n monitoring \
  -o jsonpath="{.data.admin-password}" | base64 --decode; echo

# 6.8 (Manual in UI) Configure Grafana Prometheus data source:
#   - URL: http://prometheus-server.monitoring.svc.cluster.local
#   - Save & test: expect "Data source is working".

# 6.9 Generate load against Knative hello-world service
HELLO_URL=$(kubectl get kservice helloworld-go -o jsonpath='{.status.url}')
echo "Hello-world URL: ${HELLO_URL}"

for i in $(seq 1 50); do
  curl -s -o /dev/null -w "%{http_code}\n" "${HELLO_URL}"
done

# 6.10 (Manual in UI) Validate metrics:
#   - In Prometheus: query
#       envoy_cluster_upstream_rq_time_bucket{envoy_cluster_name="default/helloworld-go-00001", le="+Inf"}
#   - In Grafana Explore: run the same query using the Prometheus data source.
#   - Confirm that the time series is non-zero and increases with load, indicating that
#     Envoy/Kourier is exporting upstream request time histograms for the Knative revision.