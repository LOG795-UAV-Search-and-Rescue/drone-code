# Script to send code to drone when on the same network
# You will need to enter the password "voxl" after executing the script
# That password is to connect to the drone via SCP

go mod tidy
go mod vendor

rm -rf drone-code-offline.tar.gz
tar --exclude='.git' \
    --exclude='bin' \
    --exclude='.idea' \
    --exclude='.vscode' \
    --exclude='.DS_Store' \
    --exclude='send_to_drone.sh' \
    -czf drone-code-offline.tar.gz .

scp drone-code-offline.tar.gz voxl@192.168.8.1:/PFE/code
