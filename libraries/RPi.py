# Robot libraries
import SSHLibrary
from LinuxBox import LinuxBox
from robot.api import logger
from robot.version import get_version
from robot import utils
import robot.libraries.OperatingSystem as ROS


# Standard libraries
import time
import string

__version__ = "0.1 beta"

class RPi(LinuxBox):
    """ Amino RPi Library by Frazer Smith.


    NOTE: For `Send Hotplug` and `Check Video` you must have the Gertboard and RPi camera installed
          Also, the gertboard must have the following jumpers:-
              J7 (top two pins connected)
              GP11 to SCLK
              GP10 to MOSI
              GP9  to MOSO
              GP7  to CSnB

          Also you must use the special Hotpin HDMI cable with:-
              Yellow cable connected to Gertboard J28 DA0
              Blue cable connected to Gertboard J25 Grnd (the one next to DA0 for convenience)

         The camera must be taped to the display in a position not affected by aspect ratio handling
         i.e. avoid pillarbox or letterbox areas


         NOTE: Hotplug waveforms are constructed out of several 3 element vectors which define:
               Start Voltage (as an absolute value from 0 to 255 (since the DAC is 8 bit) or as a percentage string (e.g. "50%")
               End Voltage (as an absolute value from 0 to 255 (since the DAC is 8 bit))
               Transition Time (in milliseconds.  This is how long it takes to travel from 'Start' to 'End' voltage)

               This allows for :-
                   . Instant switches (i.e. sharp edges to the waveform) such as [255,0,0] (High to low immediately),
                     or [0,255,0] (Low to high immediately).
                   . Periods where it is held in state such as [0,0,5000] (go low for 5000 milliseconds)
                   . Ramp waveforms, such as [255,0,1000] (High to low takes 1 second)

               You use python list notation to join several transitions into a single vector definition
               e.g. [[255,0,50],[0,0,500],[0,255,450]] 
               .. which goes from high to low over a 50ms ramp, stays low for 500ms then ramps from low to high over 450ms

               This is the same wavefrom expressed in percentage strings:-
                   [['100%','0%',50],['0%','0%',500],['0%','100%',450]]
               
             


    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()


    def __init__(self, ipaddress=None, username="root", password="vie4Laeb"):

        LinuxBox.__init__(self, ipaddress, username, password)

        """  No arguments are mandatory when instantiating the library """
 
        self._os = ROS.OperatingSystem()
        self._drivers_ok = False

        self._script_root = "/usr/sbin/gertboard/sqa"
        self._script_hotplug = "%s/hotplug.py" % self._script_root
        self._script_checkcamera = "%s/checkCamera.py" % self._script_root
        self._script_startdrivers = "%s/startDrivers.py" % self._script_root
        self._script_checkaudio = "%s/checkAudio.py" % self._script_root

    def open_door(self):
        output, rc = self._lego_door("open.py")
        if rc <> 0:
            logger.warn("Unable to open door! %s" % output)

    def close_door(self):
        output, rc = self._lego_door("close.py")
        if rc <> 0:
            logger.warn("Unable to close door! %s" % output)


    def _lego_door(self, script):
        self._login()
        output, rc = self._conn.execute_command("%s/nxt/%s" % (self._script_root, script), True, False, True)
        return output, rc

    def send_hotplug(self, vectors):

        """  Sends a hotplug waveform to DAC DA0 on gertboard

        Example:
        | Send hotplug	| [[255,0,50],[0,0,500],[0,255,450]]	|
        | Send hotplug	| $sbyon_signal				|

        """

        if not self._drivers_ok:
            self.execute_command(self._script_startdrivers)
            self._drivers_ok = True

        self._login()
        output, rc = self._conn.execute_command("%s '%s'" % (self._script_hotplug, vectors), True, False, True)
        self._conn.close_all_connections()
        
    def check_video(self, tries=3):

        """  Checks video is outputing from TV using camera on RPi

        The camera will be polled 3 times by default, 3 seconds apart.  If any of the polls return a brightness above
        a preset threshold the return will be 'True'. Otherwise it will return 'False'

        The amount of polls can be defined using 'tries'

        Example:
        | ${ret}=	| Check video	| 		|
        | ${ret}=	| Check video	| tries=5 	|

        """

        self._login()
        output, rc = self._conn.execute_command("%s %s" % (self._script_checkcamera, tries), True, False, True)
        self._conn.close_all_connections()

        if rc == 0:
            return True
        else:
            return False


    def check_audio(self, passlevel = 30, method="AVERAGE"):

        """  Checks the audio level received from TV using sound capture dongle on RPi

        The audio input to the RPi will be sampled 5 times, at 1 second intervals.

        The passlevel must be met or bettered to return 'True', otherwise 'False' is returned.

        The passlevel can be checked against the AVERAGE volume, or the PEAK volume, as defined by 'method'

        Examples:
        | ${ret}=	| Check audio	| 		|
        | ${ret}=	| Check audio	| method=PEAK 	|
        | ${ret}=	| Check audio	| passlevel=5 	|

        """

        self._login()
        output, rc = self._conn.execute_command("%s %s" % (self._script_checkaudio, method), True, False, True)

        logger.trace(output)

        if rc == 255:
            raise RPiError("Error running checkAudio")
        else:
            if rc >= int(passlevel):
                return True
            else:
                return False


class RPiError(RuntimeError):
    pass

