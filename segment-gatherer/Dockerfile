FROM registry.access.redhat.com/ubi9/ubi-minimal AS builder

ENV MAMBA_ROOT_PREFIX=/opt/conda
ENV MAMBA_DISABLE_LOCKFILE=TRUE

RUN microdnf update -y && \
    microdnf install -y tar bzip2 && \
    microdnf clean all

COPY environment.yaml /tmp

RUN mkdir /opt/conda && \
    curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj -C /usr/bin/ --strip-components=1 bin/micromamba && \
    micromamba shell init -s bash && \
    mv /root/.bashrc /opt/conda/.bashrc && \
    source /opt/conda/.bashrc && \
    micromamba activate && \
    micromamba install -y -f /tmp/environment.yaml && \
    rm /tmp/environment.yaml && \
    pip cache purge && \
    micromamba remove -y git && \
    # Remove pip, leave dependencies intact
    micromamba remove -y --force pip && \
    # Clean all mamba caches, inluding packages
    micromamba clean -af -y && \
    chgrp -R 0 /opt/conda && \
    chmod -R g=u /opt/conda

FROM registry.access.redhat.com/ubi9/ubi-minimal

COPY --from=builder /opt/conda /opt/conda
COPY --from=builder /usr/bin/micromamba /usr/bin/
COPY entrypoint.sh /usr/bin/

USER 1001
EXPOSE 40000

ENTRYPOINT ["/usr/bin/entrypoint.sh"]
