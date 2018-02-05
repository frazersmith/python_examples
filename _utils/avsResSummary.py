#!/usr/bin/python

import os
import sys
import subprocess
import time
import re


tc             = ""
initSTBPass    = ""
initSTBFail    = ""
testsPass      = ""
testsFail      = ""
numPkgs        = 0
numInitSTB     = 0
numTests       = 0
numInitSTBPass = 0
numInitSTBFail = 0
numTestsPass   = 0
numTestsFail   = 0
initSTBFails   = ""
testFails      = ""
useInclude     = True

if len(sys.argv) > 1:

    validfile = os.path.isfile(sys.argv[1])
    basename  = os.path.basename(sys.argv[1])
    if validfile == False or basename != "robotdebug.log":
        print("Please specify a path name with robotdebug.log as the file name!")
        sys.exit(1)

    logfile = open(sys.argv[1], 'r')

    for line in logfile:

        if "Include=" in line and useInclude == True:
            numPkgs = numPkgs + 1

        if "Post exclude=" in line:
            if useInclude == True:
                useInclude = False
                numPkgs = 0
            numPkgs = numPkgs + 1

        if "Starting Init_STB for TC" in line:
            regex = r"(TC[0-9]+)"
            match = re.search(regex, line)
            if match:
                tc = match.group(1)
                numInitSTB  = numInitSTB + 1
                initSTBPass = "TC " + tc + " 'Init_STB' has finished with PASS result"
                initSTBFail = "TC " + tc + " 'Init_STB' has finished with FAIL result"
                testsPass   = "TC " + tc + " 'Tests' are finished with PASS result"
                testsFail   = "TC " + tc + " 'Tests' are finished with FAIL result"
                continue
            else:
                print("Unable to determine TC. Aborted!")
                sys.exit(1)

        if "Starting Tests for TC" in line:
            numTests = numTests + 1
            continue

        if tc != "":
            if initSTBPass in line:
                numInitSTBPass = numInitSTBPass + 1
            if initSTBFail in line:
                numInitSTBFail = numInitSTBFail + 1
                initSTBFails = initSTBFails + tc + "\n"
            if testsPass in line:
                numTestsPass = numTestsPass + 1
            if testsFail in line:
                numTestsFail = numTestsFail + 1
                testFails = testFails + tc + "\n"

    logfile.close()

else:
    print("Please specify a path name with robotdebug.log as the file name!")
    sys.exit(1)

####
# Summarise results
####

print("Expected number of pkg/bin to test is: %d") % numPkgs

print("Init_STB: Total=%d, Pass=%d, Fail=%d") % (numInitSTB, numInitSTBPass, numInitSTBFail)
if len(initSTBFails) > 0:
    print("The following init_STB failures have occurred in the order given:")
    print("%s") % initSTBFails

print("Tests:    Total=%d, Pass=%d, Fail=%d") % (numTests, numTestsPass, numTestsFail)
if len(testFails) > 0:
    print("The following Test failures have occurred in the order given:")
    print("%s") % testFails

if numPkgs != numInitSTB:
    print("WARNING: Number of Init_STB reported does not match number of pkg/bin to be tested!")

if numPkgs != numTests:
    print("WARNING: Number of Tests reported does not match number of pkg/bin to be tested!")
