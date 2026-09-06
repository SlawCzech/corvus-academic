# Postgres 16 with pgvector, built on the same Alpine base the project has
# always used.
#
# Two roads not taken:
#   - the official `pgvector/pgvector:pg16` image is Debian-based, and pointing
#     it at an existing musl-built data directory changes the collation
#     provider underneath it, which is how text indexes quietly go wrong;
#   - Alpine's own `postgresql-pgvector` package builds against PG 18, so its
#     `vector.so` lands in a path this server never looks at.
#
# So the extension is compiled against this image's own PG 16 headers.
FROM postgres:16-alpine AS build

ARG PGVECTOR_VERSION=v0.8.0

RUN apk add --no-cache build-base git postgresql16-dev && \
    git clone --branch "${PGVECTOR_VERSION}" --depth 1 \
        https://github.com/pgvector/pgvector.git /tmp/pgvector && \
    cd /tmp/pgvector && \
    make USE_PGXS=1 OPTFLAGS="" with_llvm=no && \
    make USE_PGXS=1 with_llvm=no install


FROM postgres:16-alpine

COPY --from=build /usr/local/lib/postgresql/vector.so /usr/local/lib/postgresql/
COPY --from=build /usr/local/share/postgresql/extension/vector* \
     /usr/local/share/postgresql/extension/
