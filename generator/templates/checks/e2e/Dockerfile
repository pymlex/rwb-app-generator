FROM mcr.microsoft.com/playwright:v1.64.1-noble
WORKDIR /checks
RUN npm install --ignore-scripts --no-audit --no-fund playwright@1.64.1
COPY checks/e2e/smoke.cjs ./
ENTRYPOINT ["node", "/checks/smoke.cjs"]
