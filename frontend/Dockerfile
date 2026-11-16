FROM node:20-alpine AS development
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Public site address (e.g. https://chiz.example), baked into the bundle at build time: it is the
# origin of every <link rel="canonical">, JSON-LD and Open Graph URL. Optional; when empty the
# current origin is used. Pass with: docker compose build --build-arg VITE_SITE_URL=...
ARG VITE_SITE_URL=
ENV VITE_SITE_URL=$VITE_SITE_URL
# robots.txt is generated at build time (frontend/robots.js) and is BLOCKED (Disallow: /) unless
# VITE_ALLOW_INDEXING is exactly "true". Set it ONLY for the real production site; it also needs a
# real https VITE_SITE_URL (the build fails otherwise). VITE_SITEMAP_URL is optional: where the
# sitemap is served, if not <VITE_SITE_URL>/sitemap.xml. See backend/docs/adr/0004-robots-txt-build-time.md
# NOTE: build args/ENV take precedence over any frontend/.env.* file, even when empty.
ARG VITE_ALLOW_INDEXING=
ENV VITE_ALLOW_INDEXING=$VITE_ALLOW_INDEXING
ARG VITE_SITEMAP_URL=
ENV VITE_SITEMAP_URL=$VITE_SITEMAP_URL
RUN npm run build

FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
