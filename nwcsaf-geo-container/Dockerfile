FROM ubuntu:24.04 AS builder
RUN apt-get update && apt-get upgrade -y
# install openmp libomp-dev and configure non-interactive
RUN apt-get install -y xz-utils cmake m4 less libfile-ncopy-perl gcc fcc g++ gfortran libhdf5-dev make ksh

RUN mkdir /build
WORKDIR /build

COPY NWC-CDOP4-GEO-AEMET-SW-CODE-SYSTEM_v2025.2_31MAR26.tgz /build
COPY NWC-CDOP4-GEO-AEMET-SW-CODE-COTS_v2025.2_31MAR26.tgz /build
COPY nwcgeo_v2025.2_env.sh /opt



ENV SAFNWC=/opt
ENV CC=gcc
ENV FC=gfortran
ENV TZ='Europe/Copenhagen'
ENV PATH=$SAFNWC/bin:$SAFNWC/COTS/bin:$PATH
ENV LD_LIBRARY_PATH=$SAFNWC/COTS/lib:$LD_LIBRARY_PATH
ENV SAFNWC_IMPORT_DIR=$SAFNWC/import

ENV SAFNWC_CONFIG_DIR=/opt/config
ENV SAFNWC_EXPORT_DIR=/opt/export
ENV SAFNWC_LOGS_DIR=/opt/logs
ENV SAFNWC_TMP_DIR=/opt/tmp

WORKDIR /opt
RUN tar -zxvf /build/NWC-CDOP4-GEO-AEMET-SW-CODE-SYSTEM_v2025.2_31MAR26.tgz
RUN tar -zxvf /build/NWC-CDOP4-GEO-AEMET-SW-CODE-COTS_v2025.2_31MAR26.tgz


WORKDIR /opt/COTS
RUN ./cots.ksh make install

WORKDIR /opt/src

ENV ARCH=linux
ENV CFLAGS="-O3 -fcommon -fopenmp -fpic"
ENV FFLAGS="-O3 -fcommon -fopenmp -fpic"
ENV HDF5_PLUGIN_PATH=$SAFNWC/COTS/hdf5/lib/plugin/
ENV HDF5_USE_FILE_LOCKING=FALSE


RUN ksh ./nwcgeo_v2025.2.ksh make install
WORKDIR /opt/config/MTI1_L1c_PS_RT
RUN make

RUN rm -rf /opt/COTS/packages
RUN mv /opt/COTS/rtbrdf_rttov13 /build/rtbrdf_rttov13
RUN mv /opt/COTS/rtcoef_rttov13 /build/rtcoef_rttov13
RUN mv /opt/COTS/rtemis_rttov13 /build/rtemis_rttov13

FROM ubuntu:24.04

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y xz-utils cmake m4 less libfile-ncopy-perl gcc fcc g++ gfortran libhdf5-dev make ksh && \
    apt-get clean

COPY --from=builder /opt /opt
COPY --from=builder /build/rtbrdf_rttov13 /opt/COTS/rtbrdf_rttov13
COPY --from=builder /build/rtcoef_rttov13 /opt/COTS/rtcoef_rttov13
COPY --from=builder /build/rtemis_rttov13 /opt/COTS/rtemis_rttov13
COPY entrypoint.sh /usr/bin/
RUN chmod u+x /usr/bin/entrypoint.sh
#RUN useradd -ms /bin/bash satops
#USER satops
ENTRYPOINT ["/usr/bin/entrypoint.sh"]
