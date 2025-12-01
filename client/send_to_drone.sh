# Script to send code to drone when on the same network
# You will need to enter the password "voxl" after executing the script
# That password is to connect to the drone via SCP

rm -f drone-ui-offline.tar.gz

tar --exclude='.git' \
    --exclude='.idea' \
    --exclude='.vscode' \
    --exclude='.DS_Store' \
    --exclude='send_to_drone.sh' \
    -czf drone-ui-offline.tar.gz .

scp drone-ui-offline.tar.gz voxl@192.168.8.1:/PFE/code

rm -rf drone-ui-offline.tar.gz
