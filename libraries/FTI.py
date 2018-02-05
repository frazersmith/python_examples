"""
Classes:
    FTI - Factory Test Image aminorobot test library

Exceptions:
    FatalFtiError - An exception to cover fatal library errors
"""

# Robot libraries import
import robot.libraries.Telnet as Telnet
from robot.libraries.Telnet import NoMatchError
from robot.api import logger
from robot.version import get_version
from robot import utils as robot_utils
import robot.libraries.OperatingSystem as OperatingSystem
from robot.errors import ExecutionFailed

# Python Library Imports
import time
import errno

# Aminorobot library imports
import Debug

__version__ = "0.0 alpha"


class FTI(object):
    """     Amino FTI class by Tim Curtis

    The FTI aminorobot class is a sub set of the STB library, cut down to
    commands which are relevant for testing the post 4.4.x (new world)
    factory test image.

    This class will only use a telnet connection for communication to the
    STB as this is how the TeraTerm scripts access the FTI.
    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):

        self._os = OperatingSystem.OperatingSystem()

        self._shortname = 'stb_unknown'

        self._board_id = None

        self._iface = {
            'ip': None,
            'mac': None,
            'name': None,
            'serial': None
        }

        self._wifi = {
            'device': None,
            'mac': None
        }

        self._model_conf = {
            'Family': None,
            'Model': None,
            'BoardConfig': None,
            'Group': None
        }

        self._mem_conf = {
            'NAND': None,
            'eMMC': None,
            'NOR': None,
            'RAM': None
        }

        self._hdd_conf = {
            'Device': 'sda',
            'Model': None,
            'FwRev': None,
            'SerialNo': None,
            'Size': None
        }

        self._led_conf = []
        self._led_aliases = []
        self._usb_conf = []

        self._telnet_conn = None
        self._telnet_opts = dict(
            encoding='ISO-8859-15',
            default_log_level='TRACE',
            encoding_errors='Strict',
            terminal_emulation=True,
            terminal_type='vt102',
            window_size='400x100',
            prompt='FT>',
            port=4321
        )

        self._debug = None
        self._debugport = None

    def __del__(self):
        if self._debug:
            self._debug.close()

        if self._telnet_conn:
            self._close_telnet()

    def get_is_pvr(self):
        """     Gets if the unit under test is a PVR or not

        Returns if the unit under test is a PVR STB. By iterating the _hdd_conf
        dictionary, if any of the HDD properties are not set, then treat it as
        a streamer.

        See example for how to skip a test if the UUT is a streamer

        Examples:
        | ${is_pvr}=        | FTI.Get Is Pvr |                |
        | Run Keyword if    | not ${is_pvr}  | Pass Execution |
        """
        ret = True
        for key in self._hdd_conf.keys():
            if self._hdd_conf[key] == None:
                ret = False

        return ret

    def send_fti_command(self, command, close_telnet=False):
        """     Send a single command to the FTI and return the response

        Examples:
        | ${mac_get}=    | FTI.Send Fti Command  | mac get      |
        | ${ser_get}=    | FTI.Send Fti Command  | serial get   |
        | Should Contain | ${mac_get}            | ${mac_addr}  |
        | Should Contain | ${ser_get}            | ${serial_no} |
        """
        logger.debug('FTI: Sending command "%s"' % command)

        if not self._telnet_conn:
            self._start_telnet()

        output = ''

        try:
            output += self._telnet_conn.write("%s" % command)
            output += self._telnet_conn.read_until_prompt()
        except (AssertionError, NoMatchError, IOError, EOFError) as error:
            if str(error) == 'telnet connection closed':
                raise FatalFtiError('Telnet connection closed, exiting!')
            elif error.errno == errno.EPIPE:
                raise FatalFtiError('Broken Pipe, Telnet has died, exiting')
            else:
                logger.debug('FTI: "FT>" prompt not seen in timeout, continuing')
                logger.warn('FTI: resetting Telnet connection')
                self._close_telnet()
                time.sleep(2.5)

        logger.debug('output = "%s"' % (output))

        if close_telnet:
            # sleep to prevent the connection being closed while it is in use
            time.sleep(1)
            self._close_telnet()

        return output

    def send_fti_commands(self, *commands):
        """     Sends multiple commands over the telnet connection

        Sends multiple commands to the FTI and returns all of the response
        from all of the commands

        Examples:
        | ${ret_0}= | FTI.Send Fti Commands  | mac get   | serial get    |
        | ${ret_1}= | FTI.Send Fti Commands  | prov get  | system reboot |
        """
        ret = ''

        for command in commands:
            ret += self.send_fti_command(command)
            time.sleep(0.5)

        return ret

    def send_bare_fti_command(self, command):
        """     Sends bare a command to the FTI, and return the output

        Sends a command and returns the response, regardless of if the
        FT> prompt is returned, this has been specifically put in as a
        workaround for the 'fcfg list' test, as this was causing problems
        on trying to read until a prompt is seen.

        Examples:
        | ${output}=     | FTI.Send Bare Fti Command | fcfg list       |
        | Should Contain | ${output}                 | SERIAL_CONSOLE  |
        """
        logger.debug('FTI: sending bare command  "%s"' % command)

        if not self._telnet_conn:
            self._start_telnet()

        output = self._telnet_conn.write("%s" % command)

        output += self._telnet_conn.read()

        return output

    def _start_telnet(self):
        """     Initiates a telnet connection to the UUT

        Args:
            None
        Returns:
            Nothing
        """
        logger.debug('FTI: Starting Telnet Connection')
        try:
            self._telnet_conn = Telnet.Telnet(newline='\n',
                                              timeout='15 seconds')

        except:
            raise FatalFtiError('Failed to create Telnet.Telnet Instance')

        try:
            self._telnet_conn.open_connection(self._iface['ip'],
                                              **self._telnet_opts)

        except RuntimeError:
            raise FatalFtiError('Failed to open Telnet Connection')

    def _close_telnet(self):
        """     Closes the telnet connection and clears the variable

        Args:
            None
        Returns:
            Nothing
        """
        logger.debug('FTI: closing telnet connection')

        self._telnet_conn.close_all_connections()
        self._telnet_conn = None

    def get_iface_attribute(self, attribute):
        """     Returns the value of a named interface attrribute

        Valid Parameters are:
            [ ip, mac, name, serial ]

        Examples:
        | ${ip_addr}=     | FTI.Get Iface Attribute   | ip     |
        | ${mac_addr}=    | FTI.Get Iface Attribute   | mac    |
        | ${iface_name}=  | FTI.Get Iface Attribute   | name   |
        | ${serial_no}=   | FTI.Get Iface Attribute   | serial |
        """
        try:
            ret = self._iface[attribute]
            return ret
        except KeyError:
            logger.debug('FTI: Invalid param passed to get_interface_attr')
            return ''

    def _set_iface_conf(self, ip_addr='', mac='', name='', serial=''):
        """     Sets the network interface configuration

        Args:
            ip_addr - IPv4 address
            mac     - MAC address of the UUT
            name    - name of the interface
            serial  - UUT serial number
        Returns:
            Nothing
        """
        self._iface['ip'] = ip_addr
        self._iface['mac'] = mac
        self._iface['name'] = name
        self._iface['serial'] = serial

        logger.debug('FTI: Set iface attributes dict: %s' % str(self._iface))

    def get_wifi_attribute(self, attribute):
        """
        docstring
        """
        try:
            ret = self._wifi[attribute]
            return ret
        except KeyError:
            logger.debug('FTI: Invalid param passed to get_wifi_attr')
            return ''

    def _set_wifi_conf(self, device='', mac=''):
        """     Sets the wifi configuration information from the UUT

        Args:
            device - device infor from running 'wifi device' from the FTI
            mac    - the mac address of the wifi card, as reported from
                     running 'wifi mac' from the FTI
        """
        self._wifi['device'] = device
        self._wifi['mac'] = mac

    def get_is_wifi_enabled(self):
        """     Gets if the UUT is wifi enabled

        Examples:
        | ${is_wifi}=   | LM.Get Is Wifi Enabled    |
        """
        ret = True
        for key in self._wifi.keys():
            if self._wifi[key] == None:
                ret = False

        return ret

    def get_model_attribute(self, attribute):
        """     Returns the value of a named model attribute

        Valid Parameters are:
            [ Family, Model, BoardConfig, Group ]

        Examples:
        | ${hw_family}=     | FTI.Get Model Attribute   | Family        |
        | ${hw_model}=      | FTI.Get Model Attribute   | Model         |
        | ${board_config}=  | FTI.Get Model Attribute   | BoardConfig   |
        | ${hw_group}=      | FTI.Get Model Attribute   | Group         |
        """
        try:
            ret = self._model_conf[attribute]
            return ret
        except KeyError:
            logger.debug('FTI: Invalid param passed to get_model_attribute')
            return ''

    def _set_model_conf(self, family='', model='', board_config='', group=''):
        """     Sets the model configuration for the UUT

        Args:
            family       - HW family e.g. 'Ax5x'
            model        - HW model e.g. 'A550'
            board_config - HW board config e.g. '0x0607'
            group        - HW group e.g. 'A550,Ax5x,BCM'
        Returns:
            Nothing
        """
        self._model_conf['Family'] = family
        self._model_conf['Model'] = model
        self._model_conf['BoardConfig'] = board_config
        self._model_conf['Group'] = group

    def get_memory_attribute(self, attribute):
        """     Returns the value of a named memory attribute

        Valid Parameters are:
            [ NAND, NOR, eMMC, RAM ]

        Examples:
        | ${nand_size}=     | FTI.Get Memory Attribute      | NAND      |
        | ${ram_size}=      | FTI.Get Memory Attribute      | RAM       |
        | ${nor_size}=      | FTI.Get Memory Attribute      | NOR       |
        | ${emmc_size}=     | FTI.Get Memory Attribute      | eMMC      |
        """
        try:
            ret = self._mem_conf[attribute]
            return ret
        except KeyError:
            logger.debug('FTI: Invalid param passed to get_memory_attribute')
            return ''


    def _set_mem_config(self, nand='', emmc='', nor='', ram=''):
        """     Sets the memory configuration for the UUT

        Args:
            nand - size of the NAND device
            emmc - size of the eMMC device, if supported, else what
                   is reported by the FTI, e.g. 'Not supported'
            nor  - size of the NOR device
            ram  - amount of memory
        Returns:
            Nothing
        """
        self._mem_conf['NAND'] = nand
        self._mem_conf['eMMC'] = emmc
        self._mem_conf['NOR'] = nor
        self._mem_conf['RAM'] = ram

    def get_hdd_attribute(self, attribute):
        """     Returns the value of a named HDD attribute

        Valid Parameters Are:
            [ Model, FwRev, SerialNo, Size ]

        Examples:
        | ${hdd_model}=     | FTI.Get Hdd Attribute  | Model    |
        | ${hdd_fwrev}=     | FTI.Get Hdd Attribute  | FwRev    |
        | ${hdd_serial}=    | FTI.Get Hdd Attribute  | SerialNo |
        | ${hdd_size}=      | FTI.Get Hdd Attribute  | Size     |
        """
        try:
            ret = self._hdd_conf[attribute]
            return ret
        except KeyError:
            logger.debug('FTI: Invalid param passed to get_hdd_attribute')
            return ''

    def _set_hdd_config(self, model='', fwrev='', serial='', size=''):
        """     Sets the UUT HDD configuration

        Args:
            model  - The HDD model string
            fwrev  - The value of FwRev of the HDD
            serial - The serial number of the HDD
            size   - The size of the HDD reported by 'df'
        """
        self._hdd_conf['Model'] = model
        self._hdd_conf['FwRev'] = fwrev
        self._hdd_conf['SerialNo'] = serial
        self._hdd_conf['Size'] = size

    def get_board_id(self):
        """     Returns the board id as set in the fti_ definition file

        Warns via the logger API if this value is not set, then throws
        a fatal exception to prevent damage to the UUT by setting an
        incorrect board id

        Examples:
        | ${board_id}=  | FTI.Get Board Id |
        """
        if self._board_id == None:
            logger.warn('FTI: No board id set for: %s' % self._shortname)
            raise FatalFtiError('FTI library requires Board ID to be set!')

        return self._board_id

    def get_led_numbers(self):
        """     Gets the LED configuration numbers from self._led_conf

        Returns a list of the led numbers as defined in the fti_*.py
        definition file. See example use for iterating the list of LEDs

        Warns via the logger API and returns the empty list if the
        self._led_conf list is empty, as this will not trigger the loop,
        not breaking the test run

        Examples:
        | @{LEDS}= | FTI.Get Led Numbers  |                |             |
        | :FOR     | ${LED}               | IN             | @{LEDS}     |
        | ...      | FTI.Send Fti Command | led on ${LED}  |             |
        | ...      | Sleep                | 5 Seconds      |             |
        | ...      | FTI.Send Fti Command | led off ${LED} |             |
        | ...      | Sleep                | 5 Seconds      |             |
        """

        if len(self._led_conf) == 0:
            logger.warn('FTI: No LED numbers for uut %s' % self._shortname)

        return self._led_conf

    def get_led_aliases(self):
        """     Gets the list of LED aliases from self._led_aliases

        Returns a list of led's identified by the alias, e.g 'power', 'standby'

        Examples:
        | @{LEDS}= | FTI.Get Led Aliases  |                |             |
        | :FOR     | ${LED}               | IN             | @{LEDS}     |
        | ...      | FTI.Send Fti Command | led on ${LED}  |             |
        | ...      | Sleep                | 5 Seconds      |             |
        | ...      | FTI.Send Fti Command | led off ${LED} |             |
        | ...      | Sleep                | 5 Seconds      |             |
        """

        if len(self._led_aliases) == 0:
            logger.warn('FTI: No Led aliases for uut %s' % self._shortname)

        return self._led_aliases

    def get_usb_ports(self):
        """     Gets the numbers of the USB ports in the UUT

        Examples:
        | @{USBS}= | FTI.Get Usb Ports    |                         |         |
        | :FOR     | ${USB}               | IN                      | @{USBS} |
        | ...      | FTI.Send Fti Command | usb hash ${USB} file.ts |         |
        | ...      | Sleep                | 5 Seconds               |         |
        """

        if len(self._usb_conf) == 0:
            logger.warn('FTI: No usb ports defined for: %s' % self._shortname)

        return self._usb_conf

    def capture_debug(self, debugport='default'):
        """     Starts Serial debug capture

        Uses the serial port defined in the fti_*.py definition file to
        capture serial debug.

        Examples:
        | FTI.Capture Debug     |                           |
        | FTI.Capture Debug     | debugport='/dev/ttyUSB1'  |
        """
        if debugport == 'default':
            if not self._debugport:
                raise FatalFtiError('FTI: Debug port not set')
            else:
                debugport = self._debugport

        try:
            self._debug = Debug.Debug(appendsuffix=self._shortname, terminal_emulation=False)
            self._debug.open_connection(commport=debugport)
            logger.info('FTI: Started Debug capture port=%s' % debugport)

        except Debug.DebugError as debug_error:
            raise FatalFtiError('Failed to capture debug: %s' % debug_error)

    def add_debug_marker(self, debug_marker):
        """     Adds a marker to the serial debug capture to indicate run status

        Examples:
        | ${test_name}=         | Set Variable               | "serial" |
        | FTI.Add Debug Marker  | Starting test ${test_name} |          |
        | FTI.Add Debug Marker  | Ending Test ${test_name}   |          |
        """
        ret = 0
        if not self._debug:
            logger.warn('FTI: Cannot add debug marker if not capturing debug')
            ret = -1

        else:
            logger.trace('FTI: marking debug with "%s"' % debug_marker)
            self._debug.debug_marker(debug_marker)

        return ret

    def validate_config(self):
        """     Validate the configuration set in the fti_* definition file

        Examples:
        | FTI.Validate Config   |
        """
        logger.debug('FTI: Validating UUT configuration')

        for key in self._iface.keys():
            if self._iface[key] == None:
                raise FatalFtiError('Configuration Item Missing %s' % key)

        for key in self._model_conf.keys():
            if self._model_conf[key] == None:
                raise FatalFtiError('Configuration Item Missing %s' % key)

        for key in self._mem_conf.keys():
            if self._mem_conf[key] == None:
                raise FatalFtiError('Configuration Item Missing %s' % key)

        if self._board_id == None:
            raise FatalFtiError('_board_id is not set in %s.py' %
                                self._shortname)

    def upgrade_fti(self, software_uri):
        """     Use a HTTP URI install a new FTI using 'system upgrade $URI'

        Uses write_bare rather than send FTI command as there is no response
        code within the timeout, the connection is then closed, as the upgrade
        will continue with the telnet connection closed. The method then sleeps
        for 60 seconds to allow the image to download, then pings until the UUT
        comes back up from the upgrade

        Examples:
        | FTI.Upgrade Fti   | http://host/mc2.mcfs  |
        """
        logger.debug('FTI: Upgrading using URI %s' % software_uri)

        if not self._telnet_conn:
            self._start_telnet()

        self._telnet_conn.write_bare('system upgrade "%s" \n' % software_uri)

        self._close_telnet()

        logger.debug('FTI: upgrade_fti: Sleeping for 60 seconds')
        time.sleep(60)

        self.ping_stb_until_alive()

        logger.debug('FTI: upgrade_fti: waiting for telnet connection')
        time.sleep(10)

    def reboot_stb(self, ping_timeout='2 minutes'):
        """     Reboot the STB using the FTI telnet interface

        Runs the command 'system reboot', sleeps for 20 seconds, then pings
        the STB until it comes back up from the reboot.

        Examples:
        | FTI.Reboot Stb    |                            |
        | FTI.Reboot Stb    | ping_timeout='3 minutes'   |
        """
        logger.debug('FTI: Rebooting UUT')

        ret = self.send_fti_command('system reboot', close_telnet=True)

        if 'OK' not in ret:
            raise FatalFtiError('Failed to reboot UUT')
        else:
            logger.debug('FTI: reboot_stb: sleeping for 20 seconds')
            time.sleep(20)
            self.ping_stb_until_alive(timeout=ping_timeout)

    def ping_stb_until_alive(self, timeout='2 minutes', die_on_fail=True):
        """     Pings the UUT IP address, until it becomes available

        Examples:
        | FTI.Ping Stb Until Alive  |                     |                   |
        | FTI.Ping Stb Until Alive  | timeout='3 minutes' |                   |
        | FTI.Ping Stb Until Alive  | timeout='5 minutes' | die_on_fail=False |
        """
        logger.debug('FTI: Pinging STB until alive with timeout %s' % timeout)

        ip_addr = self.get_iface_attribute('ip')
        start_time = time.time()
        end_time = start_time + robot_utils.timestr_to_secs(timeout)

        while time.time() < end_time:
            if self._ping(ip_addr) == 0:
                ping_time = int(time.time() - start_time)
                logger.debug('FTI: Ping success after %ss' % ping_time)
                return ping_time
            else:
                time.sleep(5)

        if die_on_fail:
            raise FatalFtiError('Failed to ping uut after %s' % timeout)
        else:
            return -1

    def _ping(self, ip_addr):
        """     Send a single ping command

        Sends a single ping command using the shell command "ping -c 1 $ip_addr"

        Args:
            ip_addr - IPv4 address to be pinged

        Returns:
            on success - 0
            on failure - 1
        """
        return_code = self._os.run_and_return_rc('ping -c 1 %s' % ip_addr)

        return 0 if return_code == 0 else 1


class FatalFtiError(ExecutionFailed):
    """     Raise a fatal FTI exception

    Inherits ExecutionFailed and passes exit=True to initialisation
    to stop the test run.

    Args:
        message - message to be passed to logger.warn
    """
    def __init__(self, message=''):
        logger.warn('FTI: %s' % message)

        ExecutionFailed.__init__(self, message, exit=True)
