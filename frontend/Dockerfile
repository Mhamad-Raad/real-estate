# Production frontend image — the built SPA, served by Nginx (§2.3).
#
# Two stages so the shipped image carries no Node, no `node_modules` and no source: the office
# gets static files and a web server. That is both smaller to carry on the external drive and a
# smaller surface on a machine that must never reach the internet (§12).

# ---------- build ----------
FROM node:22-slim AS build

WORKDIR /app

# Dependencies first: this layer only rebuilds when the lockfile changes, so a source edit does
# not re-download the whole tree — which matters when the build machine is someone's laptop.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# The build stamp is compiled **into the bundle** by `vite.config.ts` (§2.6). It has to be present
# here, at build time: the frontend has no server to ask, and a bundle that reports 0.0.0 makes the
# version-mismatch banner useless — which is the one thing that catches a half-applied update.
ARG APP_VERSION=0.0.0
ARG APP_BUILD=0
ENV APP_VERSION=${APP_VERSION} \
    APP_BUILD=${APP_BUILD}

RUN npm run build

# ---------- serve ----------
FROM nginx:1.27-alpine

# Our config replaces the default site entirely; the stock one would answer on / and shadow ours.
RUN rm -f /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# `daemon off;` because a container's main process must stay in the foreground, or Docker
# considers it exited the moment Nginx forks.
CMD ["nginx", "-g", "daemon off;"]
