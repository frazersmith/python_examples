# Robot libraries
import robot.libraries.Telnet as Telnet
from robot.api import logger
from robot.version import get_version
from robot import utils
from robot.libraries.BuiltIn import BuiltIn
import robot.libraries.OperatingSystem as OperatingSystem

# Standard libraries
import time
from collections import namedtuple
import threading
import os
import math
import xml.etree.ElementTree as ET

# Amino Libraries
import Debug
import Fakekey
from InfraRedBlaster import InfraRedBlaster

__version__ = "0.1 beta"

DEBUG = True

class STB(object):

    """ Amino Aminet STB Library by Frazer Smith.

    This library is designed for use with Robot Framework.

    NOTE: This library is not intended for use with Enable stack.  Refer to the ESTB library for Enable stack.

    It provides access to common Aminet STB methods including:-
       Ability to connect via Telnet to any defined interface
       Ability to send commands using that telnet connection
       Ability to receive output and return codes for commands sent via Telnet
       Ability to capture debug from a serial connection
       Ability to send fakekey commands, or run fakekey scripts
       Ability to log STB statistics (CPU, Memory, Wifi)

    It can be used as a library directly in a suite (as long as the basic setup are carried out
    for interfaces etc) or, more commonly, can be used as a base class for devices set up as
    their own library.

    Example of device library (in resources/devices).  In this case stb_50c1fc.py (library name must match internal class name):-

    | import os, sys
    | lib_path = os.path.abspath('../../libraries')
    | sys.path.append(lib_path)
    |
    | from libraries.STB import STB
    |
    | class stb_50c1fc(STB):
    |
    |    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    |
    |    def __init__(self):
    |
    |        # Dont change these
    |        STB.__init__(self)
    |        self._shortname = self.__class__.__name__
    |
    |        # Start box specifics here
    |        self.create_interface("eth0","10.172.249.141","00:02:02:50:c1:fc")
    |        self.create_interface("wlan0","10.172.249.224","a8:54:b2:ab:e9:9b")
    |        self.set_powerip_port("10.172.249.14:0")
    |        self._serialnumber = "J54113H0000005"
    |        self._debugport = "/dev/ttyUSB0"


    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, family='Ax0xx', prompt='[root@AMINET]#', prompt_regex=False, login_prompt='AMINET login: ',
                 password_prompt='Password: ', telnet_encoding='ISO-8859-15',
                 telnet_terminal_type='vt102', telnet_user='root', telnet_password='root2root',
                 debugport=None, fakekey_port=40000, fakekey_keymapfile=None):

        """  No arguments are required to initialise the STB object as they will all default to common settings or 'None'

        The essential requirements of a STB (interfaces, serialnumber etc) must all be created after instantiation, either
        at runtime or by creating a device which inherits this baseclass first.
        """

        self._IFACE = namedtuple("IFACE","name ip mac")

        # STB properties
        self._shortname = "stb_unknown"
        self._serialnumber = None
        self._family = family
        self._interfaces = []
        self._active_interface = None
        self._os = OperatingSystem.OperatingSystem()
        self._stateflags = {}

        # Telnet properties
        self._login_prompt = login_prompt
        self._password_prompt = password_prompt
        self._prompt = prompt
        self._prompt_regex = prompt_regex
        self._telnet_encoding = telnet_encoding
        self._telnet_terminal_type = telnet_terminal_type
        self._telnet_user = telnet_user
        self._telnet_password = telnet_password
        self._telnet_conn = None
        self._telnet_timeout = "3 seconds"
        self._newline = "\n"
        self._keep_telnet_open = False
        self._reboot = True

        # Stats collection properties
        self._stats_conn = None
        self._keep_stats_open = False
        self._stats_memory = False
        self._stats_cpu = False
        self._stats_wifi = False
        self._stats_qoemon = False
        self._stats_thread = None
        self._stats_interval = "10 seconds"
        self._stats_abort = False
        self._stats_collecting = False

        # Debug properties
        self._debug = None
        self._debugport = debugport
        self._fatals = ['Kernel panic -']
        self._fatal = False

        # Fakekey properties
        self._fakekey_port = fakekey_port
        self._fakekey_keymapfile = fakekey_keymapfile
        self._fakekey = None

        # InfraRedBlaster properties
        self._ir_port = None
        self._ir = None

        # Power IP port settings
        self._powerip_port = None
        self._powerip_type = "netbooter"

    def read_disk_space_levels(self):
        """

        Author: S. Housley
        Date:   21FEB14

        Returns a list of "total", "available" and "low" disk space levels as read from streamerctl

        Examples:-
        | ${disk_levels}= | Read Disk Space Levels |
        """


        ip = self.get_interface_attribute()

        self._open_connection(ip)
        ## Check we have a PVR device which is ready?
        if int(self._send_command('diskman info | grep "Ready" > /dev/null ; echo $?')) > 0:
            raise STBError("Fill PVR Failure:  No 'Ready' disk found")

        self._set_telnet_timeout("2 minutes")

        self._send_command("cd /PVR")
        FS = '"= "'
        total_disk = int(self._send_command("streamerctl diskinfo | awk '/total_size/ { FS = %s; print $2;}'" % FS))
        avail_disk = int(self._send_command("streamerctl diskinfo | awk '/available_size/ { FS = %s; print $2;}'" % FS))
        low_disk   = int(self._send_command("streamerctl diskinfo | awk '/low_space_size/ { FS = %s; print $2;}'" % FS))

        diskLevels = [total_disk,avail_disk,low_disk]
        return diskLevels

    def get_low_disk_space_level(self, target_percent):
        """

        Author: S. Housley
        Date:   29JAN14

        Returns a LOW_DISK_SPACE_LEVEL value in Kbytes for a given percentage figure.

        Examples:-
        | Get Low Disk Space Level | 30%        |
        """

        ip = self.get_interface_attribute()

        self._open_connection(ip)
        ## Check we have a PVR device which is ready?
        if int(self._send_command('diskman info | grep "Ready" > /dev/null ; echo $?')) > 0:
            raise STBError("Fill PVR Failure:  No 'Ready' disk found")

        self._set_telnet_timeout("2 minutes")

        # Convert percentage to float
        target_percent = target_percent.rstrip("%")
        pcnt_target = float(target_percent)

        self._send_command("cd /PVR")
        FS = '"= "'
        total_disk = float(self._send_command("streamerctl diskinfo | awk '/total_size/ { FS = %s; print $2;}'" % FS))
        target_avail_disk = total_disk - (total_disk * (float(pcnt_target)/100))

        low_disk_size = int(target_avail_disk)
        return low_disk_size

    def fill_pvr(self, target_percent):
        """

        Author: S. Housley
        Date:   09JAN14

        Updated to handle adding and removing filler files by Frazer Smith, 2014-01-10

        Takes a human readable percentage and fills the HDD to match it.

        If the HDD already has filler files and a percetage is provided which requires
        their removal, they will be deleted to match the percentage.

        If 100% is required the last filler file will fill the disk.

        The % supplied can be a floating precision number

        Will return the number of filler files (tempfillerxxxxx) that exist at the end.

        Examples:-
        | Fill PVR      | 30%       |                                |
        | Fill PVR      | 75%       |                                |
        | Fill PVR      | 85%       | low_disk_space_warn=True       |
        | ${filecount}= | Fill PVR  | 99.9%                          |
        """

        # Convert percentage to float
        target_percent = target_percent.rstrip("%")
        pcnt_target = float(target_percent)

        ip = self.get_interface_attribute()

        self._open_connection(ip)
        ## Check we have a PVR device which is ready?
        if int(self._send_command('diskman info | grep "Ready" > /dev/null ; echo $?')) > 0:
            raise STBError("Fill PVR Failure:  No 'Ready' disk found")

        self._set_telnet_timeout("2 minutes")

        # Run this in /PVR
        self._send_command("cd /PVR")
        FS = '"= "'

        # Get initial readings

        total_disk = float(self._send_command("streamerctl diskinfo | awk '/total_size/ { FS = %s; print $2;}'" % FS))
        avail_disk = float(self._send_command("streamerctl diskinfo | awk '/available_size/ { FS = %s; print $2;}'" % FS))
        try:
            file_count = int((self._send_command("cd /PVR;ls tempfiller* | tail -1").lstrip("tempfiller")))
        except ValueError:
            file_count = 0

        # Work out how many filler files are required
        target_avail_disk = total_disk - (total_disk * (float(pcnt_target)/100))
        filler_files_needed = int(math.ceil((avail_disk - target_avail_disk)/(1024**2)))

        # Sanity check that this many filler will not fill disk, unless we wanted that
        if ((filler_files_needed * (1024**2) + (total_disk - avail_disk)) > total_disk) and pcnt_target < 100:
            # We don't want 100 but this will be over 100
            filler_files_needed = filler_files_needed - 1

        # If we need to remove files, are there enough
        if filler_files_needed < 0 and abs(filler_files_needed) > file_count:
            raise STBError("Not enough filler files exist to trim down to that percentage.")

        if filler_files_needed > 0:
            logger.info("Need to add '" + str(filler_files_needed) + "' 1GB filler files")
        else:
            logger.info("Need to remove '" + str(abs(filler_files_needed)) + "' 1GB filler files")

        file_target = file_count + filler_files_needed
        while file_target != file_count:
            if filler_files_needed > 0:
                # Adding filler files
                file_count = file_count + 1
                logger.info("Adding 1GB file.. tempfiller" + str(file_count).zfill(5))
                self._send_command("cd /PVR; dd if=/dev/zero bs=1M count=1024 of=tempfiller"+str(file_count).zfill(5))
            else:
                # Removing filler files
                logger.info("Removing file tempfiller" + str(file_count).zfill(5))
                self._send_command("cd /PVR; rm tempfiller"+str(file_count).zfill(5))
                file_count = file_count -1

        return file_count

    def add_debug_listener(self, listener):
        """  Add a text string to 'listen' for on the debug interface

        If you wish to act upon a specific listener asyncronously (i.e. not pausing execution)
        add it to this list and then interogate with `Check Debug Listeners` keyword later.

        Examples:
        | Add debug listener    | AC_BOOT   |

        """
        if listener not in self._debug._listeners:
            self._debug.add_listener(listener)

    def remove_debug_listener(self, listener):
        """  Remove a text string to 'listen' for on the debug interface

        Opposite action to adding with `Add debug listener`.

        NOTE: The listener must exist in the listeners list or an error with be thrown

        Examples:
        | Remove debug listener | AC_BOOT   |

        """
        if listener in self._debug._listeners:
            self._debug._listeners.remove(listener)
        else:
            raise STBError("ERROR: Trying to remove a listener that is not in the listeners list")


    def check_debug_listeners(self, reset=False):
        """  Check if any listener has been heard

        A list object is returned with information of which listeners were heard and at what time

        Optionally you can reset this list of 'heard' listeners to avoid getting the same information later

        Examples:
        | ${heards}= | Check debug listeners |               |
        | ${heards}= | Check debug listeners | reset=True    |

        """

        ret =  self._debug.check_listeners()

        if reset == True or reset == 'True':
            self._debug._listeners_heard = []

        return ret

    def wait_for_debug_listener(self, listener, timeout, donotError=False):
        """  Pause execution until a specific text string is read over debug

        Any previous debug listener list will be replaced while this string is waited for.

        An integer representing how many seconds it took to see the string will be returned.

        If the timeout expires an error will be thrown halting test execution unless the donotError
        flag is set to True. The donotError flag is useful if we want to test a scenario where we do not expect
        to see a string in the debug log e.g. disabling watchdog on an Ax0xx means you will not see
        WARM_BOOT and to test this we might want to wait for a few minutes to ensure this is the case.

        Examples:
        | ${timetaken}=  | Wait for debug listener   | WARM_BOOT     | 2 minutes     |                 |
        | ${timetaken}=  | Wait for debug listener   | WARM_BOOT     | 2 minutes     | donotError=True |
        | ${timetaken}=  | Wait for debug listener   | CHANGEPAGE    | 30 seconds    |                 |

        """

        templisteners = self._debug._listeners
        templistenersheard = self._debug._listeners_heard
        self._debug._listeners = ['%s' % listener]
        self._debug._listeners_heard = []
        tout = utils.timestr_to_secs(timeout)

        seccount = 0
        found = False
        while seccount <= tout:
            time.sleep(1)
            if len(self._debug._listeners_heard) > 0:
                found = True
                break
            seccount = seccount + 1

        self._debug._listeners = templisteners
        self._debug._listeners_heard = templistenersheard

        if not found:
            if donotError:
                # We did NOT expect to see the listener string!
                return seccount
            else:
                raise STBError("Listener '%s' not heard within %s" % (listener, timeout))
        else:
            logger.debug("Listener '%s' heard in %ss" % (listener, seccount))
            return seccount


    def get_qoemon_value(self, value="VPTS", videowindow="0"):
        """  Return a value obtained from qoemon

        Each of the keyword values is assigned a specific command within STB library

        Optionally you can set the video window to gather the stats from (defaults to 0)

        Available values are:-
        - VPTS      - Video PTS count
        - APTS      - Audio PTS count
        - VLastPTS  - Timestamp of last seen Video PTS
        - ALastPTS  - Timestamp of last seen Audio PTS

        Examples:
        | ${vpts}=      | Get qoemon Value  | videowindow=1 |
        | ${a_time}=    | Get qoemon Value  | ALastPTS      |
        """

        qoemon_values = {
                        "VLastPTS":"qoemon -sV -w%s | awk {'print $2'} | tail -1" % videowindow,
                        "ALastPTS":"qoemon -sA -w%s | awk {'print $2'} | tail -1" % videowindow,
                        "VPTS":"qoemon -sP -w%s | awk {'print $2'} | tail -1" % videowindow,
                        "APTS":"qoemon -sP -w%s | awk {'print $4'} | tail -1" % videowindow
                        }

        qoemon_command = qoemon_values.get(value)

        if qoemon_command == None:
            raise STBError("qoemon value '" + value + "' not found")

        ret = self.send_command_and_return_output(qoemon_command)

        # Some may need post processing
        if value == 'VPTS' or value =='APTS' or value == 'VLastPTS' or value == 'ALastPTS':
            try:
                ret = int(ret)
            except:
                ret = -1
        return ret

    def send_command_over_debug(self, command):

        """  Sends a command over the serial debug connection

        This does not return any value, it sends the command blindly so it does not interrupt debug capture.

        A `Capture Debug` keyword must have been called earlier (in suitesetup normally) to be able to send
        commands over the serial interface.


        Examples:
        | Send command over debug   | rm -rf /PVR/0000000001    |

        """
        self._debug.send_command(str(command))

    def send_commands_over_debug(self, *commands):
        """  Sends multiple commands over the serial debug connection

        This does not return any value, it sends the command blindly so it does not interrupt debug capture.

        A `Capture Debug` keyword must have been called earlier (in suitesetup normally) to be able to send
        commands over the serial interface.


        Examples:
        | Send commands over debug  | rm -rf /PVR/0000000001    | mv /tmp /newtemp  |

        """

        first = True
        for command in commands:
            if first:
                self._debug.send_command(str(command))
                first = False
            else:
                self._debug.send_command(str(command), suppresslogin=True)


    def set_wifi_parameters(self, *args, **kwargs):
        """ Set the wifi parameters

        This gives access, through keywords, to all elements of the radio interface

        Supported keywords:-
            region          String representing the region code
            country         String representing the country code
            ssid            String representing the SSID to associate with
            security_mode   String representing the security_mode
            passphrase      String representing the passphrase
            reboot          ${True} if you would rather reboot the STB to apply wireless settings (NOTE: You need to add the reboot step yourself)


        After setting the parameters the netman config will update and the wifi driver restart.  The a nominal 10 second wait will occur to allow WiFi to stabilise

        Examples:
        | Set Wifi Parameters   | country=GB    | region=GR-E11 | security_mode=WPA2-PSK-AES    |
        | Set Wifi Parameters   | passphrase='' | country=US    | ssid=TestSSID01               |
        """
        commands = []


        if 'region' in kwargs:
            commands.append("WIRELESS_REGION %s" % kwargs['region'])

        if 'country' in kwargs:

            commands.append("WIRELESS_COUNTRY %s" % kwargs['country'])

        if 'ssid' in kwargs:

            commands.append("WIRELESS_SSID %s" % kwargs['ssid'])

        if 'security_mode' in kwargs:

            commands.append("WIRELESS_SECURITY_MODE %s" % kwargs['security_mode'])

        if 'passphrase' in kwargs:

            commands.append("WIRELESS_PASSPHRASE %s" % kwargs['passphrase'])

        if 'reboot' in kwargs:

            reboot = True

        else:

            reboot = False


        if len(commands) > 0:
            for command in commands:
                self.send_command_over_debug("libconfig-set NORFLASH.%s" % command)

            if not reboot:


                ifacename = self.get_interface_attribute('name')

                self.send_command_over_debug("ifconfig %s down; wait; netman update_config; wait; /etc/init.d/rc.wireless_drivers restart; wait; /etc/init.d/rc.network restart; wait; ifconfig %s up" % (ifacename, ifacename))

                time.sleep(10)
            else:
                #Reboot STB?

                pass

            time.sleep(10)


    def send_command_over_debug_and_return_output(self, command, timeout="3 seconds"):
        """  Sends a command over the serial debug connection and waits for a response

        This will interrupt the debug handler (by stopping the syslogd process on the stb) while it
        waits to complete the command.  Command completion is assumed when the command prompt is seen.

        Debug will be re-enabled upon completion

        A `Capture Debug` keyword must have been called earlier (in suitesetup normally) to be able to send
        commands over the serial interface.
        mystb.set_ir_blaster("127.0.0.1",1,"resources/remotes/RCU_AMINO_WILLOW.txt")

        A timeout (defaults to 3 seconds) will be applied when waiting for the prompt, ensure this is long enough
        when sending commands which take a while to complete.


        Examples:
        | ${ret}=   | Send command over debug and return output | cat /etc/version  |                       |
        | ${ret}=   | Send command over debug and return output | ls /mnt/nv        | timeout=20 seconds    |


        """
        return self._debug.send_command_and_return_output(str(command), self._prompt, timeout)

    def get_debug_filepath(self):
        """  Returns the filepath of the debug capture

        Useful if you need to post process this file

        Example:
        | ${debugfile}= | Get debug filepath    |
        """

        return self._debug._outputpath


    def send_ir(self, code):
        """  Send IR code to STB

        (depends upon `Set IR Blaster`)

        Examples:
        | Send IR   | MENU  |
        """

        self._ir.send_ir(self._ir_port, code)

    def send_ir_codes(self, *codes, **kwargs):
        self._ir.send_ir_codes(self._ir_port, *codes, **kwargs)


    def set_ir_blaster(self, ir_host, ir_port, ir_remote):
        """  Sets the IR Net Box to blast IR at STB

        Requires ir_host (IP address), ir_port (1 to 16) & ir_remote (filename of remote codes)


        Examples:
        | Set ir blaster    | 10.172.241.147    | 1 | resources/remotes/RCU_AMINO_WILLOW.txt    |

        """
        self._ir_port = ir_port

        self._ir = InfraRedBlaster(ir_host)
        self._ir.load_remote(ir_remote)


    def set_powerip_port(self, powerip_port, powerip_type="netbooter"):
        """  Sets the power IP port to control power of STB

        Format of 'powerip_port' is [IP of Power Device]:[Port index]

        The type of powerip can be set, but currently only netbooter is supported

        Examples:
        | Set power ip port | 10.172.242.10:0   |

        """
        self._powerip_port = powerip_port
        self._powerip_type = powerip_type

    def ping_stb_until_alive(self, interface=-1, timeout="2 minutes", pinginterval="5 seconds", dieonfail=True):
        """  Repeatedly pings STB on any defined interface until it responds or 'timeout' expires.

        If the STB responds before 'timeout' expires the keyword will return how long it took to respond (in seconds)

        If 'timeout' expires, behaviour is defined by 'dieonfail'.  True raises an error, false returns -1.

        Examples:
        | Ping STB until alive  | interface=${wifi}     | pinginterval=10 seconds   |
        | ${ret}=               | Ping STB until alive  | timeout=3 minutes         |
        | ${ret}=               | Ping STB until alive  | dieonfail=${False}        |

        """

        ip = self._get_iface_ip(interface)

        starttime = time.time()
        endtime = starttime + utils.timestr_to_secs(timeout)
        waitfor = utils.timestr_to_secs(pinginterval)

        while time.time() < endtime:
            try:
                self._ping(ip)
                return str(int(time.time() - starttime))
            except:
                time.sleep(waitfor)
        if dieonfail:
            raise STBError("Unable to reach STB with ping after %s" % timeout)
        else:
            return str(-1)




    def ping_stb(self, interface=-1, dieonfail=True):
        """  Pings the STB on any defined interface, returns True is successful

        You can choose to 'dieonfail' or continue execution, returning False instead

        Examples:
        | Ping STB  |                   |                  |
        | ${ret}=   | Ping STB          | dieonfail=False  |
        | Ping STB  | interface=${wifi} |                  |

        """
        ip = self._get_iface_ip(interface)
        try:
            self._ping(ip)
            return True
        except:
            if dieonfail:
                ROBOT_EXIT_ON_FAILURE = True
                raise PingResponseError
            else:
                logger.warn("Unable to ping STB on " + ip)
                return False

    def _ping(self, target):
        retcode = self._os.run_and_return_rc("ping -c 1 " + target)
        if retcode != 0:
            raise PingResponseError
        else:
            return 0

    def reboot_stb(self, pingtimeout="2 minutes"):

        """  Reboots the STB using telnet over the active interface.  It then uses `Ping STB Until Alive`,
        passing the 'pingtimeout' value as the timeout.

        If the telnet port was being held open it will be reopened after the wait period.
        If stb stats were being collected they will be halted and restarted after the wait period.
        A debug capture will stay open.

        This keyword will return the number of whole seconds it took for the STB to become responsive to ping.

        Examples:
        | ${time}=      | Reboot STB            |
        | Reboot STB    | pingtimeout=3 minutes |

        """

        #Handle old method
        try:
            if pingtimeout.startswith("waitfor"):
                pingtimeout = pingtimeout.split("=")[1]
        except:
            pass

        restart_telnet = False
        restart_stats = False


        if (self._keep_telnet_open == True) and (self._telnet_conn != None):
            restart_telnet = True


        if (self._keep_stats_open == True) and (self._stats_conn != None):
            restart_stats = True
            # Close down stats gracefully
            try:
                self._keep_stats_open = False
            except:
                pass
            try:
                self.stop_stb_statistics()
            except:
                pass

        # Reboot box

        logger.info("Rebooting STB now....")

        try:
            #self.send_commands("reboot")
            self.send_command_and_return_output("reboot")
        except Exception as e:
            #logger.warn("Reboot error: %s" % e.__str__())
            logger.info("Failed to open telnet, trying over debug...")
            self.send_commands_over_debug("reboot")

        # Close down telnet gracefully
        try:
            self._keep_telnet_open = False
        except:
            pass
        try:
            self._close_telnet()
        except:
            pass

        logger.info("Waiting for STB to restart.....")
        time.sleep(20)
        timetaken = self.ping_stb_until_alive(timeout=pingtimeout)
        logger.info("STB has responded, waiting for 10 seconds before commencing")
        time.sleep(10)



        # Now restart all the stuff that was stopped
        if restart_telnet:
            logger.info("Reopening telnet connection")
            self.login_and_keep_telnet_open()

        if restart_stats:
            logger.info("Restarting stats capture")
            self.capture_stb_statistics(mem=self._stats_memory, cpu=self._stats_cpu, wifi=self._stats_wifi, qoemon=self._stats_qoemon, interval=self._stats_interval)

        self._stateflags = {}

        return str(int(timetaken) + 20)

    def get_stateflag(self, stateflag):
        """ Get Stateflag - Return stateflag information for the current object

        See `Set Stateflag` for stateflag use information.

        If a stateflag is not set at all it will return ${False}

        Example:-
        | ${ret}=   | Get Stateflag | startedproc   |

        """
        try:
            ret = self._stateflags[stateflag]
        except KeyError:
            ret = False

        return ret

    def set_stateflag(self, stateflag, state=True):
        """ Set Stateflag - Allows stateful information be stored

        These flags are all removed when a `Reboot STB` is called

        Examples:-
        | Set Stateflag | startedproc   |               |
        | Set Stateflag | flag2         | ${flagvalue}  |

        """

        self._stateflags[stateflag] = state


    def power_cycle_stb(self, waitfor="1 minute", downtime="1 second"):

        """  Power cycles the STB and waits for a set time (default = 1 minute) before continuing.

        When the wait period expires the STB will be pinged.  A failure to respond will halt the test execution.

        If the telnet port was being held open it will be closed and reopened after the wait period.
        If stb stats were being collected they will be halted and restarted after the wait period.
        A debug capture will stay open.

        Defining a downtime (defaults to 1 second) will change the time between OFF and ON

        Examples:
        | Power cycle STB   |                       |
        | Power cycle STB   | waitfor=2 minutes     |
        | Power cycle STB   | downtime=5 seconds    |

        """

        if self._powerip_port == None:
            logger.warn("A power cycle was attempted when no powerip settings were defined!")
            return

        restart_telnet = False
        restart_stats = False

        powerip = self._powerip_port.split(":")[0]
        powerport = self._powerip_port.split(":")[1]

        try:
            self._ping(powerip)
        except:
            logger.warn("No response from powerip device on ip '" + powerip + "'.  Unable to power cycle STB")
            return

        if (self._keep_telnet_open == True) and (self._telnet_conn != None):
            restart_telnet = True
            # Close down telnet gracefully
            try:
                self._keep_telnet_open = False
            except:
                pass
            try:
                self._close_telnet()
            except:
                pass

        if (self._keep_stats_open == True) and (self._stats_conn != None):
            restart_stats = True
            # Close down stats gracefully
            try:
                self._keep_stats_open = False
            except:
                pass
            try:
                self.stop_stb_statistics()
            except:
                pass

        # Power cycle box

        if self._powerip_type == "netbooter":

            logger.info("Power cycling STB now....")
            self._power_ip_netbooter(powerip, powerport, 0)
            time.sleep(utils.timestr_to_secs(downtime))
            self._power_ip_netbooter(powerip, powerport, 1)
            logger.info("Waiting for STB to restart (" + waitfor + ")")
            sleeptime = utils.timestr_to_secs(waitfor)
            time.sleep(sleeptime)
            self.ping_stb_until_alive(timeout=sleeptime)

        # Now restart all the stuff that was stopped
        if restart_telnet:
            logger.info("Reopening telnet connection")
            self.login_and_keep_telnet_open()

        if restart_stats:
            logger.info("Restarting stats capture")
            self.capture_stb_statistics(mem=self._stats_memory, cpu=self._stats_cpu, wifi=self._stats_wifi, qoemon=self._stats_qoemon, interval=self._stats_interval)

        self._stateflags = {}


    def _power_ip_netbooter_old(self, powerip, powerport, state, max_attempts=3):
        counter = 0
        while self._os.run_and_return_rc('curl --user admin:admin http://' + powerip + '/status.xml 2>&1 | grep "<rly' + powerport + '>0" > /dev/null 2>&1') != int(state):
            counter = counter + 1
            if counter > max_attempts:
                raise STBError("Unable to change power ip")
            time.sleep(0.2)
            self._os.run_and_return_rc('curl --user admin:admin http://' + powerip + '/cmd.cgi?rly=' + powerport + ' >/dev/null 2>&1')


    def _power_ip_netbooter(self, powerip, powerport, state, max_attempts=3):
        if state == self._power_ip_netbooter_read(powerip, powerport, max_attempts):
            logger.info("Power IP already in state %s.  No action" % state)
        else:
            self._os.run_and_return_rc('curl --user admin:admin http://' + powerip + '/cmd.cgi?rly=' + powerport + ' >/dev/null 2>&1')
            counter = 0
            while int(state) != int(self._power_ip_netbooter_read(powerip, powerport, max_attempts)):
                counter = counter + 1
                if counter > max_attempts:
                    raise STBError("Could not set rly to state %s on powerip %s" % (state, powerip))
                else:
                    logger.info("Set powerip state failed... retrying")
                    time.sleep(0.5)
                    self._os.run_and_return_rc('curl --user admin:admin http://' + powerip + '/cmd.cgi?rly=' + powerport + ' >/dev/null 2>&1')


    def _power_ip_netbooter_read(self, powerip, powerport, max_attempts=3):
        counter = 0
        # Check for a response from the powerip unit
        logger.info("Pinging powerip")
        while self._os.run_and_return_rc('ping %s -c 1' % powerip) != 0:
            counter = counter + 1
            if counter > max_attempts:
                raise STBError("Unable to ping powerip on %s" % powerip)
            else:
                logger.info("Ping powerip failed... retrying")
                time.sleep(0.5)

        counter = 0


        try:
            root = ET.fromstring(self._os.run('curl -s --user admin:admin http://%s/status.xml' % powerip))
        except Exception as inst:
            logger.warn('Power Ip Error: %s' % (inst))
            raise STBError("Unable to read status of powerip on %s" % powerip)

        return root.find('rly%s' % powerport).text

    # Fakekey methods (public)
    def send_fakekey(self, key, pause=None, repeatcount=1):

        """  Sends a key code, as defined in the active fakekey keymapping.

        If a keycode is sent as a keydown only, this state will persist until the
        corresponding keyup is sent later.  This is how you achieve key holds (for
        operations such as CTRL+A).

        Manitory argument:
        - keycode   - The key code as mapped in the active mapping file

        Optional arguments:
        - pause     - Provides a pause in thread execution immediately after sending
        - repeatcount   - Send the same keycode (and pause, if appropriate) multiple times

        Examples:
        | Send fakekey  | CIR_BTN_CH_UP |                   |               |
        | Send fakekey  | ${mykey}      | pause=1 second    |               |
        | Send fakekey  | ${mykey}      | pause=0.5 second  | repeatcount=3 |

        """

        try:
            self._open_fakekey()
            self._fakekey.send_fakekey(key, pause, repeatcount)
        except LookupError as l:
            logger.warn(l.__str__())
            raise l
        except Exception as e:
            if e.__str__() != "Execution terminated by signal":
                logger.warn("Unable to connect to fakekey on STB.  Check it's running and self._fakekey_port is set correctly.")
            raise e

    def run_fakekey_script(self, filename, repeats=-1, timeout=None):

        """  Runs a standard fakekey script.

        Compatable with original format fakekey scripts containing either keycodes,
        'wait', 'exit' or comments.  As with the old fakekey method the script will
        repeat unless an 'exit' command is encoutered or the 'repeats' counter is set.

        Unlike the old method you can also define a 'timeout' which can be used to timebox
        a soak test, e.g. run a script for 72 hours.

        Mandatory arguments:
        - filename  - The fakekeyscript.  Can be an absolute path, or relative to the
                          aminorobot directory.

        Optional arguments:
        - repeats   - Provides a pause in thread execution immediately after sending
        - repeatcount   - Send the same keycode (and pause, if appropriate) multiple times

        Examples:
        | Run fakekey script    | resources/fakekeyscripts/standby.fakekey      |                |
        | Run fakekey script    | ${myscript}                                   | repeats=3      |
        | Run fakekey script    | resources/fakekeyscripts/chanchange.fakekey   | timeout=5 days |
        """

        try:
            self._open_fakekey()
            self._fakekey.run_fakekey_script(filename, repeats, timeout)
        except LookupError as l:
            logger.warn(l.__str__())
            raise l
        except Exception as e:
            if e.__str__() != "Execution terminated by signal":
                logger.warn("Unable to connect to fakekey on STB.  Check it's running and self._fakekey_port is set correctly.")
            raise e

    # Fakekey methods (private)
    def _open_fakekey(self):
        if self._fakekey_keymapfile != None:
            self._fakekey = Fakekey.Fakekey(mappingfile=self._fakekey_keymapfile, ipaddress=self.get_interface_attribute(), port=self._fakekey_port)
        else:
            self._fakekey = Fakekey.Fakekey(ipaddress=self.get_interface_attribute(), port=self._fakekey_port)


    # STATS methods (public)
    def stop_stb_statistics(self):

        """  Stops gathering STB statistics

        Example:
        | Stop stb statistics   |

        """

        if self._stats_thread != None:
            logger.info("Stopping stb statistics..")
            self._keep_stats_open = False
            self._stats_abort = True
            self._stats_thread.join()
            self._stats_thread = None
            self._close_stats()

    def capture_stb_statistics(self, mem=True, cpu=True, wifi=False, qoemon=False, interval="10 seconds", keepopen=True):

        """  Starts gathering STB statistics

        By default this will start gathering CPU IDLE and FREE MEMORY.
        Optionally wifi signal stats can also be collected.

        Log files are stored in the output directory with the naming convention:-
        ${SUITENAME}_${STB_SHORTNAME}_{mem|cpu|wifi}.log
        (This makes the scope of a logfile suite based)

        Optional arguments:
        - mem={True|False}  - Capture 'free memory' stats (defaults to True)
        - cpu={True|False}  - Capture 'cpu idle' stats (defaults to True)
        - wifi={True|False} - Capture 'wifi signal' stats (defaults to False)
        - qoemon={False|xxxx}   - Capture 'qoemon' stats where xxxx is any of the available qoemon counters*
        - interval      - Set the time between captures (default 10 seconds)
        - keepopen={True|False} - Allows the telnet connection to stay open rather than log in each time, saving at least 3 seconds a capture. (defaults to True)

        * qoemon can monitor one or more from:-
        - T - Time
        - S - Skips
        - A - Audio Decoder
        - AF    - Audio Decoder Frames
        - V - Video Decoder
        - VF    - Video Decoder Frames
        - X - Demux
        - XT    - Demux Times
        - D - Discontinuities
        - B - Buffer usage
        - P       - Video PTS and Audio PTS


        Examples:
        | Capture STB Statistics    |                |             | # Start capturing CPU and MEM at 10 second intervals                              |
        | Capture STB Statistics    | mem=False      | wifi=True   | # Start capturing CPU and WIFI at 10 second intervals                             |
        | Capture STB Statistics    | cpu=False      | interval=30 | # Start capturing MEM only at 30 second intervals                                 |
        | Capture STB Statistics    | keepopen=False |             | # Start capturing CPU and MEM at 10 second intervals, log in each time            |
        | Capture STB Statistics    | qoemon=SD      | cpu=False   | # Start capturing MEM and qoemon skips and discontinuities at 10 second intervals |

        """

        if keepopen:
            ip = self.get_interface_attribute()
            self._open_stats_connection(ip)
            self._keep_stats_open = True

        logger.info("Starting stats collection")
        if self._stats_thread != None:
            logger.warn("A call to collect stb stats was issued while stb stats where already being collected.  Ignoring.")
            return
        self._stats_memory = mem
        self._stats_cpu = cpu
        self._stats_wifi = wifi
        self._stats_qoemon = qoemon
        self._stats_interval = interval
        self._stats_abort = False
        self._stats_thread = threading.Thread(target=self._capture_stats_thread)
        self._stats_thread.start()
        self._stats_collecting = True

    # STATS methods (private)
    def _capture_stats_thread(self):

        countsec = 0

        ip = self.get_interface_attribute() #Use active for now

        outdir = BuiltIn().replace_variables('${OUTPUTDIR}')
        suitename = BuiltIn().replace_variables('${SUITENAME}')
        outputpath = os.path.join(outdir, suitename + '_' + self._shortname).replace(' ','_')


        while not self._stats_abort:

            self._open_stats_connection(ip)
            if self._stats_cpu:
                #Collect CPU stats
                logfile = outputpath + "_cpu.log"
                if not os.path.isfile(logfile):
                    with open(logfile, 'w') as outputfile:
                        outputfile.write("Timestamp,CPU_IDLE(%)\n")
                timestamp = self._send_stats_command("date +'%Y%m%d%H%M%S'")
                output = self._send_stats_command("top -n 1 | head -n 2 | tail -n 1")

                with open(logfile, 'a') as outputfile:
                    outputfile.write(timestamp + "," + output.split()[7].rstrip("%") + "\n")

            if self._stats_memory:
                #Collect Mem stats
                logfile = outputpath + "_mem.log"
                if not os.path.isfile(logfile):
                    with open(logfile, 'w') as outputfile:
                        outputfile.write("Timestamp,FreeMemory(B)\n")

                timestamp = self._send_stats_command("date +'%Y%m%d%H%M%S' && `cat /proc/meminfo > /tmp/mem`")
                output = self._send_stats_command("echo `expr $(cat /tmp/mem | grep 'Buffers' | awk {'print $2'}) + $(cat /tmp/mem | grep 'MemFree' | awk {'print $2'}) + $(cat /tmp/mem | grep 'Cached:' | grep -v 'SwapCached:' | awk {'print $2'})`")
                self._send_stats_command("rm /tmp/mem")
                with open(logfile, 'a') as outputfile:
                    outputfile.write(timestamp + "," + output + "\n")


            if self._stats_wifi:
                #Collect Wifi stats
                logfile = outputpath + "_wifi.log"
                if not os.path.isfile(logfile):
                    with open(logfile, 'w') as outputfile:
                        outputfile.write("Timestamp,Quality(%),SignalStrength(dBm),Noisefloor(dBm)\n")

                timestamp = self._send_stats_command("date +'%Y%m%d%H%M%S'")
                qual = self._send_stats_command("cat /proc/net/wireless | grep wlan0 | awk '{print $3}'").rstrip('.')
                strength = self._send_stats_command("cat /proc/net/wireless | grep wlan0 | awk '{print $4}'").rstrip('.')
                noise = self._send_stats_command("cat /proc/net/wireless | grep wlan0 | awk '{print $5}'")
                with open(logfile, 'a') as outputfile:
                    outputfile.write(timestamp + "," + qual + "," + strength + "," + noise + "\n")

            if self._stats_qoemon != False:
                logfile = outputpath + "_qoemon.log"
                qoeoutput = self._send_stats_command("qoemon -s " + self._stats_qoemon + " -c 1")
                timestamp = self._send_stats_command("date +'%Y%m%d%H%M%S'")
                with open(logfile, 'a') as outputfile:
                    outputfile.write(timestamp + "\n")
                    outputfile.write(qoeoutput + "\n")

            self._close_stats()

            targetsec = utils.timestr_to_secs(self._stats_interval)
            countsec = 0
            while (targetsec > countsec):
                if self._stats_abort:
                    return
                time.sleep(1)
                countsec = countsec + 1

    # Debug methods (public)
    def debug_marker(self, text):
        """ Mark a debug log with a message.

        Most useful for marking the start of a test or a particular step to aid with fault finding.

        Example:
        | Debug marker  | Starting Testcase ${TESTNAME}     |
        | Debug marker  | Starting a particular step now    |

        """

        if self._debug != None:
            self._debug.debug_marker(text)

    def capture_debug(self, debugport="default", suffix=None, dieonfail=True, compressed=False):
        """  Capture debug from a serial port

        Opens a serial connection to the debug on port ${debugport} (defaults to the
        debugport passed as an argument when creating the STB) and keeps it open
        for the life of the test suite.  Debug will be saved to the same output dir as
        other log files for the run and will contain the suitename, a defined suffix (or
        the STB shortname if no suffix is provided) and the text "_debug.log"

        Be default, if capturing debug fails for any reason (i.e. no debug port configured,
        serial port locked, unable to open the serial port specified etc) the test execution will
        halt.  This can be overridden with 'dieonfail'.

        If you are running a long test it would be advisable to compress the log as it is being
        written.  You can do this with 'compressed=${True}'

        Examples:
        | Capture debug |                           |
        | Capture debug | debugport=/dev/ttyUSB0    |
        | Capture debug | suffix=UUT                |
        | Capture debug | dieonfail=${False}        |
        | Capture debug | compressed=${True}        |


        NOTE:  The current user MUST have access rights to serial ports!  To acheive this
        add the user to the 'dialout' group using:-

        sudo usermod -a -G dialout USERNAME

        NOTE: It is good practice to mark the debug log when starting a new test case, using the
        `Debug marker` keyword.
        """

        if suffix == None:
            if self._shortname != None:
                suffix = self._shortname

        comp = ""
        if compressed:
            comp = "(compressed) "

        if debugport != "default":
            self._debugport = debugport

        if self._debugport == None:
            logger.warn("Unable to capture debug: No serial port configured!")
            if dieonfail:
                raise STBError("Debug capture failed")
            else:
                return
        try:
            self._debug = Debug.Debug(appendsuffix=suffix)
            self._debug.open_connection(commport=self._debugport, compressed=compressed)
            logger.info("Serial debug capture %sstarted on '%s'" % (comp, self._debugport))
        except Debug.DebugError as d:
            logger.warn("Unable to capture debug on port '" + self._debugport + "'. "  + d.__str__())
            if dieonfail:
                raise STBError("Debug capture failed")
        except Exception as e:
            logger.warn("Unable to capture debug on port '" + self._debugport + "'.  Check it exists and you have permission to use it." + e.__str__())
            if dieonfail:
                raise STBError("Debug capture failed")

    def get_property(self, property):
        # type: (object) -> object
        """  Get a STB property at runtime

        Note: To get interface attributes you must use `Get Interface Attribute`

        Examples:
        | ${serial}=    | Get property  | serialnumber  |
        | ${family}=    | Get property  | family        |

        """
        property = '_' + property.lower()
        return getattr(self, property)

    def set_property(self, property, value):
        """  Set a STB property at runtime

        Note: You can not set individual interface attributes during runtime, only
        add a new interface with `Create interface`

        Available properties (and their defaults) are:-

        === STB properties ===
        - shortname         = 'stb_unknown'
        - serialnumber      = None
        - family        = 'Ax0xx'
        - active_interface  = None          # Note becomes 0 when first is added

        === Telnet properties ===
        - login_prompt      = 'AMINET login: '
        - password_prompt   = 'Password: '
        - prompt        = '[root@AMINET]#'
        - telnet_encoding   = 'ISO-8859-15'
        - telnet_terminal_type  = 'vt102'
        - telnet_user       = 'root'
        - telnet_password   = 'root2root'
        - telnet_timeout    = '3 seconds'
        - newline       = "\n"
        - keep_telnet_open  = False
        - reboot        = True          # Defines if STB will reboot after libconfig-set

        === Stats collection properties ===
        - stats_memory      = False
        - stats_cpu         = False
        - stats_wifi        = False
        - stats_qoemon      = False
        - stats_interval    = "10 seconds"

        === Debug properties ===
        - debugport = debugport

        === Fakekey properties ===
        - fakekey_port      = 40000
        - fakekey_keymapfile    = None

        === Power IP port settings ===
        - powerip_port      = None
        - powerip_type      = "netbooter"

        Examples:
        | Set property  | serialnumber  | J12121991829812   |
        | Set property  | family        | ${family}         |

        """
        property = '_' + property
        setattr(self, property, value)



    def __del__(self):
        self.close_all()

    def close_all_but_debug(self):
        """ Closes all open connectons except debug
        Best used when upgrading or rebooting

        Example:
        | Close all but debug   |
        """
        try:
            self._fakekey.close()
        except:
            pass
        try:
            self._keep_telnet_open = False
        except:
            pass
        try:
            self._keep_stats_open = False
        except:
            pass
        try:
            self._close_telnet()
        except:
            pass
        try:
            self.stop_stb_statistics()
        except:
            pass



    def close_all(self):
        """ Closes all open connectons including debug, telnet, stats and fakekey

        Example:
        | Close all |
        """
        try:
            self._debug.close()
        except:
            pass
        self.close_all_but_debug()


    def _checkfatal(self):
        if self._fatal == True:
            raise KernelPanicError('Kernel panic detected!')



    def create_interface(self, name, ip, mac):
        """  Create interface ${name} ${ip} ${mac})

        This will add a network interface to the STB which can then be used for testing.

        The first interface created will become the 'active' interface by default.
        Optionally the index of the interface is returned and can be used later
            to set it as active using `Set active interface`

        A STB can have any number of interfaces.

        Examples:
        | Create interface      | eth0              | 10.172.249.10 | 68:e2:02:24:11:ab |                   |
        | ${wifi_interface}=    | Create interface  | wlan0         | 10.172.249.224    | 00:02:02:24:ef:d7 |

        """

        self._interfaces.append(self._IFACE(name, ip, mac))
        if len(self._interfaces) == 1:
            self._active_interface = self._interfaces[0]
        return (len(self._interfaces)-1)

    def set_active_interface(self, number):
        """  Set active interface ${interface_index}

        Allows the active interface (for telnet connections etc) to switch between multiple defined interfaces.

        Examples:
        | Set active interface  | 1                 |
        | Set active interface  | ${wifi_interface} |

        """

        self._active_interface = self._interfaces[int(number)]

    def get_interface_attribute(self, attributename = 'ip', interface = -1):
        """  Get interface attribute ${attributename} [${interface_index}]

        Returns an attribute from a given interface.

        Examples:
        | ${ret}=   | Get interface attribute   | ip    |   | #Returns ip of active interface   |
        | ${ret}=   | Get interface attribute   | name  | 1 | #Returns name of interface[1]     |
        """
        interface = int(interface)

        if interface == -1:
            thisinterface = self._active_interface
        else:
            thisinterface = self._interfaces[interface]
        return getattr(thisinterface, attributename)

    def login_and_keep_telnet_open(self, interface=-1):
        """  Allows the telnet connection to stay open for the duration of the test suite.

        If there are many telnet commands to make it will save at least 3 seconds per command.

        Examples:
        | Login and keep telnet open    |               |
        | Login and keep telnet open    | ${eth_iface}  |

        """
        ip = self._get_iface_ip(interface)
        self._open_connection(ip)
        self._keep_telnet_open = True

    def set_telnet_timeout(self, timeout):
        self._telnet_timeout = timeout


    def _open_connection(self, ip):
        if self._keep_telnet_open == False:
            try:
                self._telnet_conn = Telnet.Telnet(newline=self._newline)
                self._telnet_conn.open_connection(ip,encoding=self._telnet_encoding,encoding_errors="strict", terminal_emulation=True, terminal_type=self._telnet_terminal_type, window_size='400x100')
                if self._login_prompt is not None:
                    self._telnet_conn.login(self._telnet_user,self._telnet_password,login_prompt=self._login_prompt,password_prompt=self._password_prompt,login_timeout="2 seconds")
                else:
                    # Need to consume first prompt
                    self._telnet_conn.read()
                self._telnet_conn.set_prompt(self._prompt, self._prompt_regex)
                time.sleep(2)
            except Exception as inst:
                raise Exception("Unable to open Telnet connection! - " + inst.__str__())

    def _open_stats_connection(self, ip):
        if self._keep_stats_open == False:
            try:
                self._stats_conn = Telnet.Telnet(newline=self._newline)
                self._stats_conn.open_connection(ip,encoding=self._telnet_encoding,encoding_errors="strict", terminal_emulation=True, terminal_type=self._telnet_terminal_type, window_size='400x100')
                self._stats_conn.login(self._telnet_user,self._telnet_password,login_prompt=self._login_prompt,password_prompt=self._password_prompt,login_timeout="2 seconds")
                self._stats_conn.set_prompt(self._prompt)
                time.sleep(2)
            except Exception as inst:
                raise Exception("Unable to open Telnet connection for stats! - " + inst.__str__())

    def get_wifi_stats(self, telnet_interface = -1, stats_interface = -1):
        """   Get wifi stats    [${telnet_interface}=active_interface]    [${stats_interface}=active_interface]

        Returns the signal quality, signal strength and noise floor, comma separated.

        NOTE:
        This is executed in the main test thread so will halt test execution until it is finished.
        If you would rather collect stats while a test is running see `Collect STB Statistics`

        Examples:
        | ${stats}= | Get wifi stats | 0    | 1 | # Return stats for interface index 1 by sending telnet commands over interface 0  |
        | ${stats}= | Get wifi stats |      |   | # Return stats for, and by send commands over, active interface (defaults to 0)   |

        """

        t_ip = self._get_iface_ip(telnet_interface)

        self._open_connection(t_ip)
        qual = self._send_command("cat /proc/net/wireless | grep wlan0 | awk '{print $3}'").rstrip('.') + " %"
        strength = self._send_command("cat /proc/net/wireless | grep wlan0 | awk '{print $4}'").rstrip('.') + " dBm"
        noise = self._send_command("cat /proc/net/wireless | grep wlan0 | awk '{print $5}'") + " dBm"

        self._close_telnet()
        return qual + "," + strength + "," + noise


    def _get_iface_ip(self, interface_index):
        if interface_index == -1:
            return self.get_interface_attribute()
        else:
            return self.get_interface_attribute('ip',interface_index)



    def send_command_and_return_output(self, command, interface=-1):
        """   Send telnet command and return output

        Sends a single command over Telnet and returns the output received until the next prompt

        Examples:
        | ${ret}=   | Send command and return output    | ls /tmp           |                   | # This sends the command to the active interface                          |
        | ${ret}=   | Send command and return output    | cat /etc/hosts    | ${wifi_interface} | # Sends command to interface index saved in ${wifi_interface} variable    |

        """
        ip = self._get_iface_ip(interface)

        _DEBUG("IP = %s" % ip)


        self._open_connection(ip)
	try:
            output = self._send_command(command)
            _DEBUG("output = %s" % output)
            self._close_telnet()
        except Exception as e:
            logger.warn("Exception2 = '%s'" % e)
        
        return output

    def _close_telnet(self):
        if self._keep_telnet_open == False:
            self._telnet_conn.close_all_connections()

    def _close_stats(self):
        if self._keep_stats_open == False:
            self._stats_conn.close_all_connections()
            #self._stats_conn = None

    def send_commands(self, *commands):
        """   Sends a list of commands to telnet on the active interface

        returns an array of return codes

        Examples:
        | Send commands | ls /mnt/nv    | cp log.temp / | rm log.temp       |
        | @{rcodes}=    | Send commands | cd /root      | mv log.txt /home  |
        """
        ip = self.get_interface_attribute() #Use active
        self._open_connection(ip)
        #old = self._set_telnet_timeout("11 minutes")
        ret = []
        for command in commands:
            self._send_command(command)
            thisret = self._send_command("echo $?")
            ret.append(thisret)
        self._close_telnet()
        return ret

    def record_pvr_asset_and_check_level(self, url, rectime, level_event='Low'):
        """   Records a PVR asset for given url and checks for a disk space level event

        returns True if disk space level detected otherwise False


        Examples:
        | ${warnseen}= | record pvr asset | igmp://239.255.250.22:2002 | 600 |                    |
        | ${warnseen}= | record pvr asset | igmp://239.255.250.22:2002 | 600 | level_event='Low'  |
        | ${fullseen}= | record pvr asset | igmp://239.255.250.22:2002 | 900 | level_event='Full' |
        """

        level_event = level_event.rstrip()
        grepStr = 'PVR_EVENT_LOW_DISK_SPACE'
        if level_event == 'Full':
            grepStr = 'PVR_EVENT_NO_DISK_SPACE'

        logger.info("Record debug>> LEVEL=" + level_event + " GREP=" + grepStr)

        ip = self.get_interface_attribute() #Use active
        self._open_connection(ip)

        # Keep telnet session open for "rectime + 60"
        opentime = int(rectime) + 60
        timestr = "" + str(opentime) + " seconds"
        old = self._set_telnet_timeout(timestr)

        # Tried piping output of streamerctl to tee command but this command is not available!
        cmdstr1 = "rm -f temp*.txt"
        cmdstr2 = "streamerctl record " + url + " test " + rectime + " > temp1.txt"
        cmdstr3 = "cat temp1.txt"
        cmdstr4 = "grep '" + grepStr + "' temp1.txt > temp2.txt"
        cmdstr5 = "test -s temp2.txt"
        commands = [cmdstr1, cmdstr2, cmdstr3, cmdstr4, cmdstr5]

        ret = []
        for command in commands:
            self._send_command(command)
            thisret = self._send_command("echo $?")
            ret.append(thisret)

        self._close_telnet()

        # The values in the ret[] array are strings!
        # Check that the temp.txt file is non-zero bytes long.
        if int(ret[4]) == 0:
            # Found!
            return True
        else:
            return False

    def send_command_and_return_output_and_rc(self, command, interface=-1):
        """   Send command and return output and rc

        Sends a single command over Telnet and returns the output received until the next prompt, and the return code

        Examples:
        | ${ret}    | ${rc}=    | Send command and return output and rc | ls /tmp           |                   | #This sends the command to the active interface                       |
        | ${ret}    | ${rc}=    | Send command and return output and rc | cat /etc/hosts    | ${wifi_interface} | #Sends command to interface index saved in ${wifi_interface} variable |
        """
        ip = self._get_iface_ip(interface)

        self._open_connection(ip)
        output = self._send_command(command)
        rc = self._send_command("echo $?")
        self._close_telnet()
        return output, rc

    def get_browser_pid(self):
        """   Gets the Browser PID

        returns the Browser PID if /var/run/opera.pid exists otherwise 0


        Examples:
        | ${bpid}= | get browser pid |
        """

        # Check the browser pid exists.
        output,retval = self.send_command_and_return_output_and_rc("test -e /var/run/opera.pid")
        logger.debug("DEBUG>>retval=" + retval)
        rc = int(retval)

        # Set browser pid to default value.
        bpid = "0"

        # If return code says pid file exists then get the pid.
        if rc == 0:
            # Browser PID file exists as the browser has been daemonised so get the value.
            cmdstr = "cat /var/run/opera.pid | awk '{FS = " + '" "' + "; print $2;}'"
            logger.debug("DEBUG>>cmdstr=" + cmdstr)
            bpid = self.send_command_and_return_output(cmdstr)

        return bpid


    def get_snapshot(self, interface=-1, saveaslog=False):
        """ Uses the shell script /mnt/nv/snapshot.sh to produce a report on the STB

        NOTE: This requires a telnet connection to the STB

        Examples:
        | ${snapshot}=  | Get snapshot  |           | # Gets the STB snapshot using the active interface    |
        | ${snapshot}=  | Get snapshot  | 2         | # Gets the STB snapshot using interface 2     |
        | ${snapshot}=  | Get snapshot  | saveaslog=True    | # Gets the STB snapshot and saves it as a log*    |
        * the log will be saved in the output directory using the following format:-
            ${SUITENAME}_[${TESTNAME}_]${STB_SHORTNAME}_snapshot.log  (the ${TESTNAME} will be used if the call occured during a testcase.  It will not be used if a call was made during a suite setup)

        """

        ip = self._get_iface_ip(interface)
        self._open_connection(ip)

        old = self._set_telnet_timeout("30 seconds")
        ret = self._send_command("/mnt/nv/snapshot.sh")
        self._set_telnet_timeout(old)
        self._close_telnet()

        if saveaslog:
            outdir = BuiltIn().replace_variables('${OUTPUTDIR}')
            suitename = BuiltIn().replace_variables('${SUITENAME}') + "_"
            try:
                testname = BuiltIn().replace_variables('${TESTNAME}') + "_"
            except:
                testname = ""
            outputpath = os.path.join(outdir, suitename.replace(' ','_') + testname.replace(' ','_') + self._shortname + "_snapshot.log").replace(' ','_')
            with open(outputpath,'a') as ofile:
                ofile.write(ret + "\n")
        return ret

    def reboot_after_libconfig_set(self, value):
        """   Reboot after libconfig set    True|False

        Tell the STB object if it needs to reboot after applying libconfig set commands using `Send libconfig set commands`
        (defaults to True)

        NOTE: Libconfig settings don't come into effect until after a reboot so be careful that you really want to disable this.

        Example:
        | Reboot after libconfig set    | False | # Allows the test to control the behaviour |
        """

        self._reboot = value

    def send_libconfig_set_commands(self, *commands):

        """    Send libconfig set commands  ${command1}    [${command2}].....

        Sends a list of commands to libconfig-set, setting and value are seperated by a single space

        The keyword will check if the change has had any effect (parse response to libconfig-set command to see
        what it was 'currently' set to).  If no changes were required the STB will not reboot.

        If changes were required, by default the STB will reboot. This behaviour can be changed using
        the `Reboot after libconfig set` keyword


        Example:
        | Send libconfig set commands   | NORFLASH.TVSYSTEM NTSC-M  | SETTINGS.OUTPUT_RESOLUTION HDAUTO |

        """

        self._open_connection(self.get_interface_attribute())
        settings_have_changed = False
        for command in commands:
            output = self._send_command("libconfig-set " + command)
            if self._check_setting_has_changed(output) == True:
                settings_have_changed = True
        if self._reboot == True and settings_have_changed:
            self.reboot_stb()
        elif self._reboot == True and not settings_have_changed:
            logger.info("NOTE: No need to reboot STB since no changes to settings have been required")
        self._close_telnet()


    def _check_setting_has_changed(self, output):
        lines = output.split("\n")
        current_value = 'current'
        new_value = 'new'
        for line in lines:
            if "Setting '" in line:
                # This is the setting line
                new_value = line.split("=")[len(line.split("="))-1]
            elif " currently " in line:
                current_value = line.split()[len(line.split())-1]
        if current_value == new_value:
            return False
        else:
            return True


    def send_libconfig_get_command(self, command):
        """    Send libconfig get command    ${command}

        Sends a single command to return a libconfig-get value

        Example:-
        | ${value}= | Send libconfig get command | NORFLASH.TVSYSTEM    |

        """
        self._open_connection(self.get_interface_attribute())
        output = self._send_command("libconfig-get " + command)
        self._close_telnet()
        return output

    # Added by Steve Housley 16/01/2014.
    # Implements libconfig-dump command available in 3.3.0 Live and Ax4x Release.
    def send_libconfig_dump_command(self, group=""):
        """    Send libconfig dump command    ${group}

        Sends a libconfig-dump with an optional "group" (defaults to "all groups") to return a list of configuration settings

        Example:-
        | ${config}=    | Send libconfig dump command |                 |
        | ${config}=    | Send libconfig dump command | NORFLASH        |
        | ${config}=    | Send libconfig dump command | SYSTEM          |
        | ${config}=    | Send libconfig dump command | SETTINGS        |
        | ${config}=    | Send libconfig dump command | USERSETTINGS    |

        """
        self._open_connection(self.get_interface_attribute())
        tempfile = "/tmp/stbconfig.txt"
        output = self._send_command("libconfig-dump " + tempfile + " " + group + "; cat " + tempfile + "; rm " + tempfile)
        self._close_telnet()
        return output

    def get_dhcp_init_args(self):
        """ This function returns a list of attributes of the STB object which are used in initialising
        the DHCP server library, it returns a 3 element list which consists of the following data:
            [uut, IP_ADDRESS, MAC_ADDRESS]
        e.g:
            ['stb_4a7099', '10.172.249.103', '00:02:02:4A:70:99']

        Example:-
        | ${stb_info}=  | STB.Get Dhcp Init Args |
        | DHCP.Add Host | ${stb_info}            |
        """
        ret = []
        ret.append(self._shortname)
        ret.append(self.get_interface_attribute('ip'))
        ret.append(self.get_interface_attribute('mac'))
        return ret

    def _set_telnet_timeout(self, timeout):
        old = self._telnet_conn._timeout
        self._telnet_conn._timeout = timeout
        self._telnet_timeout = timeout
        return old


    def _send_command(self, command):
        self._telnet_conn.set_timeout(self._telnet_timeout)
        ret = self._telnet_conn.execute_command(command).rstrip(self._prompt)
        ret = ret.rstrip(self._newline)
        return ret

    def _send_stats_command(self, command):
        ret = self._stats_conn.execute_command(command).rstrip(self._prompt)
        ret = ret.rstrip(self._newline)
        return ret

    def find_IGMP_stream (self, hexValue, streamCount, interface):
        """

        Author: S. Housley
        Date:   xxAUG15

        Find IGMP stream in output from cat /proc/net/igmp and if found returns True otherwise False.

        Needs modifying and testing with wifi!

        Examples:-
        | ${ret}= | Find IGMP Stream |
        """

        logger.info("DEBUG>> hexValue=" + hexValue + " streamCount=" + str(streamCount) + " interface=" + interface)
        found = False
        timeout = "3 seconds"
        command = "cat /proc/net/igmp"
        lines1 = self._debug.send_command_and_return_output(str(command), self._prompt, timeout)
        logger.info("DEBUG>> lines1=" + lines1)
        lines2 = lines1.split("\n")
        searchActive = False
        searchCount = 0
        for line in lines2:
            if interface in line:
                searchActive = True
                logger.info("DEBUG>> SEARCH ACTIVE!")
                continue
            if searchActive:
                if hexValue in line:
                    found = True
                    logger.info("DEBUG>> FOUND!")
                    break
                else:
                    searchCount = searchCount + 1
                    if searchCount == streamCount:
                        logger.warn("DEBUG>> NOT FOUND in " + str(streamCount) + " IGMP streams for " + interface)
                        break
        return found



class KernelPanicError(RuntimeError):
    ROBOT_EXIT_ON_FAILURE = True
    pass

class PingResponseError(RuntimeError):
    pass

class STBError(RuntimeError):
    pass

def _DEBUG(msg):
    if DEBUG:
        print "DEBUG: %s" % str(msg)
