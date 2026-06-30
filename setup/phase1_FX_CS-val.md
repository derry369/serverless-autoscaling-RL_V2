## Phase 1 – Function 1: Lightweight API (baseline)

- Implemented a minimal FastAPI-based HTTP service (`light-api`) exposing a single `GET /` endpoint that returns a small JSON payload with a timestamp, representing a simple Azure HTTP-trigger analogue.[web:279][web:282]
- Containerized the service using a `python:3.11-slim` base image with `fastapi` and `uvicorn[standard]` as the only third-party dependencies to minimise image size and import overhead.[web:279][web:281]
- Built the image locally as `light-api:phase1`, tagged it as `<ACR_LOGIN_SERVER>/light-api:phase1`, and pushed it to the Basic-tier Azure Container Registry configured in Phase 0.[web:297][web:299]
- Deployed the image as a Knative Service (`light-api`) on the local kind cluster, configured to pull from ACR using the existing `acr-pull-secret`, and verified successful responses via `curl` to the URL reported in `.status.url`, establishing the “fast baseline” function for cold-start comparisons.

## Phase 1 – Function 2: Data processor (pandas ETL analogue)

- Implemented a `data-processor` service using FastAPI that simulates a small ETL workload: on each request it constructs a 1000-row pandas DataFrame with a categorical column, applies a group-by aggregation (mean, std, count) per category, and returns the result as JSON.[web:279][web:284]
- Containerized the service with a `python:3.11-slim` base image and explicit installation of `pandas`, `numpy`, `fastapi`, and `uvicorn[standard]`, plus `build-essential` to satisfy pandas/numpy build requirements, creating a realistically heavier image than the lightweight API.[web:279][web:281]
- Built the image locally as `data-processor:phase1`, tagged it as `<ACR_LOGIN_SERVER>/data-processor:phase1`, and pushed it to the Basic-tier ACR used throughout the experiments.[web:297][web:299]
- Deployed the image as a Knative Service (`data-processor`) on the kind cluster with `acr-pull-secret` configured for image pulls, and verified correct behaviour by `curl`-ing the service URL and observing per-category statistics returned in the response.

## Phase 1 – Function 3: ML inference (PyTorch model analogue)

- Implemented an `ml-inference` service using FastAPI and PyTorch. The service defines a small fully connected network (`TinyNet`) and instantiates it at module import time, so model construction and library imports occur during cold-start rather than lazily on the first request.[web:285][web:290]
- For each request the service generates a random input tensor of shape (1, 16), performs a forward pass through the model under `torch.no_grad()`, and returns the resulting 4-dimensional output vector as JSON, representing a simple ML inference endpoint.[web:289]
- Containerized this service with `python:3.11-slim` plus `torch`, `fastapi`, and `uvicorn[standard]`, and added minimal system dependencies (`build-essential`, `libffi-dev`) required by the PyTorch wheel, resulting in a significantly larger image than the previous two functions and a correspondingly higher cold-start cost.[web:279][web:293]
- Built the image locally as `ml-inference:phase1`, tagged it as `<ACR_LOGIN_SERVER>/ml-inference:phase1`, and pushed it to the same ACR registry used for the other functions.[web:297][web:299]

### ml-inference deployment issue and resolution

- The initial deployment of the `ml-inference` Knative Service reported a timeout from `kubectl wait` and the KService conditions indicated `RevisionFailed` / `RevisionMissing`, while no `ml-inference` pods appeared in the `default` namespace.
- Inspection of the `ml-inference-00001` Revision showed `Ready=False` with `Reason=ContainerCreating` and an `InternalError` event from the revision-controller indicating a conflict when updating the underlying deployment (`Operation cannot be fulfilled ... the object has been modified`).[web:312][web:330]
- To resolve this, the existing `ml-inference` KService was deleted, ensuring that any stale Deployment objects were cleaned up, and then recreated with an explicit image reference of the form `<ACR_LOGIN_SERVER>/ml-inference:phase1` and the `acr-pull-secret` attached.
- After recreating the service, `kubectl wait kservice ml-inference --for=condition=Ready` succeeded. Subsequent `curl` requests to the KService URL caused Knative to scale the service from zero by creating a pod (`ml-inference-00001-deployment-...`) that transitioned through `Pending` and `ContainerCreating` to `Running`, confirming both the scale-to-zero behaviour and the presence of a real cold-start path that includes pulling the PyTorch image, importing the library, and loading the model.

## Phase 1 – Function 4: Image-resize (image library workload)


- Implemented an `image-resize` service using FastAPI that generates an in-memory RGB image on each request, resizes it, and encodes it as JPEG using Pillow, representing a typical serverless image processing function such as thumbnail generation or basic media manipulation.[web:401][web:404]
- Containerized the service on top of a `python:3.11-slim` base image with `fastapi`, `uvicorn[standard]`, and `Pillow`, plus the minimal native libraries required for JPEG support, resulting in a medium-sized image that introduces additional import and initialisation overhead compared to the lightweight API.[web:362][web:402]
- Built the image locally as `image-resize:phase1`, tagged it as `<ACR_LOGIN_SERVER>/image-resize:phase1`, and pushed it to the same Basic-tier Azure Container Registry used for the other functions.[web:385][web:391]
- Deployed the image as a Knative Service (`image-resize`) on the local kind cluster with `acr-pull-secret` configured for private image pulls, and verified correct behaviour by issuing `curl` requests to the KService URL and observing the reported original and resized dimensions and encoded payload size, confirming the presence of a moderate dependency footprint and image-processing logic during cold-start.[web:387][web:397]


## Phase 1 – Function 5: Long-task (long-running batch workload)


- Implemented a `long-task` service using FastAPI that simulates a long-running batch or background job by sleeping for a configurable duration (defaulting to 30 seconds) before returning a JSON payload with start and end timestamps, isolating the impact of extended execution time while keeping imports minimal.[web:403][web:379]
- Containerized the service with a `python:3.11-slim` base image and only `fastapi` and `uvicorn[standard]` as third-party dependencies, producing a small image whose cold-start characteristics are close to the baseline function but whose requests occupy the runtime environment for substantially longer.[web:362][web:403]
- Built the image locally as `long-task:phase1`, tagged it as `<ACR_LOGIN_SERVER>/long-task:phase1`, and pushed it to the same ACR registry as the other workloads.[web:385][web:391]
- Deployed the image as a Knative Service (`long-task`) on the kind cluster with `acr-pull-secret` configured, and validated behaviour by issuing `curl` requests with short (for example 5 seconds) and default (30 seconds) durations, verifying that response timestamps differ by approximately the requested sleep interval and that Knative still performs a full cold-start path for the first invocation after scaling to zero.[web:397][web:362]