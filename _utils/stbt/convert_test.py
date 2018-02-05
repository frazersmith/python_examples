#!/usr/bin/env python
import sys
import os

"""
convert_test.py by Frazer Smith

Takes a test.py file created by 'stbt record' and converts it to Aminorobot syntax for pasting into a testsuite



"""

def usage():
    print "\nconvert_test.py"
    print   "---------------"
    print "\nUsage:-"
    print "\nconvert_test.py INFILE"
    print "--- to convert test.py INFILE and output to screen"
    print "\nconvert_test.py INFILE > OUTFILE.TXT"
    print "--- to convert test.py INFILE and output to file OUTFILE"





if __name__ == "__main__":
    args = sys.argv
    if len(args) <> 2: #No file name passed
        usage()
        exit(1)

    # Read in file
    if not os.path.isfile(args[1]):
        print "\n\nERROR! file not found '%s'" % args[1]
        usage()
        exit(1)

    with open(args[1]) as testfile:
        testfiletext = testfile.read()

    testfilelines = testfiletext.split("\n")

    output = "converted_test_case\n"


    # Convert stbt.press to UUT.Send Keys
    # Convert stbt.wait_for_match to VT.Wait For Match

    for testfileline in testfilelines:
        if testfileline[:15] == "    stbt.press(":
            output += "    UUT.Send Keys    %s\n" % testfileline.split("'")[1]


        if testfileline[:24] == "    stbt.wait_for_match(":
            output += "    VT.Wait For Match    %s\n" % testfileline.split("'")[1]


    print "\n\n"


    for outputline in output.split('\n'):
        print outputline
