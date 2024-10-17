FROM ubuntu:22.04 as builder
ENV DEBIAN_FRONTEND noninteractive

SHELL ["/bin/bash", "-c"]
ENV MAMBA_ROOT_PREFIX=/opt/conda

RUN apt-get update
RUN apt-get install -y curl wget bzip2 python3-pip
RUN mkdir /opt/conda && \
    curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj -C /usr/bin/ --strip-components=1 bin/micromamba && \
    micromamba shell init -s bash -p /opt/conda

COPY environment.yaml /tmp
RUN eval "$(micromamba shell hook --shell bash)" && \
    micromamba config append channels conda-forge && \
    micromamba config set channel_priority strict && \
    micromamba activate && \
    micromamba install pip && \
    micromamba install -y -f /tmp/environment.yaml


RUN mv /root/.bashrc /opt/conda/.bashrc
RUN source /opt/conda/.bashrc


RUN chgrp -R 0 /opt/conda && \
    chmod -R g=u /opt/conda

RUN mkdir /app
COPY entrypoint.sh /app
RUN chmod u+x /app/entrypoint.sh


ENTRYPOINT [ "/app/entrypoint.sh" ]

# To use the micromamba env do:
#    eval "$(micromamba shell hook --shell bash)"
#    micromamba activate