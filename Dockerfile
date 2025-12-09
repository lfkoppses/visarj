FROM registry.access.redhat.com/ubi9/python-312:9.7 AS builder

WORKDIR /app

COPY requirements.txt .

USER root

RUN dnf update -y \
    && dnf install -y \
        gcc \
        unixODBC-devel \
        dnf-utils \
    && dnf config-manager --add-repo https://packages.microsoft.com/config/rhel/9/prod.repo \
    && dnf update -y \
    && ACCEPT_EULA=Y dnf install -y msodbcsql17 \
    && dnf clean all \
    && rm -rf /var/cache/dnf

USER 1001 


RUN python -m venv /opt/app-root/src/venv && \
    /opt/app-root/src/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM registry.access.redhat.com/ubi9/python-312:9.7 AS run

USER root

RUN dnf update -y \
    && dnf config-manager --add-repo https://packages.microsoft.com/config/rhel/9/prod.repo \
    && dnf update -y \
    && ACCEPT_EULA=Y dnf install -y msodbcsql17 unixODBC \
    && dnf clean all \
    && rm -rf /var/cache/dnf
    
USER 1001

COPY --from=builder /opt/app-root/src/venv /opt/app-root/src/venv

COPY app.py app.py

ENV PATH="/opt/app-root/src/venv/bin:$PATH"

EXPOSE 8000

CMD ["gunicorn", "app:app", "--workers", "4", "--bind", "0.0.0.0:8000", "--worker-class", "uvicorn.workers.UvicornWorker"]

#docker build -t visarj .
#docker run  --name visarj_api_container  -p 8000:8000  -e DB_USER=sevisa  -e DB_PASSWORD=ASc67jX0ZaP2zS3s -e DB_SERVER=10.42.88.226 -e DB_NAME=Visarj  -e DB_DRIVER="ODBC Driver 17 for SQL Server"  --restart always visarj