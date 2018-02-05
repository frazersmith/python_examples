#!/bin/bash

MOUNTPOINT=/mnt/aminorobotresults
NFS=qa-test2:/var/www/results

# Check if mount already exists
cat /proc/mounts | grep "$NFS $MOUNTPOINT" > /dev/null 2>&1
if [ ! $? -eq 0 ]; then
    echo "The mount point is currently not configured... creating it."
    # Mount does not exist, create it
    if [ -d $MOUNTPOINT ]; then
        echo "Mountpoint folder '$MOUNTPOINT' already exists, checking it's empty..."
        if [ ! "$(ls -A $MOUNTPOINT 2> /dev/null)" == "" ]; then
            echo "FAILED: Mountpoint '$MOUNTPOINT' is not empty!. Exiting"
            exit 1
        fi
    else
        echo "Mountpoint '$MOUNTPOINT' does not exist, creating it..."
        sudo mkdir -p $MOUNTPOINT
    fi
    echo "Creating NFS share '$NFS' at mountpoint '$MOUNTPOINT'..."
    sudo mount -o nolock,tcp,nocto $NFS $MOUNTPOINT
    if [ $? -eq 0 ]; then
        echo "Completed successfully!"
        exit 0
    else
        echo "FAILED: Unable to create mount...(error code returned)"
        exit 1
    fi 
else
    echo "Mount to '$NFS' already exists at '$MOUNTPOINT'"
    exit 0
fi
