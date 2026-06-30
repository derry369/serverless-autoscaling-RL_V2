# Phase 0 – Local environment validation (kind + Knative + Kourier)

**Host OS:** Ubuntu 24.04.3 LTS  
**Goal:** Verify local path from host → kind cluster → Knative Service → Kourier ingress → curl hello-world.

## Step 1 – Docker Engine

- Installed Docker Engine from the official Docker APT repository on Ubuntu 24.04.3.
- Verified installation with `docker run hello-world`.
- Encountered `docker-credential-desktop` error; resolved by editing/removing `~/.docker/config.json` to remove the `credsStore: "desktop"` entry.

## Step 2 – Kubernetes in Docker (kind) and Knative bootstrap

- Installed `kubectl` client via `snap` and verified with `kubectl version --client`.
- Installed `kind` (v0.31.0 binary for Linux) and verified with `kind --version`.[web:40][web:87]
- Created a `kind-knative.yaml` configuration with `extraPortMappings` for ports 80 and 443 mapped to NodePorts 31080 and 31443 on the control-plane node.[web:47][web:53]
- Created a kind cluster named `knative` using this configuration and confirmed connectivity with `kubectl cluster-info --context kind-knative`.

## Step 3 – Knative Serving, Kourier, and networking configuration

- Installed Knative Serving (CRDs and core) using release `knative-v1.10.2` and waited for all deployments in `knative-serving` to become Available.[web:6][web:88]
- Installed Kourier (`knative-v1.10.0`) as the networking layer and waited for deployments in `kourier-system` to become Available.[web:6][web:88]
- Patched the `config-network` ConfigMap in `knative-serving` to set the `ingress-class` to `kourier.ingress.networking.knative.dev` so that Knative routes are handled by Kourier.[web:6][web:88]
- Patched the `config-domain` ConfigMap to use `127.0.0.1.sslip.io` as a magic local domain for Knative service URLs.
- Exposed the `kourier-ingress` Service as a `NodePort` in the `kourier-system` namespace, mapping HTTP/HTTPS ports (80/443) to NodePorts 31080/31443 to align with the kind port mappings.[web:48][web:88]

## Step 4 – Hello-world Knative Service deployment and verification

- Created a `helloworld-go` Knative Service in the `default` namespace using the `gcr.io/knative-samples/helloworld-go` container image with `TARGET="World"`.[web:84][web:89]
- Waited for the Knative Service to reach the `Ready` condition via `kubectl wait kservice helloworld-go --for=condition=Ready`.
- Retrieved the service URL from `.status.url`, which followed the pattern `http://helloworld-go.default.127.0.0.1.sslip.io`.
- Verified the full local path (host → kind → Knative → Kourier → service) by issuing `curl -v <SERVICE_URL>` and observing the expected “Hello World” response.

## Step 5 – Azure Container Registry integration (cost-cautious)

- Created a Basic tier Azure Container Registry (ACR) in the chosen European region using Azure CLI, under a dedicated resource group to keep costs isolated within the $100 student credit.[web:106][web:151]
- Built a small Alpine-based test image locally, tagged it as `<loginServer>/acr-test:latest`, and pushed it to ACR using `az acr login` followed by `docker push`.[web:111][web:115]
- Retrieved the ACR `loginServer`, `username`, and `password` values with `az acr show` and `az acr credential show`, and used them to create a `docker-registry` Kubernetes secret (`acr-pull-secret`) in the `default` namespace via `kubectl create secret docker-registry ...`.[web:116][web:168]
- Deployed a test pod (`acr-test-pod`) in the kind cluster referencing the ACR image and the `acr-pull-secret` in `imagePullSecrets`, and confirmed that the pod reached the `Ready` condition, demonstrating that the kind cluster can pull private images from ACR successfully.

## Step 6 – Observability: Prometheus and Grafana

- Installed Helm 3 on the local Ubuntu host using the official Helm install script, then added the `prometheus-community` and `grafana` chart repositories and updated the index.[web:180][web:176]
- Deployed Prometheus to the `monitoring` namespace via the `prometheus-community/prometheus` chart and verified that the Prometheus server and related exporters (kube-state-metrics, node exporter, etc.) were running.[web:180][web:187]
- Deployed Grafana to the same `monitoring` namespace using the `grafana/grafana` chart and retrieved the automatically generated admin password from the `grafana` secret.[web:176][web:199]
- Port-forwarded the Prometheus service to `localhost:9090` and the Grafana service to `localhost:3000`, allowing direct access to both UIs from the host.[web:180][web:182]
- Configured Grafana with a Prometheus data source pointing at the in-cluster Prometheus server (`http://prometheus-server.monitoring.svc.cluster.local`) and confirmed the data source test succeeded.[web:199][web:242]
- Generated HTTP traffic against the Knative `helloworld-go` service using repeated `curl` requests to the service URL obtained from `.status.url`.
- In both Prometheus and Grafana, queried the Envoy/Kourier histogram metric  
  `envoy_cluster_upstream_rq_time_bucket{envoy_cluster_name="default/helloworld-go-00001", le="+Inf"}`  
  and observed a non-zero, monotonically increasing time series, indicating that the Envoy gateway was exporting upstream request time histograms for the hello-world revision and that the observability pipeline from Knative/Kourier into Prometheus and Grafana was functional.[web:208][web:211]