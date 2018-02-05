"""
DHCP aminorobot module
Classes:
    DHCP ( LinuxBox ) - The DHCP automation library

Functions:
    get_option_type  - get formatting type of DHCP option
    check_is_ip_addr - Check vailidity of IPv4 address string

Exceptions:
    FatalDhcpError ( ExecutionFailed ) - fatal DHCP configuration error

Data Structures:
    DHCP_OPTIONS ( dict ) - Defines the data types for the DHCP options
    TIME_ZONES   ( dict ) - Time zone strings and their POSIX identifiers
"""
# Robot libraries
from robot.api import logger
from robot.version import get_version
from robot.errors import ExecutionFailed
from robot.libraries.BuiltIn import BuiltIn

# Standard python libraries
import os
import re
import glob
import pytz
from datetime import datetime

# aminorobot libraries
from libraries.LinuxBox import LinuxBox

__version__ = "0.1 beta"

class DHCP(LinuxBox):
    """ Amino DHCP configuration library by Tim Curtis

    This library is designed for use with Robot Framework.

    This is an extension of the LinuxBox library
    """
    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):
        LinuxBox.__init__(self)

        self.restart_command = ''
        self.dhcpd_path = ''
        self.auto_path = '/etc/dhcp/auto/'
        self.include_path = ''
        self.robot_auto_file = '/etc/dhcp/auto/robot-auto.cfg'

        self._unit_under_test = None
        self._ip_address = None
        self._mac_address = None

        self._setup_dhcp()

    def _setup_dhcp(self):
        """     Helper method to setup the files for the DHCP libraries

        Args:
            None
        Returns:
            Nothing
        """
        logger.debug('Setting up DHCP library')

        self.execute_command('mkdir -p /etc/dhcp/auto')
        self.execute_command('chmod 777 /etc/dhcp/auto')
        self.execute_command('touch /etc/dhcp/auto/robot-auto.cfg')
        self.execute_command('chmod 777 /etc/dhcp/auto/robot-auto.cfg')

    def add_host(self, infolist):
        """     Add Host    ${init_args}

        Add a new host to the DHCP server, the UUT will need to be removed from
        any other DHCP servers on the network, or the test will not work

        Example:
        | ${init_args}= | UUT.Get Dhcp Init Args                                |
        | DHCP.Add Host | ${init_args}                                          |
        | DHCP.Add Host | ['stb_4a7099', '10.172.249.103', '00:02:02:4A:70:99'] |
        """
        if not self._unit_under_test:
            self._set_obj_properties(infolist)

        logger.debug('DHCP: add_host values:')
        logger.debug('\tuut = "{0}"'.format(self._unit_under_test))
        logger.debug('\tip  = "{0}"'.format(self._ip_address))
        logger.debug('\tmac = "{0}"'.format(self._mac_address))

        if not self._check_is_auto_included():
            msg = 'you must add \'include "%s";\' in dhcpd.conf' % (self.robot_auto_file)
            logger.warn(msg)
            raise FatalDhcpError('DHCP: Need to include robot-auto.cfg!')

        if not os.path.exists(self.auto_path):
            logger.info('DHCP: Creating working dir: {0}'
                        .format(self.auto_path))
            try:
                os.makedirs(self.auto_path)
            except OSError:
                logger.info('DHCP: permission error, allowing chmod ugo+w')
                self.execute_command('mkdir -p {0}'.format(self.auto_path))
                self.execute_command('chmod -R ugo+w {0}'
                                     .format(self.auto_path))

        if not os.path.isfile(self.robot_auto_file):
            logger.info('DHCP: creating file: "{0}"'
                        .format(self.robot_auto_file))
            with open(self.robot_auto_file, 'w') as auto_file:
                auto_file.write('include "/etc/dhcp/auto/dummy.cfg";\n')

        dummy_file = '/etc/dhcp/auto/dummy.cfg'
        if not os.path.isfile(dummy_file):
            logger.info('DHCP: dummy.cfg creating: "{0}"'.format(dummy_file))
            open(dummy_file, 'a').close()

        new = []
        new.append('host {0}\n'.format(self._unit_under_test))
        new.append('{\n')
        new.append('\tvendor-option-space AMINO;\n')
        new.append('\thardware ethernet {0};\n'.format(self._mac_address))
        new.append('\tfixed-address {0};\n'.format(self._ip_address))
        new.append('}\n')

        with open(self.include_path, 'w+') as auto_cfg:
            for line in new:
                auto_cfg.write(line)

        with open(self.robot_auto_file, 'r') as main_conf:
            main_conf_lines = main_conf.readlines()

        is_present = False

        for line in main_conf_lines:
            if self._unit_under_test in line:
                is_present = True

        if not is_present:
            main_conf_lines.append('include "{0}";'.format(self.include_path))

            with open(self.robot_auto_file, 'w') as conf_file:
                for line in main_conf_lines:
                    conf_file.write(line)
        else:
            logger.warn('DHCP: UUT is already present in robot-auto.cfg!')

    def remove_host(self):
        """ Remove UUT Host from the test DHCP server

        this removes the UUT from the test DHCP server, this call should be
        made in the SUITETEARDOWN to ensure that the library cleans up any
        additions made running tests, even if one of the tests fails.

        Example:
        | DHCP.remove host |
        """
        logger.info('DHCP: remove_host : "{0}"'.format(self._unit_under_test))

        with open(self.robot_auto_file, 'r') as conf_file:
            conf_lines = conf_file.readlines()

        for index, line in enumerate(conf_lines):
            if self._unit_under_test in line:
                del conf_lines[index]

        with open(self.robot_auto_file, 'w') as new_conf_file:
            for line in conf_lines:
                new_conf_file.write(line)

        try:
            os.remove(self.include_path)
        except OSError:
            logger.warn('DHCP: Failed to remove UUT host file: {0}'
                        .format(self.include_path))

    def add_option(self, option_name, option_value=''):
        """     Add option    ${option_name}    ${option_value}

        Add a single DHCP option to the test server. Defined by the 2 keyword
        parameters see example. This keyword will validate the option type
        being added and add the correct syntax for that option type. Passing a
        single option, with no option_value parameter will add the option to
        the DHCP configuration, and set the value to null, see the final
        example usage for how to use this.

        to add the following lines:
            option AMINO.software_uri "http://server/mc2.mcfs";
            option AMINO.STBrc-mcast-port 12321;
            option AMINO.STBrc-mcast-address 225.100.0.214;
            option AMINO.timezone "";

        Example:
        | DHCP.Add Option   | AMINO.software_uri        | http://server/mc2.mcfs   |
        | DHCP.Add Option   | AMINO.STBrc-mcast-port    | 12321                    |
        | DHCP.Add Option   | AMINO.STBrc-mcast-address | 225.100.0.214            |
        | DHCP.Add Option   | AMINO.timezone            |                          |
        """
        logger.debug('DHCP: add_option parameters')
        logger.debug('\tUUT: "{0}"'.format(self._unit_under_test))
        logger.debug('\tOption Name: "{0}"'.format(option_name))
        logger.debug('\tOption Value: "{0}"'.format(option_value))

        option_type = get_option_type(option_name, option_value)

        if option_type == 2:
            logger.warn('DHCP: option_name in Add Option is not recognised!')
        elif option_type == 3:
            logger.warn('DHCP: option_value passed to Add Option is invalid!')
        else:
            logger.debug('DHCP: Add Option: option passed verification')

        with open(self.include_path, 'r') as conf_file:
            conf_lines = conf_file.readlines()

        # pop() removes the closing '}' of the host definition
        conf_lines.pop()

        if not option_type == 'text':
            conf_lines.append('\toption {0} {1};\n'.format(option_name, option_value))
        else:
            conf_lines.append('\toption {0} "{1}";\n'.format(option_name, option_value))

        conf_lines.append('}\n')

        with open(self.include_path, 'w') as new_conf_file:
            for line in conf_lines:
                new_conf_file.write(line)

    def remove_option(self, option_name):
        """     Remove Option     ${option_name}

        Remove a single option from the DHCP configuration defined by the
        ${option_name} parameter.

        Example:
        | DHCP.Remove Option |  ${option_name}      |
        | DHCP.Remove Option |  AMINO.software_uri  |
        | DHCP.Remove Option |  ntp-servers         |
        """
        logger.debug('DHCP: remove_option UUT: {0} Option Name: {1}'\
            .format(self._unit_under_test, option_name))

        with open(self.include_path, 'r') as conf_file:
            conf_lines = conf_file.readlines()

        is_removed = False
        for index, line in enumerate(conf_lines):
            if option_name in line:
                is_removed = True
                del conf_lines[index]

        if not is_removed:
            logger.warn('DHCP: Remove Option: option not removed "{0}"'\
                .format(option_name))
        else:
            logger.debug('DHCP: Remove Option Option: successfully removed')

        with open(self.include_path, 'w') as new_conf_file:
            for line in conf_lines:
                new_conf_file.write(line)

    def reset_dhcp_server(self):
        """     Reset Dhcp Server

        Resets the DHCP server back to original configuration, removing all
        options and restarting the server so the new configuration takes
        effect

        Example:
        | DHCP.Reset Dhcp Server |
        """
        logger.debug('DHCP: resetting dhcp server')
        self.clear_all_dhcp_options()
        self.restart_dhcp_server()

    def clear_all_dhcp_options(self):
        """     Clear All Dhcp Options

        clears all options set by the DHCP automation library, this is not
        required to be run before removing the host and closing the library
        but is useful for running another test with a blank configuration file

        Example:
        | DHCP.Clear All Dhcp Options |
        """
        logger.debug('DHCP: Removing all options for UUT: {0}'
                     .format(self._unit_under_test))

        with open(self.include_path, 'r') as conf_file:
            conf_lines = conf_file.readlines()

        new_conf_lines = []

        for line in conf_lines:
            if ('option' in line) and ('vendor-option-space' not in line):
                logger.debug('DHCP: Removing option: {0}'.format(line.replace('\n', '')))
            else:
                new_conf_lines.append(line)

        with open(self.include_path, 'w') as new_conf_file:
            for line in new_conf_lines:
                new_conf_file.write(line)

    def restart_dhcp_server(self):
        """     Restart Dhcp Server

        send the restart DHCP server command set in the dhcp library definition file
        to apply the configuration changes made by the library. This will need to be
        called after any configuration changes for the settings to take effect, the UUT
        will also need to be rebooted.

        Example:
        | DHCP.Restart Dhcp Server |
        """
        logger.info('DHCP: Restarting DHCP server')
        self._check_dhcp_config()

        commandout = self.restart_command
        logger.debug('DHCP: Restarting dhcp server "{0}"'.format(commandout))

        alloutput = self.execute_command(commandout, return_rc=True)
        retcode = alloutput[1]
        logger.debug('DHCP: restart command return code: {0}'.format(retcode))

        if retcode != 0:
            raise FatalDhcpError('DHCP restart failed rc='.format(retcode))

    def restart_dhcp_and_reboot_uut(self, instance_name="UUT"):
        """     Restart Dhcp And Reboot Uut

        Restarts the DHCP server using DHCP.Restart Dhcp Server, then looks
        for an instance of the STB library with name 'UUT', and uses this
        instance to reboot the UUT.

        Default behavour would use the followiing as the STB library import
        statement where the instance name is 'UUT'
            Library ../../resources/devices/${uut}.py    WITH NAME    UUT

        As this is defined per test suite, if an alternative name for the
        library import is used e.g. STB1 then the default can be overridden
        with the "instance_name" optional parameter, see example usage.

        Example:
        | DHCP.Restart Dhcp And Reboot Uut |                      |
        | DHCP.Restart Dhcp And Reboot Uut | instance_name="STB1" |
        """
        try:
            self.restart_dhcp_server()

            logger.debug('DHCP: Rebooting UUT from DHCP library')
            unit_under_test = BuiltIn().get_library_instance(instance_name)
            unit_under_test.reboot_stb()
        except RuntimeError:
            logger.warn('DHCP: Failed to get UUT library instance for reboot')
            raise FatalDhcpError(fatal_message='restart dhcp and reboot error')

    def _set_obj_properties(self, infolist):
        """
        Sets the object properties for _unit_under_test, _ip_address and _mac_address

        Args:
            infolist (list of str) - [ uut, ip_addr, mac_addr ]
        Returns:
            Nothing
        """
        try:
            self._unit_under_test = infolist[0]
            self._ip_address = infolist[1]
            self._mac_address = infolist[2]
            self.include_path = '{0}{1}.cfg'.format(self.auto_path, self._unit_under_test)
        except IndexError:
            logger.warn('DHCP: Failed to set object properties, exiting')
            raise FatalDhcpError(
                fatal_message='DHCP: Failed to set object properties')

    def _check_dhcp_config(self):
        """
        _check_dhcp_config docstring
        """
        check_command = '/usr/sbin/dhcpd -t -cf {0}'.format(self.dhcpd_path)
        logger.debug('DHCP: Externally Validating dhcp config file: {0}'\
            .format(self.dhcpd_path))

        alloutput = self.execute_command(check_command, return_stderr=True, return_rc=True)

        if alloutput[2] != 0:
            logger.warn('DHCP: dhcp config file validation failed!')
            raise FatalDhcpError(fatal_message='Failed to validate dhcp config!')
        else:
            ret_lines = alloutput[1].split('\n')
            # Iterate over repsonse from dhcpd command output and look for potential warnings added
            #       in by the DHCP library and send the warning to the robot loggers info method
            for line in ret_lines:
                if 'WARNING' in line:
                    logger.info('DHCP: Non Fatal warning in validation:')
                    logger.info('\t{0}'.format(line))

    def _check4duplicates(self, stageInd, checkType, duplicateFile, regExpression):
        """ _check4duplicates

        This function is used by validate_dhcp_configuration to process the output from the Linux
        commands that produce files containing duplicate MAC/IP address information.

        Args:
        stageInd         - String containing DHCP validation stage indication.
        checkType        - String showing either 'MAC' or 'IP' addresses being processed.
        duplicateFile    - Path for file containing duplicate address information.
        regExpression    - Regular expression used to extract either MAC or IP details.

        Returns: True if duplicates found, otherwise False.
        """
        retVal = False

        # Check results file. An empty file means no duplicates detected.
        if os.stat(duplicateFile).st_size != 0:
            # Report duplicate information.
            with open(duplicateFile, 'r') as tempfile:
                reslines = tempfile.readlines()

            # From each line obtain the number of occurrences and the actual duplicate address.
            for resLine in reslines:
                m_obj = re.search(regExpression, resLine)
                if m_obj:
                    # Output details of duplicates found.
                    logger.warn("ERROR: DHCP.Validate Configuration (Stage " + stageInd + "): There are " + m_obj.group(1) + " occurrences of " + checkType + " address " + m_obj.group(2) + " in the DHCP configuration!")

            # Return false
            retVal = True
        return retVal

    def validate_dhcp_configuration(self):
        """ Validate the DHCP configuration

        This checks that no duplicate IP and/or MAC addresses are used in the DHCP configuration.
        The validation is performed in 2 stages. STAGE1 ensures there is no duplication in the
        configuration files produced by the Add Host" command.  STAGE2 will only be performed when
        STAGE1 is deemed free of duplicates and ensures there is no duplication between configuration
        files created by Add Host commands and the main dhcpd.conf file.

        Returns True if validation is successful, otherwise False.

        Example:
        | ${result}= | DHCP.Validate DHCP Configuration |
        """
        # Initialise path names for temporary files used.
        macFile = '/tmp/ROBOT_MAC_ADDRESSES.txt'
        ipFile  = '/tmp/ROBOT_IP_ADDRESSES.txt'
        dupFile = '/tmp/ROBOT_DUPLICATES.txt'

        # Initialise commands and regex used.
        macCmd1_1 = "grep 'hardware ethernet' " + self.auto_path + "stb_*.cfg | grep -v \"^\s*#\" | sed -e {s/^.*ethernet\s*//} | tr [:lower:] [:upper:]"
        macCmd2_1 = "grep 'hardware ethernet' " + self.dhcpd_path + " | grep -v \"^\s*#\" | sed -e {s/^.*ethernet\s*//} | tr [:lower:] [:upper:]"
        macCmd2   = "sort " + macFile + " | uniq -cd > " + dupFile

        ipCmd1_1 = "grep 'fixed-address' " + self.auto_path + "stb_*.cfg | grep -v \"^\s*#\" | sed -e {s/^.*fixed-address\s*//}"
        ipCmd2_1 = "grep 'fixed-address' " + self.dhcpd_path + " | grep -v \"^\s*#\" | sed -e {s/^.*fixed-address\s*//}"
        ipCmd2   = "sort " + ipFile + " | uniq -cd > " + dupFile

        macrExp = r"([0-9]+)\s*([0-9a-fA-F]{2}\:[0-9a-fA-F]{2}\:[0-9a-fA-F]{2}\:[0-9a-fA-F]{2}\:[0-9a-fA-F]{2}\:[0-9a-fA-F]{2})"

        iprExp = r"([0-9]+)\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)"

        # Initialise stage flags.
        stage1Fail = False
        stage2Fail = False

        # Stage 1: Check for duplicate IP addresses and/or MAC addresses in Robot DHCP configuration files.

        # Use glob to get all the config files in the directory. Must use full path (no ~ allowed).
        globArg = self.auto_path + 'stb_*.cfg'
        robotcfgfiles = glob.glob(globArg)

        # Check that there are Robot DHCP config files available to process.
        if len(robotcfgfiles) > 0:
            logger.debug("There is/are " + str(len(robotcfgfiles)) + " Robot DHCP configuration file(s) in the directory " + self.auto_path)

            # STAGE1: Now process the Robot DHCP configuration files
            # MAC address check.

            # Look for lines with 'hardware ethernet'
            # Ignore lines that are commented out.
            # Remove other text and leave only the MAC address
            # Convert any lower case MAC chars to upper.
            cmd =  macCmd1_1 + " > " + macFile
            logger.debug('Stage 1 command for MAC = %s' % cmd)
            os.system(cmd)

            # Sort the MAC addresses (sort MUST be done for uniq to work correctly).
            # Use the uniq options to isolate duplicates and their number of occurrences.
            os.system(macCmd2)

            # Check for duplicates.
            stageMACFail = self._check4duplicates("1", "MAC", dupFile, macrExp)

            # IP address check.
            cmd = ipCmd1_1 + " > " + ipFile
            logger.debug('Stage 1 command for IP = %s' % cmd)
            os.system(cmd)

            os.system(ipCmd2)

            # Check for duplicates.
            stageIPFail = self._check4duplicates("1", "IP", dupFile, iprExp)

            # Return false
            stage1Fail = stageMACFail or stageIPFail

        # Only perform STAGE2 if STAGE1 was clean.
        if not stage1Fail:
            # STAGE2: Now look for duplicates using the results of STAGE1 and the dhcpd.conf file.
            # MAC address check.

            cmd =  macCmd2_1 + " >> " + macFile
            logger.debug('Stage 2 command for MAC = %s' % cmd)
            os.system(cmd)

            os.system(macCmd2)

            # Check for duplicates.
            stageMACFail = self._check4duplicates("2", "MAC", dupFile, macrExp)

            # IP address check.
            cmd = ipCmd2_1 + " >> " + ipFile
            logger.debug('Stage 2 command for IP = %s' % cmd)
            os.system(cmd)

            os.system(ipCmd2)

            # Check for duplicates.
            stageIPFail = self._check4duplicates("2", "IP", dupFile, iprExp)

            # Return false
            stage2Fail = stageMACFail or stageIPFail

        # Cleanup
        cmd = "rm -f " + macFile + "; rm -f " + ipFile + "; rm -f " + dupFile
        logger.debug('Cleanup cmd = %s' % cmd)
        os.system(cmd)

        # Return False if either validation stage failed previously.
        if stage1Fail or stage2Fail:
            logger.info('DHCP.Validate DHCP Configuration FAILED!')
            return False

        # Validation successful!
        logger.info('DHCP.Validate DHCP Configuration SUCCESSFUL!')
        return True

    def set_restart_command(self, command):
        """
        Command used to restart the DHCP server

        Args:
            command(str) - full command to restart the DHCP server
        Returns:
            Nothing
        """
        self.restart_command = command

    def set_dhcpd_path(self, dhcpd_path):
        """
        Set the absolute path of the dhcpd.conf file

        Args:
            dhcpd_path (str) - absolute path to the dhcpd.conf file
        Returns:
            Nothing
        """
        self.dhcpd_path = dhcpd_path

    def set_auto_path(self, auto_path):
        """
        Set the path of the automated working directory, if it is requried to
        be different than /etc/dhcp/auto

        Args:
            auto_path (str) - absolute path to the dir to store stb_*.cfg files
        Returns:
            Nothing
        """
        self.auto_path = auto_path

    def _check_is_auto_included(self):
        """
        checks that robot-auto.cfg is included in the specified dhcpd.conf file
        on the DHCP server in use for testing.

        Args:
            None
        Returns:
            True  ( bool ) - robot-auto.cfg is included in dhcpd.conf
            False ( bool ) - robot-auto.cfg is missing from dhcpd.conf
        """
        is_included = False
        with open(self.dhcpd_path, 'r') as check_file:
            for line in check_file:
                strp_line = line.replace(' ', '')
                if 'robot-auto.cfg' in strp_line and strp_line[:1] != '#':
                    is_included = True

        return is_included

    def get_time_zone_list(self):
        """     Get a list of time zone from the keys of the TIME_ZONES

        See example usage for how to assing the list to a variable and how to
        iterated over the list.

        The keys are returned seperately so they can be used for testing setting
        the time zone using libconfig value NORFLASH.TIME_ZONE

        Examples:
        | @{TIME_ZONES}= | DHCP.Get Time Zone List  |         |               |
        | :FOR           | ${ZONE}                  | in      | @{TIME_ZONES} |
        | ...            | log                      | ${ZONE} |               |
        """
        ret = []
        for zone in TIME_ZONES.keys():
            ret.append(zone)

        logger.debug('DHCP: returning {0} time zones in list'.format(len(ret)))

        return ret

    def get_posix_for_time_zone(self, time_zone):
        """     Return the POSIX time string from the TIME_ZONES dict

        Example:
        | ${berlin_posix}=  | DHCP.Get Posix For Time Zone | Europe/Berlin |
        | ${london_posix}=  | DHCP.Get Posix For Time Zone | Europe/London |
        """
        ret = ''
        try:
            ret = TIME_ZONES[time_zone]
        except KeyError:
            logger.debug('DHCP: trying to get timezone that isnt specified')

        return ret

    def check_system_timezone(self, system_hour, time_zone):
        """     Check a time zone string against the system time hour

        Using the system hour reported by running 'date +"%H"', check the
        system time against UTC reported by the host running the test. The
        offset is returned from the pytz module, which is kept up to the
        most recent set of time zones.

        Examples show usage of hard coded values for the time zones and system
        time, however these values should be fetched from the UUT using the STB
        library, and from DHCP.Get Time Zone List

        Examples:
        | DHCP.Check System Timezone  | 23      | Etc/GMT+11  |
        | DHCP.Check System Timezone  | 01      | Etc/GMT-11  |
        """
        try:
            stb_zone = pytz.timezone(time_zone)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warn('DHCP: UnknownTimeZoneError {0}'.format(time_zone))
            return False

        utc_time = datetime.utcnow().hour

        # This get the time zone offset in seconds, for comparison
        tz_offset = stb_zone.utcoffset(datetime.utcnow()).seconds

        # convert seconds to hours, hours can not be returned here
        tz_offset = (tz_offset/60)/60

        should_be = utc_time + tz_offset

        # correct time if the hour falls over the end of a 24 hour clock
        if should_be >= 24:
            should_be = should_be - 24

        logger.debug('DHCP: UUT time hour="{0}" should be="{1}"'
                     .format(system_hour, should_be))

        if int(should_be) == int(system_hour):
            return True
        else:
            logger.warn('Time Zone does not match: {0}'.format(time_zone))
            return False

def get_option_type(option_name, option_value):
    """
    checks an option_name is supported by the library and if the type is
    an int or and IP address, then validate the option_value using the type
    returned from the DHCP_OPTIONS dictionary

    Args:
        option_name  (str) - DHCP option name  e.g "AMINO.software_uri"
        option_value (str) - DHCP option value e.g "http://host/mc2.mcfs"
    Returns:
        "ip"      - option type is ip address
        "text"    - option is type text
        "int"     - option is type int
        "ip_list" - option is single or list of IPs
        2         - option_name is not recognised
        3         - option_value is not valid
    """
    try:
        option_type = DHCP_OPTIONS[option_name]
    except KeyError:
        logger.warn('DHCP: get_option_type invalid option_name {0}'
                    .format(option_name))
        return 2

    if option_type == 'ip':
        if check_is_ip_addr(option_value):
            pass
        else:
            return 3

    elif option_type == 'int':
        if not option_value.isdigit():
            return 3

    elif option_type == 'ip_list':
        if not ',' in option_value:
            if not check_is_ip_addr(option_value):
                return 3
        else:
            ip_addrs = option_value.split(',')
            for ip_addr in ip_addrs:
                if not check_is_ip_addr(ip_addr):
                    return 3
    return option_type

def check_is_ip_addr(ip_addr):
    """     check_is_ip_addr

    Checks the validity of an IPv4 address

    Args:
        ip_addr - IP address to be validated
    Returns:
        True  - IP address is valid
        False - IP address is not valid
    """
    ip_addr = ip_addr.replace(' ', '')
    logger.debug('DHCP: Validating IP: "{0}"'.format(ip_addr))

    parts = ip_addr.split(".")
    try:
        if len(parts) != 4:
            return False
        for item in parts:
            if not 0 <= int(item) <= 255:
                return False
        return True
    except ValueError:
        logger.debug('DHCP: non numeric value passed to check_is_ip_addr')
        return False

class FatalDhcpError(ExecutionFailed):
    """
    This exception definition is used to raise a fatal DHCP library error
    on a condition where the configuration is in a state where it cannot
    be recovered
    """
    def __init__(self, fatal_message=None):
        if fatal_message:
            logger.warn(fatal_message)
        else:
            fatal_message = "FatalDhcpError() raised"

        ExecutionFailed.__init__(self, fatal_message, exit=True)

DHCP_OPTIONS = {
    'AMINO.address'             : 'ip',
    'AMINO.port'                : 'int',
    'AMINO.product'             : 'text',
    'AMINO.option'              : 'text',
    'AMINO.version'             : 'text',
    'AMINO.homepage'            : 'text',
    'AMINO.STBrc-mcast-address' : 'ip',
    'AMINO.STBrc-mcast-port'    : 'int',
    'AMINO.STBrc-unicast-port'  : 'int',
    'AMINO.timezone'            : 'text',
    'AMINO.mw_args'             : 'text',
    'AMINO.mirimon_args'        : 'text',
    'AMINO.software_di'         : 'int',
    'AMINO.software_uri'        : 'text',
    'AMINO.igmp_max_ver'        : 'int',
    'AMINO.extra_options'       : 'text',
    'AMINO.middleware'          : 'ip',
    'AMINO.middleware2'         : 'ip',
    'ntp-servers'               : 'ip_list',
    'domain-name-servers'       : 'ip_list'
}

TIME_ZONES = {
    'America/Anchorage':             'AKST9AKDT8,M3.2.0/2,M11.1.0/2',
    'America/Argentina/Buenos_Aires':'ART3',
    'America/Chicago':               'CST6CDT5,M3.2.0/2,M11.1.0/2',
    'America/Denver':                'MST7MDT6,M3.2.0/2,M11.1.0/2',
    'America/Guatemala':             'CST6',
    'America/Los_Angeles':           'PST8PDT7,M3.2.0/2,M11.1.0/2',
    'America/New_York':              'EST5EDT4,M3.2.0/2,M11.1.0/2',
    'America/Phoenix':               'MST7',
    'America/Sao_Paulo':             'BRT3BRST2,M10.3.0/0,M2.3.0/0',
    'Asia/Jakarta':                  'WIT-7',
    'Asia/Singapore':                'SGT-8',
    'Asia/Ulaanbaatar':              'ULAT-8',
    'Atlantic/Bermuda':              'AST4ADT3,M3.2.0/2,M11.1.0/2',
    'Australia/Brisbane':            'EST-10',
    'Australia/Hobart':              'EST-10EST-11,M10.1.0/2,M4.1.0/3',
    'Australia/Melbourne':           'EST-10EST-11,M10.1.0/2,M4.1.0/3',
    'Australia/Perth':               'WST-8',
    'Etc/GMT+1':                     'Etc/GMT+1',
    'Etc/GMT+10':                    'Etc/GMT+10',
    'Etc/GMT+11':                    'Etc/GMT+11',
    'Etc/GMT+12':                    'Etc/GMT+12',
    'Etc/GMT+2':                     'Etc/GMT+2',
    'Etc/GMT+3':                     'Etc/GMT+3',
    'Etc/GMT+4':                     'Etc/GMT+4',
    'Etc/GMT+5':                     'Etc/GMT+5',
    'Etc/GMT+6':                     'Etc/GMT+6',
    'Etc/GMT+7':                     'Etc/GMT+7',
    'Etc/GMT+8':                     'Etc/GMT+8',
    'Etc/GMT+9':                     'Etc/GMT+9',
    'Etc/GMT-0':                     'Etc/GMT-0',
    'Etc/GMT-1':                     'Etc/GMT-1',
    'Etc/GMT-10':                    'Etc/GMT-10',
    'Etc/GMT-11':                    'Etc/GMT-11',
    'Etc/GMT-12':                    'Etc/GMT-12',
    'Etc/GMT-13':                    'Etc/GMT-13',
    'Etc/GMT-14':                    'Etc/GMT-14',
    'Etc/GMT-2':                     'Etc/GMT-2',
    'Etc/GMT-3':                     'Etc/GMT-3',
    'Etc/GMT-4':                     'Etc/GMT-4',
    'Etc/GMT-5':                     'Etc/GMT-5',
    'Etc/GMT-6':                     'Etc/GMT-6',
    'Etc/GMT-7':                     'Etc/GMT-7',
    'Etc/GMT-8':                     'Etc/GMT-8',
    'Etc/GMT-9':                     'Etc/GMT-9',
    'Europe/Amsterdam':              'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Europe/Athens':                 'EET-2EEST-3,M3.5.0/03:00,M10.5.0/04:00',
    'Europe/Berlin':                 'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Europe/Bratislava':             'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Europe/Brussels':               'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Europe/Budapest':               'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Europe/Copenhagen':             'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Europe/Dublin':                 'GMT0IST-1,M3.5.0/01:00,M10.5.0/02:00',
    'Europe/Helsinki':               'EET-2EEST-3,M3.5.0/03:00,M10.5.0/04:00',
    'Europe/Kiev':                   'EET-2EEST-3,M3.5.0/03:00,M10.5.0/04:00',
    'Europe/Lisbon':                 'WET0WEST-1,M3.5.0/01:00,M10.5.0/02:00',
    'Europe/London':                 'GMT0BST-1,M3.5.0/01:00,M10.5.0/02:00',
    'Europe/Madrid':                 'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Europe/Moscow':                 'MSK-3',
    'Europe/Oslo':                   'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Europe/Paris':                  'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Europe/Prague':                 'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Europe/Rome':                   'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Europe/Stockholm':              'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Europe/Zurich':                 'CET-1CEST-2,M3.5.0/02:00,M10.5.0/03:00',
    'Pacific/Auckland':              'NZST-12NZDT-13,M9.5.0/2,M4.1.0/3',
    'Pacific/Honolulu':              'HST+10'
}
