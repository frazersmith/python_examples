# Robot libraries
import SSHLibrary
import robot.libraries.Telnet as Telnet
from robot.api import logger
from robot.version import get_version
from robot import utils

# Standard libraries
import time
import string
import os

__version__ = "0.1 beta"

class LinuxBox(object):
    """ Amino LinuxBox Library by Frazer Smith.

    This library is designed for use with Robot Framework.

    This is a simple helper for sending commands via SSH to a linux PC.

    It can be used as a library or as a base class for other libraries (such as STBRC or AttenuatorController)

    By default it will use root access (Amino standard root account details) but
    can be setup to use any valid credentials.

    

    """
    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, ipaddress=None, username="root", password="vie4Laeb"):
        """  No arguments are mandatory when instantiating the library """
        self._ipaddress = ipaddress
        self._prompt = None
        self._username = username
        self._password = password
        self._newline = "\n"
        self._conn = SSHLibrary.SSHLibrary()
        self.tools={}


    def ping(self, target):
        """  LinuxBox: Sends a single ping to a defined target.  Returns 'True' if successful or 'False' otherwise.

        Example:
        | ${pingresponse}=	| Ping	| 10.172.2.5	|
        """
        retcode=self.execute_command("ping -c 1 " + target, return_stdout=False, return_rc=True)
        if retcode <> 0:
            return False
        else:
            return 
    
    def set_prompt(self, prompt):
        """  LinuxBox: The prompt is required so the SSH library knows when the execution of a command has completed

        Example:
        | Set prompt	| root@it-000199:	|
        """

        self._prompt = prompt


    def set_tool_location(self, toolname, location):
        """ Linuxbox: Give the location of a specific tool which can be used by other libraries

        Example:
        | Set tool location	| iperf	| /root/robottools/iperf	|
        """
        self.tools[toolname] = location

    def get_tool_location(self, toolname):
        """ Linuxbox: Give the location of a specific tool which can be used by other libraries

        Example:
        | ${location}=	| Get tool location	| iperf	|

        """

        if toolname in self.tools:
            return self.tools[toolname]
        else:
            raise LinuxBoxError("The location of tool '%s' has not been set!" % toolname)

        
    def get_ip_address(self):
        """  LinuxBox: Returns the IP address of the linux box
        
        Example:-
        | ${ip}=	| Get IP Address	|
        """
        return self._ipaddress

    def set_ip_address(self, ipaddress):
        """  LinuxBox: Sets the IP address of the linux box
        
        Example:-
        | Get IP Address	| 10.172.249.2	|

        """
        self._ipaddress = ipaddress

    def execute_command(self, command, return_stdout=True, return_stderr=False,
                        return_rc=False, usepubkeylogin=False):
        """ LinuxBox: Executes a command using SSH, returning any combination of stdout, stderr or return code.

        Examples:
        | ${rc}=		| Execute Command	| mkdir /temp/newdir	| return_rc=True	| return_stdout=False	|
        | ${output}=		| Execute Command	| ls -al		| 			|			|
        | ${stdout}		| ${stderr}=		| Execute Command	| mv /temp/newdir .	| return_stderr=True	|
        | Execute Command	| reboot now()		|			|			|			|
        """

        self._login(pubkeylogin=usepubkeylogin)
        output = self._conn.execute_command(command, return_stdout, return_stderr, return_rc)
        self._conn.close_all_connections()
        return output

    def execute_command_with_confirm(self, command, return_stdout=True, return_stderr=False, return_rc=False):
        """ LinuxBox: RESERVED FOR USE WITH STBRC.   This will send a command, then wait 3 seconds before confirming with 'y'.

        Always returns both stdout and rc

        """
        self._login()
        self._conn.write(command)
        time.sleep(3)
        self._conn.read()
        self._conn.write("y")
        output = self._conn.read_until_prompt()
        rc = self._conn.execute_command("echo $?")
        #logger.warn(output)
        #output = self._conn.execute_command("y", return_stdout, return_stderr, return_rc)
        return output,int(rc)     
   
    def _login(self,pubkeylogin=False):
        self._conn.open_connection(self._ipaddress, prompt=self._prompt, newline=self._newline, timeout="1 minute")
        if pubkeylogin:
            keyfile = os.getenv('HOME', '~') + "/id_rsa"
            self._conn.login_with_public_key(self._username, keyfile)
        else:
            self._conn.login(self._username, self._password)

        
    def _close(self):
        try:
            self._conn.close_all_connections()
        except:
            pass
        self._conn = None

    
    def __del__(self):
        self._close()
    
    def start_command(self, command):
        """ LinuxBox:  This will send a command and exit immediately

        """

        self._login()
        self._conn.start_command(command)


class LinuxBoxError(RuntimeError):
    pass
