from libraries.STB import STB
from robot.version import get_version
from robot import utils
from robot.api import logger
import time

__version__ = "0.1 beta"

class WiFiSTB(STB):


    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):


        STB.__init__(self)



    def check_link_stability(self, howlong="2 minutes"):

        howmanytimes = int(utils.timestr_to_secs(howlong) / 10)
        self.send_commands_over_debug("echo '' > /tmp/linktemp.txt")
        for x in range(howmanytimes):
            nowtime = time.time()
            self.send_commands_over_debug("(netman info wlan0 | grep Status | awk {'print $3'}) >> /tmp/linktemp.txt && (netman get_wifi_aps wlan0 2>/dev/null | grep 'Signal: Quality') >> /tmp/linktemp.txt")
            if time.time() < nowtime+10:
                time.sleep((nowtime+10)-time.time())
        output = self.send_command_over_debug_and_return_output("cat /tmp/linktemp.txt", timeout="30 seconds")
        stability = ""
        
        if "READY" in output:
            stability = "SOLID"
        if "LINK_DOWN" in output:
            if stability=="SOLID":
                stability="UNSTABLE"
            else:
                stability="DEAD"

        return stability
        
