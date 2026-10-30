FROM postgres:17.9-bookworm
RUN apt-mark hold postgresql-17 \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-17-postgis-3 postgresql-17-postgis-3-scripts \
    && rm -rf /var/lib/apt/lists/*
