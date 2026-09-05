# SAT-SA frontend — multi-stage build. Node builds the static Vite bundle,
# nginx serves it. No CDN, no external fonts: everything the app needs is
# either bundled at build time or proxied to the backend service.

# --- Stage 1: build the static assets ---
FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite bakes VITE_* vars into the bundle at build time, not at container
# start — so this has to be a build ARG, not a compose `environment:` entry.
# /api is same-origin through the nginx proxy below, not the backend's
# published host port, so the browser never needs to know the backend's
# actual address.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# --- Stage 2: serve with nginx ---
FROM nginx:alpine AS serve

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
