#!/bin/bash

# Add local user
# Either use the LOCAL_USER_ID if passed in at runtime or
# fallback

USER_ID=${LOCAL_USER_ID:-9001}

echo "Starting with UID : $USER_ID"
useradd --shell /bin/bash -u $USER_ID -o -c "" -m user
export HOME=/home/user
chown -R ${USER_ID}.${USER_ID} /home/user/
su user -c 'ssh-keygen -f /home/user/.ssh/id_rsa -N ""'
cp /home/user/.ssh/id_rsa.pub /mnt/config/
exec gosu user "$@"
