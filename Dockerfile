FROM python:3.10-alpine AS base

WORKDIR /usr/src/app
RUN apk --no-cache upgrade

FROM base AS builder
# Install build dependencies
# RUN apk --no-cache add make
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

FROM base AS release
# Copy the installed python dependencies from the builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
# Copy the app
COPY --chown=1000:1000 . .

USER 1000:1000
CMD [ "python", "-m", "transmission_influxdb.main" ]
