FROM node:20-alpine AS builder
ARG APP_VERSION=dev
ARG VCS_REF=unknown

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
RUN printf '{"version":"%s","commit":"%s"}\n' "$APP_VERSION" "$VCS_REF" > /app/dist/version.json

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
