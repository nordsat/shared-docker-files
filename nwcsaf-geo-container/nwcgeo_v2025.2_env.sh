#/*************************************************************************/
#/**
# * \file nwcgeo_v2025.0_env.sh
# * \brief Definition of environment variables for NWC/GEO vMTG.ORR1 (sh shell)
# *
# *
# * \par Copyright 2024, EUMETSAT, All Rights Reserved
# *
# * \par PRODUCED BY :  GMV Aerospace and Defence S.A.U.
# *                     This SW was developed by GMV within the
# *                     context of the EUMETSAT Satellite Application
# *                     Facility Co-operation Agreement for Support to
# *                     Nowcasting and Very Short Range Forecasting.
# *
# * \par PROJECT     :  NWC SAF
# *
# * \par UNIT NAME   :  NWC/GEO
# *
# * \par FILE        :  nnwcgeo_v2025.0_env.sh
# *
# * \par TYPE        :  template
# *
# * \par FUNCTION    :
# *                     Definition of environment variables for NWC/GEO vmtg.orr1
# *                     under bash, sh or ksh shells
# *
# **************************************************************************/
#/* HISTORY
# *
# *  DATE      VERSION     AUTHOR     REASONS
# * JAN 2022   vmtg.orr1    GMV      First version
# * AUG 2023   v2024        GMV      Updated to v2024.0
# * SEP 2024   v2025        GMV      Updated to v2025.0
# * MAR 2025    v2025        GMV       Updated to v2025
# * JUL 2025    v2025.1      GMV       Updated to v2025.1
# * MAR 2026    v2025.2      GMV       Updated to v2025.2
# **************************************************************************/
#

export TZ='Europe/Copenhagen'

export SAFNWC=/opt
export SAFNWC_CONFIG_DIR=/opt/config
export SAFNWC_EXPORT_DIR=/opt/export
export SAFNWC_IMPORT_DIR=/opt/import
export SAFNWC_LOGS_DIR=/opt/logs
export SAFNWC_TMP_DIR=/opt/tmp

export HDF5_PLUGIN_PATH=$SAFNWC/COTS/hdf5/lib/plugin/
export HDF5_USE_FILE_LOCKING=FALSE

export PATH=$SAFNWC/bin:$SAFNWC/COTS/bin:$PATH
export LD_LIBRARY_PATH=$SAFNWC/COTS/lib:$LD_LIBRARY_PATH
