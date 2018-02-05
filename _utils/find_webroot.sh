#!/bin/bash

if [[ ! -d "/etc/apache2/sites-available" ]]; then
    echo Error: It looks like apache is not installed!  Please run the Aminorobot install script again
    exit 1
fi

WEBDOC=$(ls /etc/apache2/sites-available | awk "{print $1"} | head -n1)

DOCROOT=$(grep -i 'DocumentRoot' /etc/apache2/sites-available/$WEBDOC | awk -F'\t' '{print $2}' | awk '{print $2}')

echo $DOCROOT
