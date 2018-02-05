import time
import threading
from datetime import datetime, timedelta
from robot.libraries.BuiltIn import BuiltIn
from robot.api import logger
from robot.version import get_version
from robot import utils
#import Pyhnr
import hnr
import sys, os

sys.path.append(os.path.abspath('./libraries/hnr'))
sys.path.append(os.path.abspath('./libraries/hnr/transports'))

__version__ = "0.1 beta"

class HNRKey:

    """ HNR to Fakekey wrapper rewritten by Frazer Smith


    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()


    #def __init__(self, mappingfile="fakekey_hnrmapping", ipaddress=None, port="20000", hnr_repeat_rate="0.12", ssh_tunnel_user='', ssh_tunnel_password=''):
    def __init__(self, mappingfile="fakekey_hnrmapping", ipaddress=None, port="0", hnr_repeat_rate="0.12", ssh_tunnel_user='', ssh_tunnel_password=''):

        cmd_array = None

        try:

            exec "from libraries.%s import cmd_array" % mappingfile
        except:
            try:
                exec "from %s import cmd_array" % mappingfile
            except:
                raise Exception("Unable to load mappingfile")

        self._cmd_array = cmd_array
        self._port = int(port)
        self._ipaddr = ipaddress
        #self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._connected = False
        self._timedout = False
        self._abandon_timeout = False
        self._timeoutthread = None
        self._timeout = None
        self._pyhnr = None
        self._hnr_repeat_rate = float(hnr_repeat_rate)
        self._trans = "AUTO" # transport type.  Will default to SSH tunnel for Q4.1 and later, and UDP for Q3.2 and earlier
        self._group = 0
        self._trans_kwargs = None
        self._flag_connected = False
        self._ssh_tunnel_user = ssh_tunnel_user
        self._ssh_tunnel_password = ssh_tunnel_password


    def _connect(self):
        #self._pyhnr = Pyhnr.Pyhnr(ip_addr=self._ipaddr, port=self._port)
        self._pyhnr = hnr.HnrConnection(self._ipaddr, self._port, self._group, trans=self._trans, trans_kwargs=self._trans_kwargs, ssh_tunnel_user=self._ssh_tunnel_user, ssh_tunnel_password=self._ssh_tunnel_password)
        self._pyhnr.connect()

        #self._socket.connect(( self._ipaddr, int(self._port) ))
        self._connected = True


    def send_fakekey(self, keyname, pause=None, repeatcount="1"):
        if keyname in self._cmd_array:

            self.send_hnrkey(self._cmd_array[keyname], pause, repeatcount)
        else:
            raise LookupError("Unrecognised fakekey command: " + keyname)


    def send_hnrkey(self, keyname, pause=None, repeatcount="1", hold=None):
        """ Sends a single hnr command to the defined IP address.

        A pause (after sending) can be defined.

        The key can be sent a number of times with repeatcount

        A 'hold' duration can be defined where the key will be sent as held for a specific time

        NOTE: repeat is not the same as hold!  Repeat simulates the key being pressed several times

        Examples:
        | Send Fakekey	| CIR_BTN_DOWN	|				|		|
        | Send Fakekey	| K_PDOWN	| pause=500 milliseconds	| repeatcount=5	|

        """

        if not self._connected:
            self._connect()

        if hold is None:
            count=0
            while (count < int(repeatcount)):
                self._pyhnr.send_key(keyname)
                if pause != None:
                    time.sleep(utils.timestr_to_secs(pause))
                count=count+1
        else:
            endtime = time.time() + utils.timestr_to_secs(hold)
            firstkey = True
            while endtime > time.time():
                if firstkey:
                    self._pyhnr.send_key(keyname, False)
                    firstkey = False
                    logger.info("Repeat rate='%s'" % str(self._hnr_repeat_rate))
                else:
                    self._pyhnr.send_key(keyname, True)
                time.sleep(self._hnr_repeat_rate)

    def close(self):
        """ Close down any open hnr connections

        Example:
        | Close	|
        """

        #self._socket.close()
        try:
            self._pyhnr.disconnect()
        except AttributeError:
            pass

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
        """ Run original style fakekey scripts - converting to HNR

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




