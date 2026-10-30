FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package*.json .
RUN npm ci --no-fund --no-audit
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.28-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/app/browser /usr/share/nginx/html
EXPOSE 8080
