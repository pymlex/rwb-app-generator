FROM node:22-bookworm-slim
RUN npm install --global --ignore-scripts --no-audit --no-fund @stoplight/spectral-cli@6.15.0
WORKDIR /checks
COPY checks/spectral/ ./
ENTRYPOINT ["node", "/checks/run.cjs"]
