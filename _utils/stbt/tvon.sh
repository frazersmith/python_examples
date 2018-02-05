#!/bin/bash
if [ $# -ne 1 ];
    then echo "USAGE: ./tv.sh x (where x is the highest /dev/videox number)"
    exit 1
fi
for i in $(eval echo {0..$1})
do
    gst-launch-1.0 v4l2src device=/dev/video$i ! autovideosink & >/dev/null 2>&1
done

