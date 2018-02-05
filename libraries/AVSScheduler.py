# Import robot libraries
from robot.libraries.BuiltIn import BuiltIn
from robot.version import get_version
from AminorobotLibrary import AminorobotLibrary

# Import python libs
import imp
import os
import ftplib
import threading
import time
import random
from bs4 import BeautifulSoup
import requests
import json

# USS-1671 imports start
import robot.libraries.OperatingSystem as OS
import sys
import subprocess
import re
import pexpect
import string
# USS-1671 imports end

# Import variables
from resources.variables.SWInterop import *

# this is a tab "	"

DEVICE_FILE_PROPERTY_LABELS = 'avs_test_labels'
DEVICE_FILE_PROPERTY_CA = 'ca_supported'
DEVICE_FILE_PROPERTY_MAJOR_SW = 'major_sw_version'
DRYRUN = ''

DEBUG = False

if DEBUG:
    DRYRUN = '--dryrun'

myOS = OS.OperatingSystem()

class AVSScheduler(AminorobotLibrary):

    """
    Amino AVS Scheduler Library by Frazer Smith

    This library is designed for use with Robot Framework.

    An Automated Variant Smoke (AVS) test is a number of small tests that can
    be run against a large number of hardware variants based on their capabilities
    and availability.

    == Implementing an AVS system requires ==
    - A number of HW variants
    - An ESTB definition file for each variant which uses properties to define it's capability
    - The name of this ESTB device file will follow the format:-
    - --> AVS_rr_ss - Where rr = Rack number, ss = Unit number
    - --> NOTE: One Aminorobot instance per Rack.  A max of 24 units per rack
    - ----> so all AVS_01_01 to AVS_01_24 units will be physically attached to one Aminorobot PC
    - Each ESTB needs it's own INI file, served from the same PC as the Aminorobot
    - Each ESTB needs to be served DHCP from the same PC as Aminorobot

   An example of the properties that the ESTB device file needs:-
    | # AVS specific options
    | self.set_property("model_variant","amulet650m")
    | self.set_property("major_sw_version","11")
    | self.set_property("avs_test_labels",("avs_all","avs_moca","avs_4k"))
    | self.set_property("ca_supported",("NoCA","verimatrixCWPP"))

    *NOTES:*
    - 'model_variant' is only for reference (from the HW label)
    - 'major_sw_version' is the first number of the SW version string this HW supports
    - --> e.g. Kamai650 uses 11.x.x
    - 'avs_test_labels' is a list of robot test  labels that can be used ..
    - --> to 'include' tests which the HW supports
    - 'ca_supported' is a list of CA types this HW supports


    The first step is to create an AVS schedule using the `Create Schedule` keyword.

    The output of this keyword is then send to the `Run Schedule` keyword.

    A single shot `Create and Run Schedule` keyword is available to avoid two steps.

    == What is a 'Schedule' ==

    You provide the schedule creator with a URL of a build directory on the ftp site, or an http location with directory listing enabled.

    For example:
    | ${schedule}=	| Create Schedule	| ftp://10.0.4.11/software_release/broadcom/etv/11.7.3_eng1-etv/	| 	| 	|
    | ${schedule}=	| Create Schedule	| http://qa-test2/test/software_release/broadcom/etv/11.7.3_eng1-etv/	| 	| 	|

    It will then produce a list of all .bin files there.  Using arguments in `Create Schedule` you can also
    filter this list by only allowing ones which match a substring ('bininclude') and then removing those which match another (binexclude).

    *NOTE:* a bininclude (if specified) will always be considered first, before an optional binexclude.

    With this list of binfiles it will then work out what major sw version and CA they are.  In
    our example we have '11' SW and 'NoCA, verimatrixCWPP' for CA's.

    It will then create a list of all available hardware which supports those SW and CA needs by reading the device files which start with the chosen hwprefix (defaults to 'avs').

    Next, it reads the test labels that the devices can support from the device files.

    It also works out the middleware, which will be used to choose the test suite to run.

    With all this information a 'Schedule' will be worked out that matches each valid bin against every valid device, creating a matrix of Test Cases (TC)

    At this point the required PBL, BBL and UFS will be determined from the 'resources/variables/SWInterop.py' data file.
    This file will provide a combination of SW elements needed for a Major and Minor combination of SW version number, for example:-

    |    "11.7": {
    |       "bbl": "ftp://10.0.4.11/software_release/broadcom/bbl/11.7.0-bbl/entone_HD_brcm_bbl.11.7.0-bbl.bin",
    |       "pbl": "ftp://10.0.4.11/software_release/broadcom/pbl/11.2.0-pbl/entone_brcm_pbl.11.2.0-pbl.bin",
    |       "ufs": "ftp://10.0.4.11/software_release/broadcom/pbl/11.2.0-ufs/entone_brcm_ufs.11.2.0-ufs.bin"
    |       },

    It will also provide a default for every major version as a fall back.  It is important that this data file is kept up to date and is correct before running an AVS Schedule.

    The schedule creator will then sort these TC's by the device they will run on, as each device will run it's own thread.

    == Logic for choosing and running tests ==

    === Init STB ===

    Every TC consists of two steps:-
    - Init STB
    - Tests

    The Init STB stage takes the bin file for that TC, along with the dependant bootloader elements and pushes that software on to the STB.

    If this stage fails for any reason then no further tests will be run for this TC. Otherwise, as successful Init STB will then lead on to running the chosen tests for this bin/device based on middleware, CA and test labels.

    *NOTE:* For the Init STB stage to work the device file must reference a device specific INI file, for example:-

    | self.set_property("inifile","/var/www/html/ini/AVS_01_05_A611C.ini")

    *NOTE:* All INI files must have the chmod value of 666.  The directory that hosts them must have chmod 777, e.g.:-

    | sudo chmod 666 /var/www/html/ini/AVS_01_05_A611C.ini
    | sudo chmod 777 /var/www/html/ini

    *NOTE:* It is always preferrable to have your UUT's connected to a supported power_ip unit.  If it has a power_ip specified in it's device file
    the Init STB test case will use this instead of a reboot.


    === Middleware ===

    The middleware of the bin will choose the test suites to be run, with the following logic:-
    - All bins will run against the 'all_middleware' suite
    - Minerva bins will also run against the 'mvn' suite
    - All ETV variants will also run against the 'all_etv' suite
    - Specific ETV variants (e.g. 'etv' for the pure etv implementation, 'etv--opera4' for the opera build etc) will run against the variant suite.
    - All ZAPPER variants will also run against the 'all_zapper' suite
    - Specific ZAPPER variants (e.g. 'zapper' for the pure zapper implementation, 'zapper--as3' for the activation server build etc) will run against the variant suite.

    *NOTE:* You will notice the '-vas' and '-nod' elements of the bin name are dropped when deciding on the middleware.  That is because the CA will determine test labels and not test suites.

    *NOTE:* If you are using an ETV or ZAPPER build you must provide a boot argument in the ini file that will not be ignored by robot (i.e. above the ignore line).  Failure will result in a box that boot-loops.

    === Test Cases ===

    Tests from the suites are chosen by test labels and CA labels from the device definition file.

    For example, ["avs_all","avs_moca","avs_4k"] will run all tests from all chosen suites which contain any of those labels.

    == Notes on test creation ==

    Here as some examples of how to ensure the right tests get executed.

    - If your test is independent of middleware put it in the 'all_middleware' suite.
    - If your ETV test is independent of the UI put it in the 'all_etv' suite.
    - If your ZAPPER test is independant of any other optional middleware option put it in the 'all_zapper' suite.
    - If your test relies on support of 4k video playback tag it with the 'avs_4k' label, ensuring the label matches the one used in the device definition file for HW which supports that functionality.

    == Output ==

    The AVS Schedule will output it's progress in the standard folder structure for sqarun tests.  The individual TC's however will have a slightly different path which is created from this information:-

    [aminorobotresults]/[runid]/AVS_Results/[binversion]/[binversion]-[[timestamp]]/.

    For example:-

    ~/aminorobotresults/AVS_FS/AVS_Results/11.7.3_eng1-etv/11.7.3_eng1-etv-[20170113-1223.34]/.....

    If you have your ~/aminorobotresults folder symlinked to your web home (normally /var/www, but could be /var/www/html) the hyperlink provided in the AVS log will work.

    == Timeout ==

    All AVS tests/suites should be created with a timeout value to help stop threads from hanging.  Just in case this is missed, or if a test/suite timeout doesn't trigger, a watchdog 'testtimeout' (defaults to 2 hours) can be chosen when creating the schedule.

    This will be used by the main thread to ensure activity on any device thread has not stopped for that length of time.  If a test lasts longer than testtimeout the following actions will be taken:-
    - The main thread will obtain the PID of the running test
    - The main thread will then ask the test to end gracefully (using sqarun --stop)
    - If this does not happen within 5 seconds, the main thread will then force the process to die (using kill -9), freeing up the device thread to move on to the next TC

    == Rerunning Tests ==

    At the start and end of an AVS run the schedule of tests is output as 'schedule.json', in JSON format.  At the start of the run all test cases will have
    the status 'pending'.  At the end of the run each test case will have a status that represents it's result.

    It is possible to use this schedule.json file as the source input for an AVS run, in conjunction with either 'rerunall' or 'rerunfailures' flags being True/${True}.

    This allows you to repeat exactly the same run as before ('rerunall=True', '-v rerunall:True') -OR- rerun only testcases that did not pass ('rerunfailures=True', '-v rerunfailures:True')

    For example:
    | ${schedule}=	| Create Schedule			| ${path}/schedule.json	| rerunall=${True}		|
    | ${schedule}=	| Create Schedule			| ${path}/schedule.json	| rerunfailures=${True}	|

    - OR -

    | Create and Run Schedule	| ${path}/schedule.json		| rerunfailures=${True}	|

    This list of testcases will start a new AVS run and output it's own schedule.json as before.  This again can be used to kick off a later run of only failures etc.

    == AVS Test Execution, Analysis and Aborting Tests ==

    Detailed notes are available on Confluence on the following pages:

		AVS Smoke Tests: https://confluence.aminocom.com/pages/viewpage.action?pageId=114406052
                AVS Soak Tests:  https://confluence.aminocom.com/pages/viewpage.action?pageId=114406694



    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):
        super(AVSScheduler, self).__init__()
        self.hardware = {}
        self.builtin = BuiltIn()
        self.testtimeout = ''
        # List of CA's to remove from etv and zapper middleware strings
        self.etv_zapper_cas = ["-nod", "-vas", "-ird"]


    def _list_variants(self, *binpaths):
        """
        output csv formatted list of binary variants
        
        """

        varlist = []

        for binpath in binpaths:
            binlist = self._get_binlist(binpath,'','')


            for bin in binlist:

                var = bin[max(bin.find("-mvn-"), bin.find("-etv-"))+1:] # Snip out everything before -mvn- or -etv-
                var = var.rstrip(".bin")
                var = var.rstrip(".DEVBUILD")
                varlist.append(var)

        for bin in sorted(varlist):
            print bin+",,"




    def _get_all_hardware(self, prefix='avs', prefixexcl='', filepath='resources/devices'):

        self._log("Looking for files with prefix '%s' in filepath '%s'" % (prefix, filepath), "debug")

        # Read all python files (source, not compiled) that start with prefix
        files = [f for f in os.listdir(filepath)
                 if (os.path.isfile(os.path.join(filepath, f))
                     and f[:len(prefix)].lower() == prefix.lower() and f[len(f)-2:]=='py')]

        self._log(".... found %s files that match" % str(len(files)),"debug")

        """
        New EXCLUDE filtering start.
        """

        # Log for debug purposes.
        for f in files:
            self._log("hwprefix PRE exclude=%s" % f, "debug")


        # Filter the python file list for all files that need to be excluded.
        if prefixexcl != '': #Filter it
            excllist = prefixexcl.split(' ')

            # This line filters out all python file names that MATCH any of the exclusion strings.
            files = [s for s in files if not any(xs in s.encode('utf-8') for xs in excllist)]

        # Log for debug purposes.
        for f in files:
            self._log("hwprefix POST exclude=%s" % f, "debug")

        """
        New EXCLUDE filtering end.
        """

        self.hardware = {}

        for f in files:
            mod_name = os.path.splitext(os.path.split(f)[-1])[0]

            mod_name_hw_instance = self._load_from_file(os.path.join(filepath, f), mod_name)

            if mod_name_hw_instance is not None:
                self.hardware[mod_name] = mod_name_hw_instance
            else:
                self._log("Tried and failed to load HW device file:- '%s'" % mod_name, "warn")

        return self.hardware

    @staticmethod
    def _load_from_file(filepath, expected_class):
                
        class_inst = None

        mod_name,file_ext = os.path.splitext(os.path.split(filepath)[-1])

        if file_ext.lower() == '.py':
            py_mod = imp.load_source(mod_name, filepath)

        elif file_ext.lower() == '.pyc':
            py_mod = imp.load_compiled(mod_name, filepath)

        if hasattr(py_mod, expected_class):
            class_inst = getattr(py_mod, expected_class)()

        return class_inst

    @staticmethod
    def _filter_hardware_list_on_property(hardware_list, property, value):

        return {k: v for k, v in hardware_list.iteritems() if (v.get_property(property)==value)}

    @staticmethod
    def _filter_hardware_list_on_property_listitem(hardware_list, property, value):

        retlist = {}

        for k, v in hardware_list.iteritems():
            try:
                if value in v.get_property(property):
                    retlist[k] = v
            except:
                pass

        return retlist

    def _read_html_directory(self, url, ext='bin'):

        url = url.strip('/')

        page = requests.get(url).text
        soup = BeautifulSoup(page, 'html.parser')
        #return [url + '/' + node.get('href') for node in soup.find_all('a') if node.get('href').endswith(ext)]
        return [node.get('href') for node in soup.find_all('a') if node.get('href').endswith(ext)]

    def _get_binlist(self, binpath, bininclude, binexclude):


        # return array of bin files at a given bin path
        binlist = []

        if binpath[:6].lower() == "ftp://":

            ftppath = binpath.strip('/').split('/')

            ftpurl = ftppath[2]
            ftppath = '/'.join(ftppath[3:])

            try:
                f = ftplib.FTP(ftpurl)
                f.login()
                f.cwd(ftppath)
                dlist = f.nlst()
                f.close()
            except ftplib.error_perm:
                self.builtin.fail("Unable to reach '%s'" % binpath)


            # Now get list of filenames that end in .bin
            for ea in dlist:
                if ea[-4:] == ".bin":
                    binlist.append(ea)

            if len(binlist) == 0:
                self.builtin.fail("Unable to find any '.bin' files at location '%s'" % binpath)

        elif binpath[:7].lower() == "http://":

            binlist = self._read_html_directory(binpath)

        else:

            self.builtin.fail("You must provide a valid url to the ftp site or http where the binary files can be found.")

        # Filter the binlist for bininclude
        if bininclude != '': #Filter it
            incllist = bininclude.split(' ')

            # This line filters out all package names that DO NOT MATCH any of the inclusion strings.
            binlist = [s for s in binlist if any(xs in s.encode('utf-8') for xs in incllist)]

            # Log for debug purposes.
            for bf in binlist:
                self._log("Include=%s" % bf,"debug")


        # Filter the binlist for binexclude
        if binexclude != '': #Filter it
            excllist = binexclude.split(' ')

            # This line filters out all package names that MATCH any of the exclusion strings.
            binlist = [s for s in binlist if not any(xs in s.encode('utf-8') for xs in excllist)]

            # Log for debug purposes.
            for bf in binlist:
                self._log("Post exclude=%s" % bf, "debug")


        if len(binlist) == 0:
            raise AVSSchedulerError("Filtering produced no results!")
        else:
            return binlist





    def _get_hwlist(self, binelements, prefix, prefixexcl):
        # Take a binelements dict and work out what HW to run it on

        if self.hardware == {}:
            self._get_all_hardware(prefix=prefix,prefixexcl=prefixexcl,filepath='resources/devices' )

        mylist = self._filter_hardware_list_on_property(self.hardware, DEVICE_FILE_PROPERTY_MAJOR_SW, binelements['binfamily'])

        mylist = self._filter_hardware_list_on_property_listitem(mylist, DEVICE_FILE_PROPERTY_CA, binelements['binca'])

        return mylist

    @staticmethod
    def _get_bootloaders(binfile):
        # Take a bin file and return a dict of bootloader elements
        # Tries full version, then first 2, then default
        # e.g. 14.4.5, then 14.4 then 14.default

        binoptions = binfile.split('.')

        # getting the third part of the version string is complex
        # e.g. could be 8_eng2-etv--MVI, or 8-etv--MVI, or 8.1-etv--mvi

        # case 1 - dot release e.g. or 8.1-etv--mvi.  Don't need to do anything
        third_level = binoptions[3]

        #case 2 - eng release e.g. 8_eng2-etv--MVI
        if "_" in third_level:
            third_level = third_level.split('_')[0]

        #case 3 - first release e.g. 8-etv--MVI
        if "-" in third_level:
            third_level = third_level.split('-')[0]

        interop_search1 = "%s.%s.%s" % (binoptions[1], binoptions[2], third_level)

        interop_search2 = "%s.%s" % (binoptions[1], binoptions[2])

        interop_default = "%s.%s" % (binoptions[1], "default")

        if interop_search1 in SWInterop:
            return SWInterop[interop_search1]
        elif interop_search2 in SWInterop:
            return SWInterop[interop_search2]
        elif interop_default in SWInterop:
            return SWInterop[interop_default]
        else:
            raise AVSSchedulerError("No BBL/PBL/UFS found in SWInterop")

    @staticmethod
    def _get_binfile_elements(binfile):

        blank_elements = {
            'binca':'',
            'binfamily':'',
            'binstring':''
        }

        my_elements = blank_elements.copy()

        binoptions = binfile.split('.')

        countback = 2
        if ".DEVBUILD." in binfile:
            countback = 3

        my_elements['binca'] = binoptions[len(binoptions)-countback]

        my_elements['binfamily'] = binoptions[1]


        # Handle Middleware (etv, mvn)
        if ("-etv-" in binfile or "-zapper-" in binfile):
            # Get string based on ETV build layout

            countback = 3
            if ".DEVBUILD." in binfile:
                countback = 4


            if len([s for s in binoptions if "-pbl" in s]): # Check if any of the options has the string -pbl in it
                # Assume this is a compound binary with app and pbl
                for x in range(len(binoptions)-countback, 1, -1):
                    if (len(binoptions[x]) > 4) and ("pbl" not in binoptions[x]):
                        binstring=binoptions[x]
                        break

            else: # Not compound binary with PBL
                binstring = binoptions[len(binoptions)-countback]

            my_elements['binstring'] = binstring[binstring.find("-")+1:]

        elif "-mvn-" in binfile:
            binstring = ''
            for opt in binoptions:
                if '-mvn-' in opt:
                    binstring = opt

            my_elements['binstring'] = binstring[binstring.find("-") + 1:binstring.rfind("-")]

        else:
            raise AVSSchedulerError("Unknown middleware in binary filename '%s'" % binfile)

        return my_elements

    # USS-1025 - Rerun feature
    def _remove_passes(self, schedule):
        # Remove any TC that has a 'Passed' status
        for k in schedule['tclist'].keys():
            if schedule['tclist'][k]['status'] == "Passed":
                del schedule['tclist'][k]

    # USS-1025 - Rerun feature
    def _read_schedule_from_file(self, filename, rerunfailures=False):
        # Read a schedule and return a schedule dictionary
        schedule = {}

        if not os.path.isfile(filename):
            raise AVSSchedulerError("File not found '%s' when reading schedule file." % filename)

        try:
            with open(filename, 'r') as infile:
                schedule['tclist'] = json.load(infile)
        except ValueError:
            raise AVSSchedulerError("Schedule file '%s' is not valid." % filename)

        if rerunfailures:
            # trim out passes
            self._log("Removing 'Passed' results from the schedule.", "info")
            self._remove_passes(schedule)
            if len(schedule['tclist'])==0:
                raise AVSSchedulerError("After removing 'Passed' tests there are none left to run.")

        # Reset all status' to 'pending re-run'
        for tc in schedule['tclist']:
            schedule['tclist'][tc]['status'] = "pending re-run"
            schedule['tclist'][tc]['statustime'] = self.get_timestamp()

        self._insert_tclist_byhw(schedule)
        schedule['binpath']='/'.join(schedule['tclist'].items()[0][1]['binpath'].split('/')[:-1])





        return schedule
    # /USS-1025

    def create_schedule(self, source, bininclude='', binexclude='', hwprefix='avs', hwprefixexcl='', testtimeout='1 hour', test_data=0, rerunfailures=False, rerunall=False):

        """  Create an Automated Variant Smoke (AVS) Schedule

        Giving an ftp directory as the source (and optionally a filter and or a hwprefix to choose hardware from) this
        keyword will return a complex dictionary 'schedule' that can then be run.

        Option argument 'testtimeout' (defaults to 1 hour) gives a timeout for a single test, not the full AVS run

        Additional optional arguments:
        - bininclude - a space separated set of strings to only include bin files that match these strings
        - binexclude - a space separated set of strings to exclude any bin files that match these strings
        - hwprefixexcl - a space separated set of strings to exclude any hardware that match these strings

        For example, if I set the bininclude as 'NoCA' only bin files with 'NoCA' in the string will be included.  If I set the
        bininclude to 'NoCA' and the binexclude to 'sunrise' the list of NoCA will be filters a second time to remove any which
        contain the string 'sunrise'.

        Alternatively, you can use the schedule report from a previous run as the source along with either 'rerunall' or 'rerunfailures' flags
        set to ${True}.  This will allow you to re-run the same TC's as a previous run, either in their entirety or only the ones which did not pass.

        Examples:
        | ${schedule}=	| Create Schedule	| ftp://10.0.4.11/software_release/broadcom/etv/11.7.3_eng1-etv/	| 	| 	|
        | ${schedule}=	| Create Schedule	| ftp://10.0.4.11/software_release/broadcom/etv/11.7.3_eng1-etv/	| hwprefix=AVS_01	| testtimeout=2 hours	|
        | ${schedule}=	| Create Schedule	| ftp://10.0.4.11/software_release/broadcom/etv/11.7.3_eng1-etv/	| hwprefix=AVS_01	| hwprefixexcl='02 03' | testtimeout=2 hours	|
        | ${schedule}=	| Create Schedule	| ftp://10.0.4.11/software_release/broadcom/etv/11.7.3_eng1-etv/	| bininclude='opera'	| 	|
        | ${schedule}=	| Create Schedule	| ftp://10.0.4.11/software_release/broadcom/etv/11.7.3_eng1-etv/	| binexclude='sunrise'	| 	|
        | ${schedule}=	| Create Schedule	| ftp://10.0.4.11/software_release/broadcom/etv/11.7.3_eng1-etv/	| bininclude="nod vas" | binexclude="opera4 pbl" |
        | ${schedule}=	| Create Schedule	| ${path_to_old_run}/Schedule.txt									| rerunfailures=${True}	|

        """

        schedule = {}
        if self.testtimeout=='':
            self.testtimeout = testtimeout


        if rerunall or rerunfailures:
            # This is a rerun using a schedule.json
            if not os.path.isfile(source):
                raise AVSSchedulerError("Can't find the source file '%s' for rerun." % source)

            schedule = self._read_schedule_from_file(source, rerunfailures)

            return schedule


        # Limit the HW scope to the prefix.
        # Defailts to 'AVS' but could be 'AVS_01' etc if we have more than one AVS robot
        schedule["hwprefix"] = hwprefix

        schedule["full_hwlist"] = self._get_all_hardware(prefix=schedule["hwprefix"],prefixexcl=hwprefixexcl,filepath='resources/devices' )

        if len(schedule["full_hwlist"]) == 0:
            self.builtin.fail("Fatal Error: No hardware configs (device files) match the prefix '%s'." % schedule['hwprefix'])


        if test_data > 0:
            # Use test data rather than real data
            from resources.variables.TestData import avs_data
            schedule["binlist"] = avs_data[test_data][1]
            schedule["binpath"] = avs_data[test_data][0]

        else:

            schedule["binpath"] = source
            schedule["binlist"] = self._get_binlist(source, bininclude, binexclude)

        schedule["coveragelist"] = {}

        for binfile in schedule["binlist"]:

            schedule["coveragelist"][binfile] = {}

            schedule["coveragelist"][binfile]["elements"] = self._get_binfile_elements(binfile)
            schedule["coveragelist"][binfile]["bootloaders"] = self._get_bootloaders(binfile)
            schedule["coveragelist"][binfile]["hwlist"] = self._get_hwlist(schedule["coveragelist"][binfile]["elements"],schedule['hwprefix'],hwprefixexcl)

        blank_exec = {
            "tc":"",
            "uut":"",
            "includes":"",
            "middleware":"",
            "binfile":"",
            "bootloaders":{},
            "status":"pending",
            "statustime":"",

        }

        schedule["tclist"] = {}

        counter = 1

        for binfile in schedule["coveragelist"]:

            for hw in schedule["coveragelist"][binfile]['hwlist']:

                tc = "TC%s" % str(counter).zfill(4)

                my_exec = blank_exec.copy()

                # Fill in the specifics for the execution

                my_exec["tc"] = tc

                # Create the uut
                my_exec["uut"] = hw

                # Create the variable binfile
                my_exec["binfile"] = binfile

                # Create the variable binpath
                my_exec["binpath"] = "%s/%s" % (schedule['binpath'].rstrip("/"), my_exec["binfile"])

                # Create the bootloaders dict
                my_exec["bootloaders"] = schedule["coveragelist"][binfile]['bootloaders']

                # Give this a timestamp
                my_exec["statustime"] = self.get_timestamp()

                # Create includes

                my_exec["includes"] = schedule["full_hwlist"][hw].get_property(DEVICE_FILE_PROPERTY_LABELS)

                # Handle CA

                ca_list = schedule["full_hwlist"][hw].get_property(DEVICE_FILE_PROPERTY_CA)

                # Add CS as a label for test selection

                for ca in ca_list:

                    if ca not in my_exec["includes"]:
                        my_exec["includes"].append(ca)

                # Handle Middleware (etv, mvn)

                mw = schedule["coveragelist"][binfile]['elements']['binstring']
                if mw.startswith("mvn"):
                    mw = "mvn"
                elif mw.startswith("etv") or mw.startswith("zapper"):
                    # Strip out the CA for etv builds, use labels for that
                    for ca in self.etv_zapper_cas:
                        if ca in mw:
                            mw = ''.join(mw.split(ca))
                            break

                else:
                    raise AVSSchedulerError("Unknown middleware '%s'" % mw)

                my_exec["middleware"] = mw

                schedule["tclist"][tc] = my_exec

                my_exec = None

                counter += 1


        self._insert_tclist_byhw(schedule)

        return schedule

    # USS-1025 - Rerun feature
    # Split out the tclist_byhw so a tclist read from file can also create one
    def _insert_tclist_byhw(self, schedule):

        # Now sort by HW platform to properly queue the threads

        schedule['tclist_byhw'] = {}


        for tc in schedule['tclist']:
            uut = schedule['tclist'][tc]['uut']
            if uut in schedule['tclist_byhw'].keys():
                schedule['tclist_byhw'][uut]['tests'].append(schedule['tclist'][tc])
            else:

                schedule['tclist_byhw'][uut] = {}
                schedule['tclist_byhw'][uut]['thread'] = None
                schedule['tclist_byhw'][uut]['tests'] = [schedule['tclist'][tc],]
    # /USS-1025


    def create_and_run_schedule(self, source, bininclude='', binexclude='', hwprefix='avs', hwprefixexcl='', testtimeout='1 hour', test_data=0, rerunfailures=False, rerunall=False ):
        """

        `Create Schedule` followed immediately by `Run Schedule`

        """

        schedule = self.create_schedule(source, bininclude, binexclude, hwprefix, hwprefixexcl, testtimeout, test_data, rerunfailures, rerunall)
        self.run_schedule(schedule)


    def _is_hw_free(self, hw):
        # Take a UUT name and check if it is available
        # by scanning the running sqarun instances
        # returns True or False
        # Check twice with a random gap to avoid race conditions

        delta = random.randint(100, 300)

        ret = True

        for x in range (0,2):

            running_tasks = os.popen("ps aux --columns 10000| grep pybot | grep -v grep").read() # json.loads(myarb.view_running_tasks(returntype='json'))

            if "--variable uut:%s" % hw in str(running_tasks):
                ret = False

            time.sleep(delta/100)

        return ret

    def _get_outputdir(self, schedule):
        binpath = schedule['binpath'].rstrip('/').rsplit('/', 1)[-1]
        ts = time.strftime("[%Y%m%d-%H%M.%S]")
        runid = self._get_runid()

        return "%s/AVS_Results/%s/%s-%s" % (runid, binpath, binpath, ts)

    def _get_runid(self):
        outdir = self._get_schedule_outputdir()
        runid="/tmp"
        parts = outdir.split('/')
        if len(parts) > 2:
            #Not in /tmp
            runid = parts[-3:][0]

        return runid

    def _get_schedule_outputdir(self):
        try:
            avsoutdir = BuiltIn().replace_variables('${OUTPUTDIR}')
        except:
            avsoutdir = "/tmp"

        return avsoutdir

    # USS-1025 - Rerun feature
    def _write_schedule_to_file(self, schedule):

        avsoutdir = self._get_schedule_outputdir()

        # Save output as JSON
        with open("%s/schedule.json" % avsoutdir, "w") as fout:
            json.dump(schedule['tclist'], fout, indent=4)
    # /USS-1025

    def run_schedule(self, schedule):
        # Step through each TC in the tclist
        # If its running, check if it's done
        # If it's not, run it
        """

        This will take the output of the `Create Schedule` keyword and start running it.  There are no arguments.

        Example:
        | Run Schedule  | ${schedule}  |

        """
        if len(schedule['tclist']) == 0:
            # No tests to run
            raise AVSSchedulerError("The schedule contains no tests!")

        # USS-1025 - Rerun feature
        self._write_schedule_to_file(schedule)
        # /USS-1025

        schedule['outputdir'] = self._get_outputdir(schedule)


        hyperlink = ("*HTML* This is a link <a href=http://%s/aminorobotresults/%s>"
                                      % (os.uname()[1],schedule['outputdir'] ) +
                                      "to all AVS test cases for this run.</a>" +
                                      "\n(NOTE: Your ~/aminorobotresults directory must be symlinked to " +
                                      "your /var/www for this to work)" )
        print hyperlink

        self.builtin.set_test_message(hyperlink)

        schedule['infomessages'] = []
        schedule['warnmessages'] = []
        schedule['overallresult'] = ['Passed']

        exit_mainloop = False
        tclist_byhw = schedule['tclist_byhw']

        # Clear all threads, or throw an error if any are still running
        if self._check_threads_running(schedule):
            raise AVSSchedulerError("Threads in this schedule are still running!  Exiting run_schedule")

        for uut in tclist_byhw:
            tclist_byhw[uut]['thread'] = None
            tclist_byhw[uut]['threadstatus'] = 'Pending'
            tclist_byhw[uut]['threadstatus_ts'] = None
            tclist_byhw[uut]['threadfails'] = 0

        # Main loop
        while not exit_mainloop:

            # Start/check threads
            for uut in tclist_byhw:
                # Step through each uut
                # Check if it has a thread
                if tclist_byhw[uut]['thread'] is None:
                    # Check the HW is available
                    if self._is_hw_free(uut):
                        # If it is, start the thread
                        tclist_byhw[uut]['thread'] = threading.Thread(target=self._run_uut_thread, args=(schedule, uut))
                        tclist_byhw[uut]['threadstatus'] = "Running:None"
                        tclist_byhw[uut]['thread'].start()

                        self._log("Starting UUT thread for %s." % uut, "info")
                    else:
                        # Otherwise report that it's blocked on HW availability
                        if tclist_byhw[uut]['threadstatus'] != "HWBlocked":
                            # Change in state, report it
                            self._log("Unable to start UUT thread for %s as it is in use by another sqarun process." % uut, "info")
                        tclist_byhw[uut]['threadstatus'] = "HWBlocked"
                    # Update the status_ts
                    tclist_byhw[uut]['threadstatus_ts'] = time.time()
                else:
                    # This uut has a thread object
                    # Check if it has changed state
                    if not tclist_byhw[uut]['thread'].is_alive() and tclist_byhw[uut]['threadstatus'][:7] == "Running":
                        tclist_byhw[uut]['threadstatus'] = "Finished"
                        tclist_byhw[uut]['threadstatus_ts'] = time.time()

                        if tclist_byhw[uut]['threadfails'] == 0:
                            self._log("UUT thread for %s has finished with an overall 'Passed' result." % uut, "info")
                        else:
                            self._log("UUT thread for %s has finished with %s 'Failed' tests." % (uut, str(tclist_byhw[uut]['threadfails'])), "warn")


            # Check if any messages are waiting to be dealt with
            self._output_messages(schedule)

            # Check if we can exit the mainloop
            if not self._check_threads_running(schedule):
                time.sleep(5)
                self._output_messages(schedule)
                time.sleep(5)
                self._log("All threads are now done!", "info")
                exit_mainloop = True
            else:

                # Need to check how long each current test has been running in the threads
                timeout = self.convert_time_to_secs(self.testtimeout)
                for uut in tclist_byhw:
                    # Use threadstatus_ts against a specified timeout
                    if (time.time() - tclist_byhw[uut]['threadstatus_ts']) > timeout and tclist_byhw[uut]['thread'].is_alive():
                        # if it's too long try to use sqarun stop (after getting pid for the UUT)
                        tctext = tclist_byhw[uut]['threadstatus'].split(":")[1]
                        self._log("TC '%s' on UUT '%s' has exceeded the timeout '%s'.  Attempting to stop it..."
                                    % (tctext,
                                       uut,
                                       self.testtimeout), "warn")
                        try:
                            pid = (os.popen("./sqarun.py --view | grep 'uut:%s'" % uut).read()).split()[0]
                        except IndexError:
                            self._log("Unable to get PID for TC '%s' on UUT '%s' has exceeded the timeout '%s'.  Dropping out."
                                        % (tctext,
                                           uut,
                                           self.testtimeout),"warn")
                            self.builtin.fatal_error("Thread hung")
                        ret = os.system("./sqarun.py --stop %s" % str(pid))
                        if ret!=0:
                            self._log(
                                "Unable to 'stop' TC '%s' on UUT '%s' using PID '%s'.  Killing PID..."
                                % (tctext,
                                   uut,
                                   str(pid)), "warn")
                            ret = os.system("sudo kill -9 %s" % str(pid))

                            if ret != 0:
                                self._log(
                                    "Unable to kill TC '%s' on UUT '%s' using PID '%s'.  Dropping out."
                                    % (tctext,
                                       uut,
                                       str(pid)),"warn")
                                self.builtin.fatal_error("Thread hung")
                            else:
                                self._log("Killed TC '%s' on UUT '%s' using PID '%s'."
                                            % (tctext,
                                               uut,
                                               str(pid)),"warn")

                        else:
                            self._log("Stopped TC '%s' on UUT '%s' using PID '%s'."
                                        % (tctext,
                                           uut,
                                           str(pid)),"warn")

                # then throw a fail and continue using the TC number in threadstatus (split :)
                time.sleep(10)

        # Main loop exited

        # USS-1025 - Rerun feature
        self._write_schedule_to_file(schedule)
        # /USS-1025

        if schedule['overallresult'] == 'Failed':

            self.builtin.fail("AVS Schedule failed.")

    def _output_messages(self, schedule):
        # Check if any messages are in the queue, and output them
        info = schedule['infomessages']
        schedule['infomessages'] = []
        warn = schedule['warnmessages']
        schedule['warnmessages'] = []

        for msg in warn:
            self._log(msg, "warn")

        for msg in info:
            self._log(msg, "info")

    ########
    # Start of code for USS-1671.
    ########

    ####
    # _look4PkgInSdkDirs
    #
    # Finds the directory where the package file resides.
    #
    #
    # Returns valid path to directory where package file resides.
    ####
    def _look4PkgInSdkDirs(self, rSshUserIP, rPasswd, dirs, pName, schedule):

        path = ''

        tmp1 = dirs.split('\r\n')

        for thisDir in tmp1:
            self._info("_look4PkgInSdkDirs: this dir: %s" % (thisDir), schedule)
            if 'txt-as3' in thisDir:
                thisDir = thisDir.rstrip('\n')
                cmdB =" 'ls " + thisDir + "/pkg*bin'"
                cmdC = rSshUserIP + cmdB
                cpwd = rPasswd + '\n'
                (cmd_output) = pexpect.run(cmdC, events={'(?i)password':cpwd})
                self._info("_look4PkgInSdkDirs: cmd_output: %s" % (cmd_output), schedule)

                tmp2 = cmd_output.split('\r\n')
                for thisPkg in tmp2:
                    self._info("_look4PkgInSdkDirs: this pkg: %s" % (thisPkg), schedule)
                    if pName in thisPkg:
                        self._info("_look4PkgInSdkDirs: found pkg!: %s" % (thisPkg), schedule)
                        path = thisDir
                        self._info("_look4PkgInSdkDirs: using path: %s" % (path), schedule)
                        return path

        ####
        # If we get here then we've failed to identify directory
        # where Pkg resides!
        ####
        return path
       
    ####
    # _getConfigFile
    #
    # Finds the build config file by searching the Build Server directories until package is found.
    #
    #
    # Returns valid path to config file that has been scp'd from build server. Otherwise returns empty
    # string if failed.
    ####

    def _getConfigFile(self, pcIP, uName, pcPwd, rSshUserIP, rPasswd, bRelease, pName, uut, schedule):

        ####
        # Make pathname to search for sdk directories.
        # Then do an 'ls -d' to list directories of interest.
        # The output of this 'ls -d' is passed to a function which searches
        # directories of interest for the package name being sought.
        ####

        sdkDirs = '/home/build/broadcom/' + bRelease + '/brcm_rootfs/entone-sdk-package*.txt-as3'
        cmdB =" 'ls -d " + sdkDirs + "'"
        cmdC = rSshUserIP + cmdB
        cpwd = rPasswd + '\n'
        self._info("_getConfigFile: Listing dirs using: %s" % (cmdB), schedule)

        (cmd_output) = pexpect.run(cmdC, events={'(?i)password':cpwd})
        self._info("_getConfigFile: cmd_output: %s" % (cmd_output), schedule)

        ####
        # Get directory path where pkg resides from directories of interest.
        # Then isolate config file name by extracting it from the returned directory
        # path.
        ####
        path = self._look4PkgInSdkDirs(rSshUserIP, rPasswd, cmd_output, pName, schedule)
        if path == '':
            self._warn("_getConfigFile: Failed to get path of interest!", schedule)
            return ""
        self._info("_getConfigFile: path of interest: %s" % (path), schedule)

        match = None
        if bRelease.endswith("-mvn"):
            regex = r"[0-9]\-([0-9a-zA-Z_\-\.]+\.txt)-as3"
            match = re.search(regex, path)
            mindex = 1
        elif bRelease.endswith("-etv"):
            regex = r"(NoCA|CWPP|CWPPUB|irdeto)\-([a-zA-Z0-9_\-]+\.txt)-as3"
            match = re.search(regex, path)
            mindex = 2
        elif bRelease.endswith("-zapper"):
            regex = r"(NoCA|CWPP|CWPPUB|irdeto)\-([a-zA-Z0-9_\-]+\.txt)-as3"
            match = re.search(regex, path)
            mindex = 2

        if match != None:
            self._info("_getConfigFile: isolated config file: %s" % (match.group(mindex)), schedule)
        else:
            self._warn("_getConfigFile: Failed to isolate config file!", schedule)
            return ""

        ####
        # Get config file.
        # Dest cfg file needs '<uut>' in name to distinguish it!!!!
        # e.g. AVS_01_05_<confignamefrom match>
        ####
        self._info("_getConfigFile: scp config file to Robot PC... ", schedule)
        cfgPath = path + "/sdk_config/" + match.group(mindex)

        myCfgPath = "/home/" + uName + "/" + uut + "_" + match.group(mindex)
        cmdB ="scp " + cfgPath + " " + uName + "@" + pcIP +  ":" + myCfgPath 

        ssh_newkey = 'Are you sure you want to continue connecting'

        self._info("_getConfigFile: spawning ssh session... ", schedule)
        # expLogFile is used to capture expect output in case of problems.
        # There might be room for improvement here if the connection fails
        # and it might require a 'repeat' loop?
        expLogFile =  "/tmp/" + uut + "_expect.log"
        child = pexpect.spawn(rSshUserIP)
        child.logfile = open(expLogFile, "w")

        # ssh into Build Server.
        i = child.expect([ssh_newkey, r"password:", pexpect.EOF, pexpect.TIMEOUT])
        if i==0:
            # First time connection to build server.
            child.sendline('yes')
            i = child.expect([ssh_newkey, r"password:", pexpect.EOF, pexpect.TIMEOUT])
        if i==1:
            child.sendline(rPasswd)
            child.expect([r"]$", pexpect.EOF, pexpect.TIMEOUT])
        elif i==2:
            self._warn("getConfigFile: key or connection timeout!", schedule)
            return ""
        elif i==3:
            self._warn("getConfigFile: connection timeout!", schedule)
            return ""

    
        # Issue scp command for copying Build Config file to Robot PC.
        self._info("_getConfigFile: Using scp command: %s" % (cmdB), schedule)
        child.sendline(cmdB)
        child.expect([r"password:", pexpect.EOF, pexpect.TIMEOUT])
        child.sendline(pcPwd)

        # Get here if scp command was successful.
        self._info("_getConfigFile: scp command success.Exiting ssh session... ", schedule)
        child.sendline('exit')
        child.expect(pexpect.EOF)

        return myCfgPath

    ####
    # _createComponentDict
    #
    # cfgFile  Path name to configuration file obtained previously.
    #
    # Creates a dictionary file based on the build components of interest for use with
    # the AVS Robot scripts.
    #
    # Returns path to dictionary file so that it can be saved later in appropriate 'results' folder.
    ####

    def _createComponentDict(self, cfgFile, uut, schedule):

        ####
        # Process the config file to create a dictionary
        # for the components of interest.
        ####
        self._info("_createComponentDict: Creating component dictionary file: %s" % (cfgFile), schedule)
        compdict = "compdict= {\n"
        cline = ''
        fcfg = open(cfgFile, 'r')
        for line in fcfg:
            if len(cline) != 0:
                compdict = compdict + cline + ',\n'
            if line.startswith("EMP="):
                if "NONE" in line:
                    cline = "'EMP':'NONE'"
                elif "AGAMA" in line:
                    cline = "'EMP':'AGAMA'"
                else:
                    cline = "'EMP':'unknown'"
            elif line.startswith("DRM_TYPE="):
                if "NoCA" in line:
                    cline = "'DRM':'nod'"
                elif "verimatrix" in line:
                    cline = "'DRM':'vas'"
                elif "irdeto" in line:
                    cline = "'DRM':'ird'"
                else:
                    cline = "'DRM':'unknown'"
            elif line.startswith("YOUTUBE="):
                if "YES" in line:
                    cline = "'YOUTUBE':'YES'"
                elif "NO" in line:
                    cline = "'YOUTUBE':'NO'"
                else:
                    regex = r"[0-9]+"
                    match = re.search(regex, line)
                    if match:
                        self._info("_createComponentDict: YOUTUBE line does not conform! Line: %s" % (line), schedule)
                        cline = "'YOUTUBE':'YES'"
                    else:
                        cline = "'YOUTUBE':'unknown'"
            elif line.startswith("VUDU="):
                if "YES" in line:
                    cline = "'VUDU':'YES'"
                elif "NO" in line:
                    cline = "'VUDU':'NO'"
                else:
                    cline = "'VUDU':'unknown'"
            elif line.startswith("VQE="):
                if "YES" in line:
                    cline = "'VQE':'YES'"
                elif "NO" in line:
                    cline = "'VQE':'NO'"
                else:
                    regex = r"[0-9]+"
                    match = re.search(regex, line)
                    if match:
                        self._info("_createComponentDict: VQE line does not conform! Line: %s" % (line), schedule)
                        cline = "'VQE':'YES'"
                    else:
                        cline = "'VQE':'unknown'"
            elif line.startswith("BROWSER="):
                if "qtwebkit" in line:
                    cline = "'BROWSER':'webkit'"
                elif "opera" in line:
                    cline = "'BROWSER':'opera4'"
                else:
                    cline = "'BROWSER':'unknown'"
            elif line.startswith("ACS="):
                if "YES" in line:
                    cline = "'ACS':'YES'"
                elif "NO" in line:
                    cline = "'ACS':'NO'"
                else:
                    cline = "'ACS':'unknown'"
            elif line.startswith("CUSTOMER="):
                if "=\"\"" in line:
                    cline = "'CUSTOMER':'default'"
                else:
                    regex = r"CUSTOMER\=\"([a-zA-Z0-9_-]+)\""
                    match = re.search(regex, line)
                    cline = "'CUSTOMER':'" + match.group(1) + "'"
            elif line.startswith("BROADPEAK_NANOCDN="):
                if "YES" in line:
                    cline = "'NANOCDN':'YES'"
                elif "NO" in line:
                    cline = "'NANOCDN':'NO'"
                else:
                    cline = "'NANOCDN':'unknown'"
            else:
                cline = ''

        fcfg.close()
        if len(cline) != 0:
            compdict = compdict + cline + '\n'
        compdict = compdict + "}\n"
        compdict = compdict.replace(",\n}","\n}")

        self._info("_createComponentDict: Dictionary: %s" % (compdict), schedule)

        ####
        # Store the dictionary that has been created in
        # a file in the git aminorobot resources/variables/<UUT>_avs_build_comps.py
        # This will be used by the various robot test scripts.
        # Will need a property that gives AVS_01_05 for UUT in actual Robot script!!!!
        ####
        robotBuildComps = os.getenv('HOME') + "/git_repos/aminorobot/resources/variables/" + uut + "_avs_build_comps.py"
        self._info("_createComponentDict: Creating Component Dictionary file: %s" % (robotBuildComps), schedule)

        frobotBC = open(robotBuildComps, 'w')
        frobotBC.write(compdict)
        frobotBC.close()

        return robotBuildComps
    
    ####
    # _getBuildServer
    #
    # bRelease e.g. '11.7.32_build5-mvn'
    #
    # Returns build server <username>@<ip of bs> if successful. Otherwise returns empty string for build server.
    ####

    def _getBuildServer(self, bRelease, bSVRUSERIPs, bSVRpwd, schedule):

        ####
        # Loop through build servers and check that 'bRelease' directory exists.
        # Returns the build server as soon as it is found.
        ####
        for bsvr in bSVRUSERIPs:

            self._info("_getBuildServer: Checking Build Server: %s" % (bsvr), schedule)
            bServerSshUserIP = 'ssh ' + bsvr
            sdkDirs = '/home/build/broadcom/' + bRelease + '/*'

            cmdB =" 'ls -d " + sdkDirs + "'"
            cmdC = bServerSshUserIP + cmdB
            bSVRpwd = bSVRpwd + '\n'

            (cmd_output) = pexpect.run(cmdC, events={'(?i)password':bSVRpwd})
            self._info("_getBuildServer:DEBUG: cmd_output: %s" % (cmd_output), schedule)

            # Convert cmd_output string into a list of lines.
            outLines = cmd_output.split('\r\n')
            for oline in outLines:
                # First check MUST be for 'no such...'
                # If true, go immediately to next build server check.
                if "No such file or directory" in oline:
                    break

                # If 'bRelease' seen in output we've got the right build server!
                if bRelease in oline:
                    self._info("_getBuildServer:Build Server identified is %s" % (bsvr), schedule)
                    return bsvr

        ####
        # If we get here we've failed to find the build server!
        # Return empty string.
        ####
        self._warn("_getBuildServer:Failed to determine Build Server to use!", schedule)
        bsvr = ''
        return bsvr

    ####
    # _getConfigFromBuildServer
    #
    # uut      e.g. 'AVS_01_05'
    # bRelease e.g. '11.7.32_build5-mvn'
    # pkgName  e.g. 'pkg_entone_hd_brcm_bin.11.7.32_build5-mvn-nod--tr069--qtwebkit--as3-5.7.5.118.NoCA.DEVBUILD.bin'
    # schedule :    for thread.
    #
    # Assumes build server has already established ssh to build servers and scp to Robot PC from build servers!!!
    #
    # Returns True if successful and path to cfgFile and dictionary file for later storage. Otherwise returns False.
    ####

    def _getConfigFromBuildServer(self, uut, bRelease, pkgName, schedule):

        # Currently same password is used for all Build Servers.
        bSVRUserIPs     = ['build@192.168.1.252', 'build@192.168.1.253']
        bServerpassword = 'build!@#'

        ####
        # Determine which build server to use.
        ####
        self._info("_getConfigFromBuildServer:Determining which Build Server to use. .. ", schedule)
        bServerUserIP = self._getBuildServer(bRelease, bSVRUserIPs, bServerpassword, schedule)
        if bServerUserIP == "":
            self._warn("_getConfigFromBuildServer:Failed to get a Build Server to use - check available Build Servers manually!!", schedule)
            return (False,"","")
        self._info("_getConfigFromBuildServer:Build Server to be used is: %s" % (bServerUserIP), schedule)

        bServerSshUserIP = 'ssh ' + bServerUserIP
        bServerpassword = 'build!@#'
        #ssh_newkey = 'Are you sure you want to continue connecting'

        ####
        # Get IP address of this PC.
        # This is used in scp of build config file to Robot PC.
        ####
        self._info("_getConfigFromBuildServer:Getting IP address of Robot PC... ", schedule)
        cmd = [r'ifconfig | egrep -m 1 "inet addr"']
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        tmp = p.communicate()
        regex = r"inet addr\:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        match = re.search(regex, tmp[0])
        PCIPaddr = match.group(1)
        self._info("_getConfigFromBuildServer:IP address of Robot PC is %s" % (PCIPaddr), schedule)

        ####
        # Get username of Robot PC.
        ####
        self._info("_getConfigFromBuildServer:Getting username of Robot PC... ", schedule)
        cmd = [r'whoami']
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        tmp = p.communicate()
        username = tmp[0].rstrip('\n')
        if username != "validation":
            self._warn("_getConfigFromBuildServer:Incorrect username/account in use: %s" % (username), schedule)
            return (False,"","")
        self._info("_getConfigFromBuildServer:Username of Robot PC account is: %s" % (username), schedule)

        # Password assumes 'validation' account!
        thisPCpwd = 'val4Test'

        ####
        # Get build configuration file from the build server.
        ####
        self._info("_getConfigFromBuildServer:Getting Build Config file from Build Server... ", schedule)
        cfgFile = self._getConfigFile(PCIPaddr, username, thisPCpwd, bServerSshUserIP, bServerpassword, bRelease, pkgName, uut, schedule)
        if cfgFile == "":
            self._warn("_getConfigFromBuildServer:Failed to obtain a build config file! Manually check Build Server!", schedule)
            return (False,"","")
        self._info("_getConfigFromBuildServer:Build Config file path is: %s" % (cfgFile), schedule)

        ####
        # Create a dictionary for the components to be included/excluded
        # from the config file that has been obtained.
        ####
        self._info("_getConfigFromBuildServer:Creating dictionary... ", schedule)
        dictFile = self._createComponentDict(cfgFile, uut, schedule)

        return (True, cfgFile, dictFile)



    def _run_uut_thread(self, schedule, uut):

        tests = schedule['tclist_byhw'][uut]['tests']

        for tc in tests:

            outputdir = "%s/%s" % (schedule['outputdir'], tc['tc'])

            tcdetails = "TC %s on UUT %s against BINFILE %s" % (tc['tc'],uut, tc['binfile'])

            # Set up this UUT with the correct BINFILE

            self._info("TC %s output directory is '[aminorobotresults]/%s'" % (tc['tc'], outputdir), schedule)
            self._info("Starting Init_STB for %s." % tcdetails, schedule)


            schedule['tclist_byhw'][uut]['threadstatus'] = "Running:%s Init_STB" % tc['tc']
            schedule['tclist_byhw'][uut]['threadstatus_ts'] = time.time()

            tc['status']="Running Init_STB"
            tc['statustime'] = self.get_timestamp()
            init_variables = "-v app:%s -v bbl:%s -v pbl:%s -v ufs:%s" % (
                        tc['binpath'],
                        tc['bootloaders']['bbl'],
                        tc['bootloaders']['pbl'],
                        tc['bootloaders']['ufs'])

            initcommand = "./sqarun.py -p -r %s/Init_STB -u %s -s AVS -t Init_STB %s %s > /dev/null 2>&1" % (outputdir, uut, init_variables, DRYRUN)
            ret = os.system(initcommand)

            self._info("TC %s 'Init_STB' has finished with %s result." % (tc['tc'], ("PASS" if ret==0 else "FAIL") )
                       , schedule)

            if ret != 0:
                # FAILED to init STB

                self._warn("** FATAL ERROR ** - %s has failed to Init_STB!" % tcdetails, schedule)
                self._fail_schedule(schedule)

                tc['status'] = "Failed Init_STB"
                tc['statustime'] = self.get_timestamp()

                schedule['tclist_byhw'][uut]['threadfails'] += 1
            else:
                # Safe to start main test
                tc['status'] = "Running Tests"
                tc['statustime'] = self.get_timestamp()

                schedule['tclist_byhw'][uut]['threadstatus'] = "Running:%s Tests" % tc['tc']
                schedule['tclist_byhw'][uut]['threadstatus_ts'] = time.time()


                # USS-1671 Start
                #outputdir = "AVS/AVS_Results/14.7.33_build5-mvn/14.7.33_build5-mvn-[20171219-0907.19]/TC0009"
                regex = r"Results\/(\d{1,2}\.\d{1,2}\.\d{1,2}(\_build|\.\d{1,2}\_build)\d{1,2}\-(mvn|etv|zapper))\/"
                match = re.search(regex, outputdir)
                bRelease = match.group(1)
                pkgName = tc['binfile']

                self._info("TC %s 'Get Build Config file: UUT=%s\nBRelease=%s\nPkg=%s\n" % (tc['tc'], uut, bRelease, pkgName), schedule)
                (retStatus, cfgFile, dictFile) = self._getConfigFromBuildServer(uut, bRelease, pkgName, schedule)
                if retStatus == False:
                    self._warn("** FAIL ** - %s has failed to get build config info." % tcdetails, schedule)
                    self._fail_schedule(schedule)
                    tc['status'] = "Failed Tests"
                    tc['statustime'] = self.get_timestamp()
                    schedule['tclist_byhw'][uut]['threadfails'] += 1
                    # Try next tc in main for loop.
                    continue
                # USS-1671 End
                    

                # Build execution string for sqarun
                includes = ''
                for include in tc['includes']:
                    includes += "-i %s " % include

                # Handle all etv or all zapper
                all_arg = ''
                if tc['middleware'][:3].lower()=="etv":
                    all_arg = "-s all_etv"
                elif tc['middleware'][:6].lower()=="zapper":
                    all_arg = "-s all_zapper"

                runcommand = "./sqarun.py -p -r %s/Tests -u %s -s avs.all_middleware -s avs.%s %s %s -e Init_STB %s > /dev/null 2>&1" % \
                            (outputdir,
                             uut,
                             tc['middleware'],
                             all_arg,
                             includes,
                             DRYRUN)

                self._info("Starting Tests for %s using run command:-\n'%s'" % (tcdetails, runcommand), schedule)

                # launch sqarun in foreground mode

                ret = os.system(runcommand)

                self._info(
                    "TC %s 'Tests' are finished with %s result." % (tc['tc'], ("PASS" if ret == 0 else "FAIL"))
                    , schedule)

                # USS-1671 Start

                # Get the results directory and copy the cfgFile and dictFile here.
                resDir = outputdir
                #resDir = resDir.replace("[", "/",1)
                #resDir = resDir.replace("]", "",1)
                resDir = os.getenv('HOME') + "/aminorobotresults/" + resDir + '/Tests'

                # Gets the next two sub-directories for the results path name.
                self._info("DEBUG:resDIR=%s" % (resDir), schedule)
                for dirName, subdirList, fileList in os.walk(resDir):
                    resDir = dirName
                    self._info("DEBUG:resDir=%s" % (resDir), schedule)

                self._info("DEBUG:resDIR=%s" % (resDir), schedule)

                # now cp/mv the 2 files to resDir
                # DO NOT USE variable 'ret' for cp/mv!!!!!
                retcode = myOS.run_and_return_rc("mv " + cfgFile + " " + resDir + "/.")
                if retcode != 0:
                    self._warn("Failed to mv %s to %s!" % (cfgFile, resDir), schedule)

                retcode = myOS.run_and_return_rc("cp " + dictFile + " " + resDir + "/.")
                if retcode != 0:
                    self._warn("Failed to cp %s to %s!" % (dictFile, resDir), schedule)

                # USS-1671 End

                # check return code
                if ret != 0:
                    # FAILED tests

                    self._warn("** FAIL ** - %s has failed it's tests." % tcdetails, schedule)
                    self._fail_schedule(schedule)

                    tc['status'] = "Failed Tests"
                    tc['statustime'] = self.get_timestamp()

                    schedule['tclist_byhw'][uut]['threadfails'] += 1
                else:
                    # Passed tests
                    tc['status'] = "Passed"
                    tc['statustime'] = self.get_timestamp()



    def _fail_schedule(self, schedule):
        schedule['overallresult'] = 'Failed'

    def _info(self, msg, schedule):
        schedule['infomessages'].append(msg)

    def _warn(self, msg, schedule):
        schedule['warnmessages'].append(msg)

    def _check_threads_running(self,schedule):
        # Step through the threads and return True if any are still active
        ret = False

        for uut in schedule['tclist_byhw']:
            thread = schedule['tclist_byhw'][uut]['thread']
            try:
                if thread.is_alive():
                    ret = True
            except AttributeError:
                pass # Ignore if the thread has not yet been created

        return ret



class AVSSchedulerError(RuntimeError):
    pass

"""
USS-1025 notes

schedule elements needed for a run
'tclist' - can be output to file and read in again
'tclist_byhw' - can be created from the tclist using _insert_tclist_byhw
'binpath' - used to create the output dir, could be sniffed from any TC





"""
