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

# Security hardening: run as a non-root, non-privileged user. nginx:alpine
# already ships an unprivileged "nginx" user/group (uid/gid 101); the
# default config just runs as root anyway to bind port 80, which is a
# privileged port a non-root process cannot bind. nginx.conf now listens on
# 8080 instead (see docker-compose.yml's "80:8080" port mapping — the
# host-facing address is unchanged, only the *container-internal* port
# moved above 1024), and every path nginx needs to write to at runtime
# (cache, the pid file) is chown'd to that user below so master/worker
# processes never need root once they start.
RUN chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
