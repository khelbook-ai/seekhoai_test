# Seekhai_test frontend — build the Vite bundle, then serve it with nginx. nginx also proxies
# /api to the backend, so the browser only ever talks to one origin (no CORS needed).
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
