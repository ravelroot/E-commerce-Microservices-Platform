FROM nginx:1.27-alpine
COPY gateway/nginx.conf /etc/nginx/conf.d/default.conf
COPY gateway/proxy_params.conf /etc/nginx/proxy_params.conf
COPY web/ /usr/share/nginx/html/
