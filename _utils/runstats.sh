#!/bin/bash

# Need to check the total number of tests, total number of suites, tests per suite, total number of keywords, keywords per library

# Firstly, keywords per library and then total

FULL=false

cd ../_documentation



KEYTOT=0
for f in *.html
do
    RET=`grep -o '","name":"' $f | wc -l`
    if $FULL ; then
        echo $f,$RET
    fi
    KEYTOT=$((KEYTOT+$RET))
done
echo TOTAL_KEYWORDS,$KEYTOT



cd ../_utils

# Now count total Tests

cd ../


SUITETOT=`./sqarun.py --list | grep Suite: | wc -l`

echo TOTAL_SUITES,$SUITETOT

TESTTOT=`./sqarun.py --list | grep Test: | wc -l`

echo TOTAL_TESTS,$TESTTOT

cd resources/devices

DEVTOT=`ls -al *.py | wc -l`

echo TOTAL_DEVICES,$DEVTOT



