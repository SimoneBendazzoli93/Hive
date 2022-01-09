#!/bin/bash

useradd -m -s /bin/bash -u 1000 $user
echo $user":"$password | chpasswd
adduser $user sudo

su $user "/workspace/create_Monai_conda_env.sh"

echo 'source /workspace/.env' >> /home/$user/.bashrc
echo 'export receiver_email='$email >> /home/$user/.bashrc
#pip install git+https://github.com/SimoneBendazzoli93/Hive.git@v1.1
#pip install git+ssh://git@github.com/SimoneBendazzoli93/Hive.git@v1.1
exec "$@"
