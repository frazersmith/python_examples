# Robot libraries
from robot.api import logger
from robot.version import get_version
from robot import utils

import time

from libraries.LinuxBox import LinuxBox

__version__ = "0.1 beta"

class FluteServer(LinuxBox):
    """ Enable Flute Server library by Frazer Smith.

    This library is designed for use with Robot Framework.

    This is an extension of the LinuxBox library with specific OpenWRT commands.


    """
    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):

        LinuxBox.__init__(self)

    # Add session
    """ if the bin does not exist in scriptdirectory we need to wget it, so prob best to give ftp details as standard?

    if bin exists in scriptdirectory we need to use fluteSessionAdd

    need to give options for mcast_address (default not set), port (default not set) and rate (default not set, 2048 if mcast and port set)
    """

    def session_add(self, build, mcast_address=None, port=None, rate="2048"):
        if mcast_address == None and port == None:
            rate = None

        args = ""

        if mcast_address is not None:
            # If an mcast address is set then all params must be included?
            pass




    # Delete session
        """ Need to know session id (the long name of the build).  Should be able to pass a session from the list sessions keyword """



    def server_stop(self):
        """
        Stops server
        """
        ret, rc = self.execute_command("cd %s; ./fluteStop.sh" % self.get_tool_location("scriptdirectory"), return_rc=True)
        if rc != 0:
            logger.warn(ret)
            raise FluteServerError("Server Stop FAILED!")
        else:
            logger.info(ret)
        pass






    def server_start(self):
        """
        Starts Server
        """

        if self.server_is_running():
            logger.warn("Server already started!")
            raise FluteServerError("Server already started!")
            return

        self.start_command("cd %s; ./fluteStart.sh &" % self.get_tool_location("scriptdirectory"))

        time.sleep(3)

        if not self.server_is_running():
            logger.warn("Server Start FAILED!")
            raise FluteServerError("Server Start FAILED!")
        else:
            logger.info("Server started")


    def session_restart(self):
        """
        Restarts session
        """
        pass


    # List sessions

    def session_list(self):
        """
        Return list of active sessions
        """
        pass


    def server_is_running(self):
        """
        Return True if the server is running
        """

        rc = self.execute_command("cat /tmp/flute.metadata", return_stdout=False, return_rc=True)

        if rc==0:
            return True
        else:
            return False





class FluteServerError(RuntimeError):
    pass