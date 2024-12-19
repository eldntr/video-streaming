FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Jakarta

RUN apt-get update && apt-get install -y \
    tzdata \
    build-essential \
    libpcre3 \
    libpcre3-dev \
    libssl-dev \
    zlib1g-dev \
    wget \
    ffmpeg \
    curl \
    python3 \
    python3-pip \
    sqlite3 \
    supervisor \
    apache2 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install flask flask_sqlalchemy gunicorn

RUN wget http://nginx.org/download/nginx-1.19.10.tar.gz && \
    tar zxvf nginx-1.19.10.tar.gz && \
    wget https://github.com/arut/nginx-rtmp-module/archive/v1.2.1.tar.gz && \
    tar zxvf v1.2.1.tar.gz && \
    cd nginx-1.19.10 && \
    ./configure --with-http_ssl_module --add-module=../nginx-rtmp-module-1.2.1 && \
    sed -i 's/-Werror//g' objs/Makefile && \
    make && make install

RUN mkdir -p /usr/local/nginx/html/uploads && \
    mkdir -p /usr/local/nginx/html/hls && \
    mkdir -p /var/log && \
    chmod -R 777 /usr/local/nginx/html && \
    chmod -R 777 /var/log

RUN mkdir -p /usr/local/nginx/html && \
    touch /usr/local/nginx/html/videos.db && \
    chmod 777 /usr/local/nginx/html/videos.db

RUN rm -rf /nginx-1.19.10* && \
    rm -rf /v1.2.1.tar.gz

COPY nginx.conf /usr/local/nginx/conf/nginx.conf

COPY www /usr/local/nginx/html

COPY app.py /app.py

RUN mkdir -p /var/log && \
    touch /var/log/supervisord.log && \
    touch /var/log/nginx.log && \
    touch /var/log/nginx_err.log && \
    touch /var/log/flask.log && \
    touch /var/log/flask_err.log && \
    chmod -R 777 /var/log && \
    chown -R root:root /var/log

RUN mkdir -p /tmp && \
    chmod 777 /tmp

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

RUN mkdir -p /var/log && chmod -R 777 /var/log

RUN mkdir -p /var/log && \
    touch /var/log/flask-gunicorn.log && \
    chmod 666 /var/log/flask-gunicorn.log

EXPOSE 80 1935 5000

ENTRYPOINT ["supervisord", "--nodaemon", "--configuration", "/etc/supervisor/conf.d/supervisord.conf"]