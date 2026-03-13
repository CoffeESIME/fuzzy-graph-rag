# ──────────────────────────────────────────────
# Stage 1: Builder – compila la app React/Vite
# ──────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Instalar dependencias primero (capa cacheable)
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# Copiar fuentes y compilar
COPY . .
RUN npm run build

# ──────────────────────────────────────────────
# Stage 2: Runtime – Nginx sirve el bundle
# ──────────────────────────────────────────────
FROM nginx:alpine AS runtime

# Copiar el bundle compilado
COPY --from=builder /app/dist /usr/share/nginx/html

# Copiar la configuración de Nginx con proxy a backend
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
