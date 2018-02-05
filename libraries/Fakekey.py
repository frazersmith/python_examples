import socket
import time
import threading
from datetime import datetime, timedelta
from robot.libraries.BuiltIn import BuiltIn
from robot.api import logger
from robot.version import get_version
from robot import utils

__version__ = "0.1 beta"

class Fakekey:

    """ Fakekey interpreter rewritten in Python by Frazer Smith, from original perl script by Alden Spiess

    Usage:  fakekey ${fakekey_mappingfile}
    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    

    def __init__(self, mappingfile="fakekey_defaultmapping", ipaddress=None, port=None):

        try:
            exec "from libraries.%s import cmd_array" % mappingfile
        except:
            try:
                exec "from %s import cmd_array" % mappingfile
            except:
                raise Exception("Unable to load mappingfile")

        self._cmd_array = cmd_array
        self._port = port
        self._ipaddr = ipaddress
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._connected = False
        self._timedout = False
        self._abandon_timeout = False
        self._timeoutthread = None
        self._timeout = None


    def _connect(self):

        self._socket.connect(( self._ipaddr, int(self._port) ))
        self._connected = True

    def send_fakekey(self, keyname, pause=None, repeatcount="1"):
        """ Sends a single fakekey command to the defined IP address.

        The key code must be in the mapping file.

        A pause (after sending) can be defined.

        The key can be sent a number of times with repeatcount

        Examples:
        | Send Fakekey	| CIR_BTN_DOWN	|				|		|
        | Send Fakekey	| K_PDOWN	| pause=500 milliseconds	| repeatcount=5	|

        """

        if keyname in self._cmd_array:
            if not self._connected:
                self._connect()

            count=0
            while (count < int(repeatcount)):
                self._socket.send(self._cmd_array[keyname] + "\n")
                if pause != None:
                    time.sleep(utils.timestr_to_secs(pause))  
                count=count+1
        else:
            raise LookupError("Unrecognised fakekey command: " + keyname)

 
    def close(self):
        """ Close down any open fakekey sockets 

        Example:
        | Close	|
        """

        self._socket.close()
        self._connected = False
        self._kill_timeout_thread()

    def __del__(self):
        self.close()

    def _get_fakekey_script(self, filename):

        try:
            with open(filename) as inputFileHandle:
                return inputFileHandle.read()

        except IOError as i:
            logger.warn( "Unable to open script file %s" % (filename) )
            raise i

    def _start_timeout(self, timeout):
        self._timeout = timeout
        self._timeoutthread = threading.Thread(target=self._timeout_thread)
        self._timeoutthread.start()

    def _kill_timeout_thread(self):
        if self._timeout != None:
            self._abandon_timeout = True
            self._timeoutthread.join()


    def _timeout_thread(self):
        endtime = datetime.now() + timedelta(seconds=utils.timestr_to_secs(self._timeout))
        
        while not self._abandon_timeout:
            time.sleep(.5)
            if endtime <= datetime.now():
                self._timedout=True
                self._timeout=None
                break
 
        

    def run_fakekey_script(self, filename, repeats=-1, timeout=None):
        """ Run original style fakekey scripts
       
        There are three ways a fakekey script can halt execution correctly:-
        - exit command in the script
        - after a defined number of repeats
        - after a defined timeout
  
        Examples:
        | Run fakekey script	| resources/testscripts/reboot.fakekey		|			|
        | Run fakekey script	| resources/testscripts/chupdown.fakekey	| repeats=10		|
        | Run fakekey script	| ${scriptname}					| timeout=5 days	|

        """

        timeouttext = "."

        if timeout!=None:
            logger.info("This test will timeout after " + timeout)
            timeouttext = ", or until timeout is reached."
            self._start_timeout(timeout)

        if repeats == -1:
            logger.info("Running fakekey script '" + filename + "' forever or until exit command is encountered" + timeouttext)
        else:
            logger.info("Running fakekey script '" + filename + "' " + str(repeats) + " time(s)" + timeouttext)
            repeats = int(repeats)
        
        lines = self._get_fakekey_script(filename).split("\n")

        count=0

        while (count <> repeats):
            for line in lines:
                if self._timedout:
                    logger.info("Timed out - Ending fakekey script execution.")
                    return
                if self._process_script_line(line)==1:
                    self._kill_timeout_thread()
                    logger.info("'Exit' encountered in fakekey script.")
                    return
            count = count + 1
        

    def _process_script_line(self, line):
        # Strip out whitespace
        line = line.strip()
        if line == "":
            logger.debug("EMPTY")
            return 0
        elif line[0] == "#":  #It's a comment
            logger.debug("COMMENT: " + line)
            return 0
        elif line.lower().startswith("wait"):
            logger.debug("SLEEPING " + str(int(line.split("|")[1])))
            time.sleep(float(line.split("|")[1]) / 1000)
            return 0
        elif line in self._cmd_array:
            logger.debug("COMMAND: " + line) 
            self.send_fakekey(line)
            return 0
        elif line.lower() == "exit":
            logger.debug("EXIT")
            return 1
        else:
            raise LookupError("Unrecognised command in script - " + line)


        

