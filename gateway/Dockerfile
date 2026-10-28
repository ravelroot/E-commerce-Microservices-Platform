FROM nginx:1.27-alpine
COPY gateway/nginx.conf /etc/nginx/conf.d/default.conf
COPY gateway/proxy_params.conf /etc/nginx/proxy_params.conf
COPY gateway/security_headers.conf /etc/nginx/security_headers.conf
COPY web/ /usr/share/nginx/html/
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
