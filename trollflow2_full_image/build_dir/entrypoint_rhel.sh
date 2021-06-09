#!/bin/bash

# Add local user
# Either use the LOCAL_USER_ID if passed in at runtime or
# fallback

USER_ID=${LOCAL_USER_ID:-9001}

echo "Starting with UID : $USER_ID"
useradd --shell /bin/bash -u $USER_ID -o -c "" -m user
export HOME=/home/user
chown -R ${USER_ID}.${USER_ID} /home/user/
mkdir -p /home/user/.ssh
echo "StrictHostKeyChecking no" >> /home/user/.ssh/config
echo ". /opt/conda/etc/profile.d/conda.sh" >> /home/user/.bashrc && \
echo "conda activate base" >> /home/user/.bashrc
exec gosu user bash -c 'source /home/user/.bashrc && supervisord -c /mnt/config/supervisord.conf'
