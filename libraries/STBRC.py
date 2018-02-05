# Robot libraries
from robot.api import logger
from robot.version import get_version
from robot import utils

import time

from libraries.LinuxBox import LinuxBox

__version__ = "0.1 beta"

class STBRC(LinuxBox):
    """ Amino STB Remoteconf Library by Frazer Smith.

    This library is designed for use with Robot Framework.

    This is an extension of the LinuxBox library with specific stbrc commands.

    
    """
    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):
        
        LinuxBox.__init__(self)
        self._stbrc_passphrase="stbrckey"
        self._stbrc_binary_path=None
        self._stbrc_keyfile_path=None
        self._stbrc_target=None
        self._stbrc_options=''

    def set_stbrc_target(self, target):
        """  Set the STBRC target (the STB to control)

        Example:
        | Set stbrc target	| ${ipaddress}	|
        """
        self._stbrc_target = target

    def set_stbrc_passphrase(self, passphrase):
        """  Set the STBRC passphrase (defaults to stbrckey)

        Example:
        | Set stbrc passphrase	| customerpassphrase	|
        """
        self._stbrc_passphrase = passphrase

    def set_stbrc_host(self, ip):
        """  Set the STBRC host (the linux box with STBremoteconf on it)

        Example:
        | Set stbrc host	| ${ipaddress}	|
        """
        self.set_ip_address(ip)

    def set_stbrc_options(self, options):
        """  Set STBRC options which will precede the target and command

        Example:
        | Set stbrc options	| -m 00:02:02:48:21:bb 	|
        """
        self._stbrc_options = options

    def clear_stbrc_options(self):
        """  Removes STBRC options

        Example:
        | Clear stbrc options	|
        """
        self._stbrc_options = ''


    def set_stbrc_binary_path(self, path):
        """  Set the STBRC binary path (the path for the STBremoteconf binary file on the host)

        Example:
        | Set stbrc binary path	| /var/www/autotest/legacy/scripts/STBremoteconf	|
        """
        self._stbrc_binary_path = path

    def set_stbrc_keyfile_path(self, path):
        """  Set the STBRC keyfile path (the path for the STBremoteconf private key file on the host)

        Example:
        | Set stbrc keyfile path	| /var/www/autotest/legacy/scripts/STBrc-KEY.private	|
        """
        self._stbrc_keyfile_path = path

    def send_stbrc_command(self, command, target="default", pubKeyLogin=False):
        """  Send a STBremoteconf command and return the output

        The return code will be checked and a warning raised if it is non zero.

        The target (STB) can be sent as an argument, otherwise the target already set (using 'Set stbrc target') will be used.

        The pubkeylogin is used to allow login to qa-wifi and issue the command on that machine. This is because qa-wifi requires a different login method.

        NOTE:  If you are sending a multicast STBrc command you must use `Send stbrc command with confirm` as confirmation is required to send it.

        Examples:
        | Send stbrc command	| GETVERSION	|				|
        | Send stbrc command	| GETVERSION	| pubKeyLogin=True              |
        | Send stbrc command	| GETVERSION	| target=${different_STB}	|
        
        """

        if target=="default":
            target=self._stbrc_target

        if target==None or self._stbrc_binary_path == None or self._stbrc_keyfile_path == None:
            logger.warn("Attempting to send a STBRC command without specifying necessary parameters (target, binary path, keyfile path)!")
            return

        # Create correct exports
        #self.execute_command("export STBPASS=" + self._stbrc_passphrase + ";export STBKEY=" + self._stbrc_keyfile_path)
        commandout = "export STBPASS=" + self._stbrc_passphrase + ";export STBKEY=" + self._stbrc_keyfile_path + ";" + self._stbrc_binary_path + " " + self._stbrc_options + " " + target + " " + command
        logger.debug(commandout)
        
        alloutput = self.execute_command(commandout, return_rc=True, usepubkeylogin=pubKeyLogin)
        if alloutput[1] <> 0:
            logger.warn("STBRC command failed to execute correctly!  Return code was " + str(alloutput[1]))
        
        return alloutput[0]

    def send_stbrc_command_with_confirm(self, command, target="default"):
        """  Send a STBremoteconf command, confirming to send it when prompted, and return the output.

        This is required for a STBRC command intended for a multicast address.

        The return code will be checked and a warning raised if it is non zero.

        The target (STB) can be sent as an argument, otherwise the target already set (using 'Set stbrc target') will be used.

        Examples:
        | Set stbrc options			| -m 00:02:02:48:21:bb 	|			|
        | Send stbrc command with confirm	| GETVERSION		| target=225.100.0.138	|
        
        """

        if target=="default":
            target=self._stbrc_target

        if target==None or self._stbrc_binary_path == None or self._stbrc_keyfile_path == None:
            logger.warn("Attempting to send a STBRC command without specifying necessary parameters (target, binary path, keyfile path)!")
            return

        # Create correct exports
        #self.execute_command("export STBPASS=" + self._stbrc_passphrase + ";export STBKEY=" + self._stbrc_keyfile_path)
        commandout = "export STBPASS=" + self._stbrc_passphrase + ";export STBKEY=" + self._stbrc_keyfile_path + ";" + self._stbrc_binary_path + " " + self._stbrc_options + " " + target + " " + command
        logger.debug(commandout)
        
        alloutput = self.execute_command_with_confirm(commandout, return_rc=True)
        if alloutput[1] <> 0:
            logger.warn("STBRC command failed to execute correctly!  Return code was " + str(alloutput[1]))
        
        return alloutput[0]

    def send_stbrc_changepage(self, url, target="default"):
        """  Send a STBremoteconf 'CHANGEPAGE' command and return the output

        The URL will be encapsulated in quotes to preserve arguments within it.

        The return code will be checked and a warning raised if it is non zero.

        The target (STB) can be sent as an argument, otherwise the target already set (using 'Set stbrc target') will be used.

        Examples:
        | Send stbrc changepage	| http://qa-test2								|								|				|
        | ${piptest}=		| Set variable									| http://qa-test2/testpages/pip/piptest.html			|				|
        | Send stbrc command	| ${piptest}?src0=igmp://239.255.250.1:11111&src1=igmp://239.255.250.18:11111	| target=${different_STB}					|				|
        
        """
        # Need to encapsulate the URL in quotes to protect the arguments
        targetout = target
        url = '"%s"' % url
        output = self.send_stbrc_command("CHANGEPAGE " + url, target=targetout)
        return output

    def send_stbrc_upgrade(self, url, target="default", waitfor="2 minutes"):
        """  Send a STBremoteconf 'UPGRADE' command and wait for a set period (defaults to 2 minutes)

        The return code will be checked and a warning raised if it is non zero.

        The target (STB) can be sent as an argument, otherwise the target already set (using 'Set stbrc target') will be used.

        Examples:
        | Send stbrc changepage	| http://qa-test2								|								|				|
        | ${piptest}=		| Set variable									| http://qa-test2/testpages/pip/piptest.html			|				|
        | Send stbrc command	| ${piptest}?src0=igmp://239.255.250.1:11111&src1=igmp://239.255.250.18:11111	| target=${different_STB}					|				|
        
        """
        targetout = target
        url = '"%s"' % url
        output = self.send_stbrc_command("UPGRADE " + url, target=targetout)
        timetowait = utils.timestr_to_secs(waitfor)
        time.sleep(timetowait)
        return output



        
