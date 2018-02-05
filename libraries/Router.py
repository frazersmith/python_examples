# Robot libraries
from robot.api import logger
from robot.version import get_version
from robot import utils

import time

from libraries.LinuxBox import LinuxBox

__version__ = "0.1 beta"

class Router(LinuxBox):
    """ Amino WiFi Router Library by Frazer Smith.

    This library is designed for use with Robot Framework.

    This is an extension of the LinuxBox library with specific OpenWRT commands.

    
    """
    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):
        
        LinuxBox.__init__(self)


    def check_ping_stats(self, targetip, packets=10):
        packets = int(packets)
        self._login()        
        output, error = self._conn.execute_command("ping -c %s %s" % (str(packets), targetip) , return_stderr=True)
        packet_loss = ""
        rtmin = ""
        rtavg = ""
        rtmax = ""
        for line in output.split("\n"):
            if "packets transmitted," in line:
                packet_loss = line.split()[6]
            elif "round-trip min/avg/max" in line:
                rt = line.split()[3]
                rtmin = rt.split("/")[0]
                rtavg = rt.split("/")[1]
                rtmax = rt.split("/")[2]

        return packet_loss, rtmin, rtavg, rtmax
                


    def check_link_stability(self, interface, targetmac, howlong="2 minutes"):

        howmanytimes = int(utils.timestr_to_secs(howlong) / 5)
        #self.send_commands_over_debug("echo '' > /tmp/linktemp.txt")
        rc = []
        signal = []
        self._login()
        for x in range(howmanytimes):
            nowtime = time.time()
            output, error = self._conn.execute_command("iw dev %s station get %s | grep signal: | awk '{print $2}'" % (interface, targetmac) , return_stderr=True)
            if 'command failed' in error:
                rc.append(1)
            else:
                rc.append(0)
                signal.append(int(output))
            if time.time() < nowtime+5:
                time.sleep((nowtime+5)-time.time())
        self._conn.close_all_connections()

        stability = ""
        avgsig = ""
        
        if 0 in rc:
            stability = "SOLID"
        if 1 in rc:
            if stability=="SOLID":
                stability="UNSTABLE"
            else:
                stability="DEAD"
        
        if stability=="SOLID":
            avgsig = str(sum(signal)/len(signal))

        return stability, avgsig

    def send_router_command_and_return_output(self, command):

        """  Send a command to the router and return the output

        The return code will be checked and a warning raised if it is non zero.

        Examples:
        | ${output}=	| Send router command and return output	| iw list 	|
        
        """

        alloutput = self.execute_command(commandout, return_rc=True)
        if alloutput[1] <> 0:
            logger.warn("Router command failed to execute correctly!  Return code was " + str(alloutput[1]))
        
        return alloutput[0]

    def commit_uci_commands(self, *commands):

        """  Sends a list of UCI commands to the router then commits them and restarts interfaces

        All output is concatenated and dumped to debug when the method completes

        Examples:
        | Commit UCI commands	| wireless.radio1.channel=${channel}	| wireless.radio1.txpower=${power}	|
        
        """
        output=""

        self._conn.set_default_configuration(timeout="2 minutes")
        self._conn.open_connection(self._ipaddress, prompt=self._prompt, newline=self._newline)
        self._conn.login(self._username, self._password)


        for command in commands:
            output = output + self._conn.execute_command("uci set " + command)
            
        output = output + self.execute_command("uci commit")
        logger.info("Restarting WiFi interfaces...")
        # New method
        output = output + self.execute_command("wifi")
        # Old method
        # output = output + self.execute_command("/etc/init.d/network restart && /etc/init.d/firewall restart")
        self._conn.close_all_connections()
        self._conn.set_default_configuration(timeout="3 seconds")
        logger.debug(output)
        return output



    def get_station_info(self, device, mac, value="all"):
        """  Returns station dump info for a given mac address on a given interface device

        If the mac is not found on the wireless interface an error will be raised

        Possible values:-
        - all		- Returns full station dump for this mac
        - inactive time
        - rx bytes
	- rx packets
        - tx bytes
        - tx packets
        - tx retries
        - tx failed
        - signal:	- Just passing 'signal' will get the signal avg
        - signal avg
        - tx bitrate
        - rx bitrate
        - authorized
        - authenticated
        - preamble
        - wmm/wme
        - mfp
        - tdls peer

        Examples:-
        | ${txbr}=	| Get Station Info	| wlan1	| ce:21:23:23:fa:d5	| tx bitrate	|
        | ${all}=	| Get Station Info	| wlan0 | a1:2f:dc:61:09:11	| 		|

        """
 
        value=value.lower()
        
        output = self.execute_command("iw dev " + device.lower() + " station dump | grep -A17 " + mac.lower(),return_rc=True)
        if output[1]!=0:
            raise RouterError("mac '" + mac.lower() + "' not found on interface '" + device.lower() + "'")
        if value == "all":
            return output[0]
        else:
            lines = output[0].split("\n")
            ret = ""
            for line in lines:
                if line.lower().find(value)!=-1:
                    ret = line.split(":")[1].rstrip().lstrip()
            if ret == "":
                raise RouterError("value '" + value + "' not found in station dump")
            else:
                return ret


class RouterError(RuntimeError):
    pass

                



        
