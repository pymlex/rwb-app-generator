Image digests must be supplied by the operator. No digest is guessed or replaced
with an image ID. Run from the generated application directory:

```bash
python3 scripts/image-digests.py
for image in \
  apache/kafka:4.1.0 \
  aquasec/trivy:0.67.2 \
  mcr.microsoft.com/dotnet/aspnet:10.0 \
  mcr.microsoft.com/dotnet/sdk:10.0 \
  mcr.microsoft.com/playwright:v1.64.1-noble \
  nginxinc/nginx-unprivileged:1.28-alpine \
  node:22-bookworm-slim \
  postgres:17.9-bookworm \
  python:3.12-alpine \
  semgrep/semgrep:1.145.0
do
  docker buildx imagetools inspect "$image"
done
```

Return the registry manifest digest (`sha256:…`) and supported platform(s) for
each tag. Keep the tag when pinning (`tag@sha256:…`) so the intended version stays
visible. The inventory lists all references that need updating.

`rwb-app-generator/postgis:${DATABASE_IMAGE_TAG:-17.9}` is a local build of `database/Dockerfile`, not a
published upstream image. Its base image is `postgres:17.9-bookworm` above. To
also pin the built image, the operator must first build and publish it to their
registry, then supply that registry reference and manifest digest. A local
`docker image inspect` ID cannot replace a registry manifest digest.

The other Compose build outputs are also local images, isolated per CI pipeline:
`rwb-app-generator/backend:${APP_IMAGE_TAG:-local}`,
`rwb-app-generator/frontend:${APP_IMAGE_TAG:-local}`,
`rwb-app-generator/unit:${APP_IMAGE_TAG:-local}`,
`rwb-app-generator/audit:${APP_IMAGE_TAG:-local}`,
`rwb-app-generator/spectral:${APP_IMAGE_TAG:-local}`,
`rwb-app-generator/schemathesis:${APP_IMAGE_TAG:-local}`,
`rwb-app-generator/e2e:${APP_IMAGE_TAG:-local}`.
Their Dockerfile base images are included in the inspection list above. Publishing
built application images is a separate operator action, after which their registry
manifest digests can be supplied as well.
