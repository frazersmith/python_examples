from libraries.STB import STB as STBClass
from libraries.WiFiRouter import WiFiRouter as RouterClass
from libraries.LinuxBox import LinuxBox as LinuxBoxClass
from libraries.AttenuatorControl import AttenuatorControl as AttenuatorControlClass
from robot.version import get_version
from robot import utils
from robot.api import logger
import libraries.PostProcessing as PP
import time
import random
import string


__version__ = "0.1 beta"

class WiFiTestStation(object):
    """ Amino WiFiTestStation Library by Frazer Smith.

    This library is designed for use with Robot Framework.

    WiFiTestStation gives access to keywords which control WiFi testing.

    A WiFi Test Station has 2 mandatory elements:-
        STB     - A Set Top Box object defined in resources/devices
        Router  - A Wireless Access Point defined in resources/devices

    Optionally, the test station may also support one or more Attenuatorcontrol's
  

    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, STB=None, Router=None, PC=None):

        # Mandatory
        if (STB is None) or (isinstance(STB, STBClass)):
            self.STB = STB
        else:
            raise WiFiTestStationError("Incorrect object type passed for STB")

        if (Router is None) or (isinstance(Router, RouterClass)):
            self.ROUTER = Router
        else:
            raise WiFiTestStationError("Incorrect object type passed for Router")

        if (PC is None) or (isinstance(PC, LinuxBoxClass)):
            self.PC = PC
        else:
            raise WiFiTestStationError("Incorrect object type passed for PC")


        # Optional
        self.Attenuators = []

        # Set defaults for test station

        # environment properties
        self._download_location = "http://qa-test2/downloads"
        self._stb_wifi_interface = 1 # This could be forced with set active interface
        self._stb_tools = "/tmp/wifi"
        self._wifi_type = "BCM" #IMPROVEMENT add other options, add a way to set an option, perhaps in STB object?


        # iperf properties
        self._iperf_test_duration = "20"
        self._iperf_test_interval = "2"
        self._iperf_tcp_extra_options = "-f m -w 85.3k"
        self._iperf_client_tcp_options = "-p 2333 -t %s -i %s %s" % (self._iperf_test_duration, self._iperf_test_interval, self._iperf_tcp_extra_options)
        self._iperf_server_tcp_options = "-p 2333"
        self._iperf_client_udp_options = "-p 2333 -u -i 3 -t 3 -yC -xCD -b "
        self._iperf_server_udp_options = "-p 2333 -u -i 1"
        self._iperf_pc_output = "~/iperf_output.txt"
        self._iperf_stb_output = "%s/iperf_output.txt" % self._stb_tools
        
    def initial_setup(self, SSID=None, Passphrase=None):
        """ TODO This will take a STB and Router from an unknown state into a known band, association and able to communicate
        """

        self.SSID = SSID or self._get_random_chars()
        self.Passphrase = Passphrase or self._get_random_chars()

        self._log("SSID = '%s'" % self.SSID)


        RADIO = self.ROUTER.get_active_radio()
        DEFAULTS = self.ROUTER.config.DEFAULTS

        CHANNEL = DEFAULTS['CHANNEL_%s' % RADIO ]
        COUNTRY = DEFAULTS['REGION_%s' % RADIO ]
        REGION = eval("self.ROUTER.config.REGIONS_%s['%s'][0]" % (RADIO, COUNTRY))
        HWMODE = DEFAULTS['MODE_%s' % RADIO ]
        ENCRYPTION = DEFAULTS['ENCRYPTION']
        STBENCRYPTION = eval("self.ROUTER.config.ENCRYPTION['%s'][1]" % ENCRYPTION)

        # Use the first HTMODE and Txpower in the default channel
        HTMODE = eval("self.ROUTER.config.CHANNELS_%s['%s'][0][0]" % (RADIO, DEFAULTS['CHANNEL_%s' % RADIO]))
        TXPOWER = eval("self.ROUTER.config.CHANNELS_%s['%s'][1][0]" % (RADIO, DEFAULTS['CHANNEL_%s' % RADIO]))


        # Set up ROUTER
        commands = []

        self.ROUTER.set_restart_wifi_after_commit(False)
        for thisradio in self.ROUTER.config.RADIOS.values():
            # Disable all radios
            commands.append('wireless.radio%s.disabled=1' % thisradio)

        self.ROUTER.commit_uci_commands(*commands)

        self.ROUTER.set_radio_parameters(
            radio=RADIO,
            disabled=0,
            country=COUNTRY,
            channel=CHANNEL,
            htmode=HTMODE,
            txpower=TXPOWER,
            hwmode=HWMODE
            )

        self.ROUTER.set_restart_wifi_after_commit(True) # Allow last commit to restart wifi

        self.ROUTER.set_access_parameters(self.SSID, self.Passphrase, RADIO, ENCRYPTION, False)


        # Set up STB

        self.configure_stb_wifi(self.SSID, REGION, COUNTRY, self.Passphrase, STBENCRYPTION)



        self.STB.reboot_stb("2 minutes")


    def _get_random_chars(self, size=16, chars=string.ascii_letters + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))
    


    def check_ready(self, dieonfail=False, *args, **kwargs):
        #Update help

        ip_pc = kwargs.get('ip_pc', self.PC.get_ip_address())
        ip_stb = kwargs.get('ip_stb', self.STB.get_interface_attribute('ip'))

        ret = False
        
        # Check if wifi_router can ping STB

        stb_to_pc = self.STB.send_command_over_debug_and_return_output("ping -c 1 %s > /dev/null ; echo $?" % ip_pc)
        if "1" in stb_to_pc:
            stb_to_pc = 1
        else:
            stb_to_pc = 0
            


        pc_to_stb = self.PC.execute_command("ping -c 1 %s > /dev/null ; echo $?" % ip_stb, return_rc=True, return_stdout=False)

        
        self._log("STB pinging PC = %s" % ('OK' if stb_to_pc==0 else 'BAD'))
        self._log("PC pinging STB = %s" % ('OK' if pc_to_stb==0 else 'BAD'))

        # Check if STB can ping wifi_router
        ret = not (stb_to_pc or pc_to_stb)

        if dieonfail and not ret:
            raise WiFiTestStationError("Failed two way check: STB to PC = %s; PC to STB = %s" % (('OK' if stb_to_pc==0 else 'BAD'),('OK' if pc_to_stb==0 else 'BAD')))
        else:
            return ret
    




    def udp_throughput_test(self, *args, **kwargs):
        """ Conduct a UCP iperf throughput test from PC to STB
        Returns the bandwidth achieved that fell within the allowable drop_limit percentage
        Only STBIN is relevant for this test
        TODO

        Supported Keywords Parameters:-

        drop_limit = 0                          - Percentage of dropped packets allowed before a fail is registered
        iperf_location = <string>               - Location on Linuxbox for iperf binary. If not set it will use the 'tool' setting from LinuxBox config
        suppress_prepare = [${True}|${False}]   - Stop this keyword from preparing the STB if it was not Ready.  Raises error instead
        
        """
        
        DROPLIMIT = float(kwargs.get('DROPLIMIT', 0.0))
        MAJORSTEP = int(kwargs.get('MAJORSTEP', 8))

               
               
        step = MAJORSTEP
        bandwidth = int(self._run_brief_tcp_stbin())
        self._log("Starting bandwidth = %s" % str(bandwidth))
        

        result = 100
        testcount = 0

        # Step back from start point until a passing value is found
        bandwidth += step
        while result > DROPLIMIT:
            bandwidth = bandwidth - step
            result = self._run_udp_stbin(bandwidth=bandwidth)
            testcount = testcount + 1
            self._log("1: bandwidth = %s, Drop=%spct" % (str(bandwidth), str(result)), "DEBUG")


        had_fail_flag = False # Track our first failure

        # Alternate between forward and backward to find the perfect value, with split half technique
        while abs(step) >= 1:
            self._log("Start Step=%s" % str(step), "DEBUG")


            bandwidth = bandwidth + step
            result = self._run_udp_stbin(bandwidth=bandwidth)
            testcount = testcount + 1
            if result <= DROPLIMIT:
                # Result was within limit
                if had_fail_flag:
                    # We've failed previously, so half the step size but keep going up
                    step = abs(step)
                    step = step / 2
                else:
                    # We've never failed before so step stays the same
                    step = MAJORSTEP
            else:
                # Result failed the limit check, so set the flag
                had_fail_flag = True
                if abs(step) > 1:
                    # We've not got to a single step yet, so half the set size and go backwards
                    step = -(abs(step / 2))
                else:
                    # We're already at a single step so go back one step and recheck
                    step = -1
                    
            self._log("2: bandwidth = %s, drop=%spct" % (str(bandwidth), str(result)), "DEBUG")

            self._log("End Step=%s" % str(step), "DEBUG")



        self._log("highest good bandwidth = %sMbps, number of tests = %s" % (str(bandwidth), str(testcount)))
        
        return "%sMbps" % str(bandwidth), "%spct" % str(result)
    
        

    def _run_udp_stbin(self, *args, **kwargs):

        iperf_location = kwargs.get('iperf_location', self.PC.get_tool_location('iperf'))
        ip_stb = kwargs.get('ip_stb', self.STB.get_interface_attribute('ip'))

        suppress_prepare = kwargs.get('suppress_prepare', False)
        BANDWIDTH = kwargs.get('bandwidth')

        got_result_flag = False
        attempts = 0
        max_attempts = 3

        while not got_result_flag:
            attempts += 1

            # kill iperf on STB then start up iperf server
            self.STB.send_command_over_debug("killall iperf")
            self.STB.send_command_over_debug("rm %s" % self._iperf_stb_output)
            self.STB.send_command_over_debug("%s/iperf -s %s > %s &" % (self._stb_tools, self._iperf_server_udp_options, self._iperf_stb_output))


            # Run iperf client on PC
            client_output = self.PC.execute_command("%s/iperf -c %s %s %sm" % (iperf_location, ip_stb, self._iperf_client_udp_options, str(BANDWIDTH)))

            # Kill iperf on PC and return the output
            self.STB.send_command_over_debug("killall iperf")
            server_output = self.STB.send_command_over_debug("cat %s" % self._iperf_stb_output)
            self.STB.send_command_over_debug("rm %s" % self._iperf_stb_output)

            self._log("Output from UDP test = %s" % client_output, "DEBUG")

            rets = client_output.split(",")
            try:
                ret = float(rets[12])
                got_result_flag = True
            except IndexError:
                if attempts == max_attempts:
                    raise WiFiTestStationError("Unable to obtain UDP throughput data")
        return ret




    def _run_brief_tcp_stbin(self, *args, **kwargs):

        # Need to run a very quick TCP throughput test and return the value rounded down to the nearest Mb
        average = self.tcp_throughput_test(data_direction='STBIN',
            iperf_client_options = "-p 2333 -t 2 -i 2 -f m -w 85.3k")

        return int(float(average))



    def tcp_throughput_test(self, *args, **kwargs):
        """ Conduct a TCP iperf throughput test from PC to STB or from STB to PC
        TODO

        Supported Keywords Parameters:-

        data_direction = [STBIN|STBOUT]              - Data flow direction. Defaults to STBIN
        iperf_location = <string>               - Location on Linuxbox for iperf binary. If not set it will use the 'tool' setting from LinuxBox config
        suppress_prepare = [${True}|${False}]   - Stop this keyword from preparing the STB if it was not Ready.  Raises error instead
        
        """

        # Handle keywords
        iperf_location = kwargs.get('iperf_location', self.PC.get_tool_location('iperf'))
        ip_pc = kwargs.get('ip_pc', self.PC.get_ip_address())
        ip_stb = kwargs.get('ip_stb', self.STB.get_interface_attribute('ip'))
        iperf_client_options = kwargs.get('iperf_client_options', self._iperf_client_tcp_options)
        iperf_server_options = kwargs.get('iperf_server_options', self._iperf_server_tcp_options)

        suppress_prepare = kwargs.get('suppress_prepare', False)

        data_direction = kwargs.get('data_direction', 'STBIN')
        if data_direction.upper() <> 'STBIN' and data_direction.upper() <> 'STBOUT':
            raise WiFiTestStationError("'%s' is not a recognised 'data_direction'.  Options are 'STBIN' or 'STBOUT'" % data_direction)


        # Check if the STB is ready
        if not self.STB.get_stateflag("WiFiDownloadsReady"):
            if suppress_prepare:
                raise WiFiTestStationError("The STB is not in the 'Ready' state")
            else:
                self.prepare_stb()

        average = 'ERROR'

        client_output = "Warning: No client output!"
        server_output = "Warning: No server output!"

        if data_direction.upper() == 'STBOUT':

            # kill iperf on PC then start up iperf server
            self.PC.execute_command("killall iperf")
            self.PC.execute_command("rm %s" % self._iperf_pc_output)
            self.PC.execute_command("%s/iperf -s %s > %s &" % (iperf_location, iperf_server_options, self._iperf_pc_output))


            # Run iperf client on STB

            client_output = self.STB.send_command_over_debug_and_return_output("%s/iperf -c %s %s" % (self._stb_tools, ip_pc, iperf_client_options), timeout="3 minutes")

            self._log(client_output)


            # Kill iperf on PC and return the output
            self.PC.execute_command("killall iperf")
            server_output = self.PC.execute_command("cat %s" % self._iperf_pc_output)
            self.PC.execute_command("rm %s" % self._iperf_pc_output)



        else:
            # kill iperf on STB then start up iperf server
            self.STB.send_command_over_debug("killall iperf")
            self.STB.send_command_over_debug("rm %s" % self._iperf_stb_output)
            self.STB.send_command_over_debug("%s/iperf -s %s > %s &" % (self._stb_tools, iperf_server_options, self._iperf_stb_output))
            
            
            # Run iperf client on PC
            client_output = self.PC.execute_command("%s/iperf -c %s %s" % (iperf_location, ip_stb, iperf_client_options))
            
            # Kill iperf on PC and return the output
            self.STB.send_command_over_debug("killall iperf")
            server_output = self.STB.send_command_over_debug("cat %s" % self._iperf_stb_output)
            self.STB.send_command_over_debug("rm %s" % self._iperf_stb_output)

        self._log(client_output)
        self._log(server_output)
        average = PP.get_iperf_tcp_data(client_output)

        return average


    def configure_stb_wifi(self, ssid, region="GR-E11", country="GB", passphrase="C0meGe750me!", security_mode="WPA2-PSK-AES"):
        commands = []

        commands.append("libconfig-set NORFLASH.WIRELESS_REGION '%s'" % region)
        commands.append("libconfig-set NORFLASH.WIRELESS_COUNTRY '%s'" % country)
        commands.append("libconfig-set NORFLASH.WIRELESS_SSID '%s'" % ssid)
        commands.append("libconfig-set NORFLASH.WIRELESS_PASSPHRASE '%s'" % passphrase)
        commands.append("libconfig-set NORFLASH.WIRELESS_SECURITY_MODE '%s'" % security_mode)
        commands.append("netman update_config")

        self._log(commands, "DEBUG")
        

        self.STB.send_commands_over_debug(*commands)

        





    def get_property(self, property):
        # type: (object) -> object
        """  Get a WTS property at runtime

        Examples:
        | ${serial}=	| Get property	| serialnumber	|
        | ${family}=	| Get property	| family	|

        """
        property = '_' + property.lower()
        self._log("Getting property '%s'" % property, 'DEBUG')
        return getattr(self, property)
        
    def set_property(self, property, value):
        """  Set a WiFiTestStation property at runtime

        Available properties (and their defaults) are:-

        === iperf properties ===
        - iperf_client_command 	= '-p 2333 -t 20 -i 2 -f m -w 85.3k'
        - iperf_server_command	= '-p 2333'

        Examples:
        | Set property	| serialnumber	| J12121991829812	|
        | Set property	| family	| ${family}		|

        """
        property = '_' + property
        self._log("Setting property '%s'to '%s'" % (property, value), 'DEBUG')
        setattr(self, property, value)

    def prepare_stb(self, family=None, force=False):
        # Prepare the STB for iperf testing and possibly wl?
        # include downloading tools to /tmp/wifi folder

        if (self.STB.get_stateflag("WiFiDownloadsReady")) and not force:
            self._log("No need to prepare stb", "DEBUG")
            return

        if family is None:
            self._log("No 'family' defined so asking STB....")
            if not self.STB._debug is None:
                self._log("... over debug connection")
                family = ''.join((self.STB.send_command_over_debug_and_return_output("cat /proc/hwfamily")).splitlines())
            else:
                self._log("... over telnet connection")
                family = ''.join((self.STB.send_command_and_return_output("cat /proc/hwfamily", self._stb_wifi_interface)).splitlines())

        self._log("Family = '%s'" % family, "DEBUG")

        supported_list = ["Ax0xx", "Ax5x", "Ax4x", "Ax6x", "Z31x"]

        if family in supported_list:
            download_from = "%s/%s" % (self._download_location, family)
            self._log("Grabbing files from '%s'" % download_from)
            if not self.STB._debug is None:
                self._log("Preparing STB over debug")
                command = "mkdir %s; wget %s/iperf ; chmod +x %s/iperf" % (self._stb_tools, download_from, self._stb_tools)
                
                self.STB.send_command_over_debug("mkdir %s; cd %s ; wget %s/iperf ; chmod +x %s/iperf" % (self._stb_tools, self._stb_tools, download_from, self._stb_tools))
                if self._wifi_type == "BCM":
                    self.STB.send_command_over_debug("mkdir %s; cd %s ; wget %s/wl ; chmod +x %s/wl" % (self._stb_tools, self._stb_tools, download_from, self._stb_tools))
            else:
                self._log("Preparing STB over telnet")
                self.STB.send_command("mkdir %s; cd %s ; wget %s/iperf ; chmod +x %s/iperf" % (self._stb_tools, self._stb_tools, download_from, self._stb_tools))
                if self._wifi_type == "BCM":
                    self.STB.send_command("mkdir %s; cd %s ; wget %s/wl ; chmod +x %s/wl" % (self._stb_tools, self._stb_tools, download_from, self._stb_tools))
            self.STB.set_stateflag("WiFiDownloadsReady")

        else:
            error = "Unknown 'family' '%s'. Supported list = '%s'" % (family, supported_list)
            self._log(error, "WARN")
            raise WiFiTestStationError(error)



    def set_stb(self, STB):
        # Check STB is an instance of the STB object
        if isinstance(STB, STBClass):
            self.STB = STB
        else:
            raise WiFiTestStationError("Incorrect object type. STB must be derived from the STB library.")

    def set_router(self, Router):
         # Check Router is an instance of the Router object
        if isinstance(Router, RouterClass):
            self.ROUTER = Router
        else:
            raise WiFiTestStationError("Incorrect object type. Router must be derived from the Router library.")

    def _check_stb_debug(self):
        # Check if debug is connected and if we are logged in on it
        pass


    def add_attenuator(self, ATTENUATOR):
        if isinstance(ATTENUATOR, AttenuatorControlClass):
            self.Attenuators.append(ATTENUATOR)
        else:
            raise WiFiTestStationError("Incorrect object type. Attenuator must be derived from the Attenuator library.")


    def set_pc(self, PC):
         # Check PC is an instance of the PC object
        if isinstance(PC, LinuxBoxClass):
            self.PC = PC
        else:
            raise WiFiTestStationError("Incorrect object type. PC must be derived from the LinuxBox library.")

    def test_log(self, message, level='INFO'):
        self._log(message,level)

    def check_link_stability(self, howlong="2 minutes"):

        howmanytimes = int(utils.timestr_to_secs(howlong) / 10)
        self.STB.send_commands_over_debug("echo '' > /tmp/linktemp.txt")
        for x in range(howmanytimes):
            nowtime = time.time()
            self.STB.send_commands_over_debug("(netman info wlan0 | grep Status | awk {'print $3'}) >> /tmp/linktemp.txt && (netman get_wifi_aps wlan0 2>/dev/null | grep 'Signal: Quality') >> /tmp/linktemp.txt")
            if time.time() < nowtime+10:
                time.sleep((nowtime+10)-time.time())
        output = self.STB.send_command_over_debug_and_return_output("cat /tmp/linktemp.txt", timeout="30 seconds")
        stability = ""
        
        if "READY" in output:
            stability = "SOLID"
        if "LINK_DOWN" in output:
            if stability=="SOLID":
                stability="UNSTABLE"
            else:
                stability="DEAD"

        return stability

    def _log(self, message, level='INFO'):
        """ Valid log levels are
        `TRACE` =   Lowest level of log message.  Not logged normally
        `DEBUG` =   Used for debug messages.  Not logged normally
        `INFO`  =   Used for information messages.  Normally shown in standard log
        `WARN`  =   Used for warnings.  Shown in standard and summery log
        """

        logger.write(message, level)


""" What needs to be done


configure_attenuation
    will take all necessary variables e.g. attenuator (assume all), value
    will check if they are already set correctly, if not set them
    validate the changes

read_router_status
    inputs: routertype
    returns: dictionary of returned status items
    ? check what we want to read and how
    ?  May we need to do this asynchronously? i.e. read half way through a data transfer?
        If so, have a way to dump it to file and read it later, so send a pause;dump to file before the transfer starts

read_stb_status
    returns: dictionary of returned status items
    ? check what we want to read and how
    ?  May we need to do this asynchronously? i.e. read half way through a data transfer?
        If so, have a way to dump it to file and read it later, so send a pause;dump to file before the transfer starts

tcp_throughput_test
    inputs:- direction wrt STB, how long for
    ouputs:- full table of results, post processed average
    put in plenty of error checking at each stage

udp_throughput_test
    inputs:- direction wrt STB, how long for
    ouputs:- full table of results, post processed average
    put in plenty of error checking at each stage





"""
class WiFiTestStationError(RuntimeError):
    pass


class Enum(set):
    def __getattr__(self, name):
        if name in self:
            return name
        raise AttributeError
