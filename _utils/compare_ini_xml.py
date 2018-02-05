#!/usr/bin/env python

'''
    compare_ini_xml reports on the differences between the items in two Enable INI XML files.

'''

# Libs to be used
import xml.etree.ElementTree as ET  # Library of XML parsing functions
import os  # Includes functions for file operations
import sys  # Includes functions for reading parameters
import atexit  # Contains Exit handler function
from downloader import download_from_ftp  # FTP download function

__author__ = 'pravey'
__version__ = "1.0"


# Namespace for INI XML files (assuming for now that this the same for all INI files
ns = "http://www.entone.com/ESD/1.0/ESDSchema"

XMLroot = []  # XML objects
XMLtag = []  # XML build version strings
matchedItems = []  # List to be populate with parameters that are in both files. Will be used to identify parameters
# that are in the old file only
summaryCounters = [0, 0, 0]  # No of new only parameters; No of old only parameters; No. of new
# with different default values


def xml_download():  # Downloads XML files specified in command line parameters

    # Read 'New' XML file as parameter
    script_name = os.path.basename(sys.argv[0])
    print "\n%s v%s\n" % (script_name, __version__)

    for my_file in sys.argv:
        if "help" in my_file:
            sys.exit("\nUsage: compare_ini_xml.py <ftp path to new XML INI> <ftp path to old XML INI>")

    sys.argv.pop(0)

    if len(sys.argv) != 2:
        sys.exit("ERROR!: Expecting 2 arguments")

    # Download XML files from FTP addresses
    for myfile in [0, 1]:
        localfile = download_from_ftp(sys.argv[myfile])
        xmlfile = ET.parse(localfile)
        XMLroot.append(xmlfile.getroot())
        for tag in XMLroot[myfile].iter('{%s}tagName' % ns):
            XMLtag.append(tag.text)


def compare_item(name, value):

    # check to see if the Item from the 'New' file is in the 'Old' one by iterating through the list
    for params in XMLroot[1].iter('{%s}param' % ns):
        if params.get('name') == name:
            # If a match is found add it to a list for a later check on the 'old' file
            matchedItems.append(name)

            # Check to see if there is a default value in the 'old' file
            dv = params.find("./{%s}text/{%s}defaultValue" % (ns, ns))
            if dv is not None:
                # If there is an old value then check to see if it matches the new one (if there is one)
                if dv.text != value:
                    if value == '':
                        return "WARNING: New file does not contain default value"
                    else:
                        summaryCounters[2] += 1
                        return "WARNING: OLD default value does not match new!"
                else:
                    return "PASS: Match found"
            elif value == '':
                return "PASS: Match found (no default value)"
            else:
                summaryCounters[2] += 1
                return "WARNING: Only NEW file has a default value"

    summaryCounters[0] += 1
    return 'WARNING: Parameter not found in OLD file'


# Tidy up function called when script terminates
def tidy_up():
    '''
    When this script exits, delete the downloaded XML files.
    '''

    # Delete XML files in current folder
    xmlfiles = [f for f in os.listdir('./') if f.endswith('.xml')]
    for xmlFile in xmlfiles:
        os.remove(xmlFile)


def main():

    atexit.register(tidy_up)  # Register fucntion runon exit that will remove downloaded XML files.

    xml_download()  # Read FTP addresses from arguments and download XML files

    print "\nComparing the XML file from %s to the one in %s\n" % (XMLtag[0], XMLtag[1])

    # Identify the paramster nodes
    params = XMLroot[0].find('{%s}params' % ns)

    # For each parameter node,
    for child in params:
        # get the 'name' and the default value (where available)
        read_item = child.get('name')
        dv = child.find("./{%s}text/{%s}defaultValue" % (ns, ns))
        if not (dv is None):
            read_value = dv.text
        else:
            read_value = ''
        # Call the function that checks for the paramter in the old XML file
        result = compare_item(read_item, read_value)
        print "%s  Default Value: %s Result: %s" % (read_item, read_value, result)

    # Identify parameters only in old file
    params = XMLroot[1].find('{%s}params' % ns)

    print "\nParameters only in %s:" % XMLtag[1]
    for child in params:
        read_item = child.get('name')
        if read_item not in matchedItems:
            summaryCounters[1] += 1
            print read_item

    # Stats summary
    print "\n\nSummary"
    print "=======\n"
    # No of parms in New only
    print "%s has %s new paramters" % (XMLtag[0], summaryCounters[0])
    # No in New with different Default Value
    print "...and %s different default values\n" % (summaryCounters[2])
    # No of parms in Old Only
    print "%s has %s parameters that are not in the new XML file\n" % (XMLtag[1], summaryCounters[1])


# Main code starts here
if __name__ == "__main__":
    main()
