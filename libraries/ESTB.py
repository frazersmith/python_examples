# Robot libraries
from robot.api import logger
from robot.version import get_version
from robot import utils
import robot.libraries.OperatingSystem as OperatingSystem
import SSHLibrary
import robot.libraries.BuiltIn as BuiltIn
# Standard libraries
from paramiko.ssh_exception import NoValidConnectionsError
import time
from collections import namedtuple
import math
import xml.etree.ElementTree as ET
import inspect
import re
import os
import subprocess
import serial
import struct
import random
from pprint import pprint as pp
import types



# AminoEnable Libraries
import Debug
import HNRKey
from InfraRedBlaster import InfraRedBlaster
import StatCollection
from libraries.hnr import HnrError

# Import variables
from resources.variables.PowerDevices import *


from ESTBRESTAPI import ESTBRESTAPI
from ESTBWiFi import ESTBWiFi
from ESTBPlayer import ESTBPlayer
from ESTBSystem import ESTBSystem
from ESTBRecorder import ESTBRecorder
from ESTBBrowse import ESTBBrowse
from ESTBTuner import ESTBTuner
from ESTBTimeControl import ESTBTimeControl





__version__ = "0.1 beta"

DEBUG = False

ANSI_ESCAPE = re.compile(r'\x1b[^m]*m')

class ESTB(object):
    """ Amino Enable STB Library by Frazer Smith.

    This library is designed for use with Robot Framework.

    NOTE: This library replaces STB (Aminet) for use with the Enable stack

    It provides access to common STB methods including:-
       Ability to connect via Telnet to any defined interface
       Ability to send commands using that telnet connection
       Ability to receive output and return codes for commands sent via Telnet
       Ability to capture debug from a serial connection
       Ability to send fakekey commands, or run fakekey scripts
       Ability to log STB statistics (CPU, Memory, Wifi)

    It can be used as a library directly in a suite (as long as the basic setup are carried out
    for interfaces etc) or, more commonly, can be used as a base class for devices set up as
    their own library.

    Example of device library (in resources/devices).  In this case estb_956548.py
    (library name must match internal class name):-

    | import os, sys
    | lib_path = os.path.abspath('../../libraries')
    | sys.path.append(lib_path)
    |
    | from libraries.ESTB import ESTB
    |
    | class estb_956548(ESTB):
    |
    |     ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    |
    |     def __init__(self):
    |
    |         # Dont change these
    |         ESTB.__init__(self)
    |         self.set_property("shortname",self.__class__.__name__)
    |         # Start box specifics here
    |         self.create_interface("eth0","10.172.249.104","00:03:E6:95:65:48")
    |         self.set_property("family","HDB72")
    |         self.set_property("serialnumber", "26-4775412")
    |         self.set_property("hnr_repeat_rate", "0.31")
    |         self.set_property("debugport","/dev/ttyUSB2")

    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, family='HDB72', ssh_prompt="(\/.* #|~ #)", debugport=None,
                 fakekey_port=None, fakekey_keymapfile=None, debug_password='entonehd',
                 hnr_repeat_rate="0.12", debugprompt="(\/.* #|~ #)",
                 debugprompt_regex=True, ssh_newline='\r\n', ssh_user='root',
                 entone_boot_ini=None):

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
        self._builtin = BuiltIn.BuiltIn()

        # Stats collection interface
        self.stats_collection = None

        # Debug properties
        self._debug = None
        self._debugport = debugport
        self._fatals = ['Kernel panic -']
        self._fatal = False
        self._debugprompt = debugprompt
        self._debugprompt_regex = debugprompt_regex
        self._debug_password = debug_password
        self._logread_is_running = False

        # Fakekey properties
        self._fakekey_port = fakekey_port
        self._fakekey_keymapfile = fakekey_keymapfile
        self._fakekey = None
        self._hnr_repeat_rate = hnr_repeat_rate

        # InfraRedBlaster properties
        self._ir_port = None
        self._ir = None

        # Power IP port settings
        self._powerip_port = None
        self._powerip_type = "netbooter"

        # Enable STB SSH connection properties
        self.ssh_conn = SSHLibrary.SSHLibrary(loglevel='TRACE')
        self._ssh_user = ssh_user
        self._ssh_newline = ssh_newline
        self._ssh_keyfile = './resources/keys/entone_ssh_system_rsa_20130306_000001.openssh_private'
        self._ssh_login_prompt = ' #'
        self._ssh_cmd_prompt = ssh_prompt
        self._keep_ssh_open = False
        self._ssh_timeout = '10 seconds'
        self._ssh_tunnel_user = ''
        self._ssh_tunnel_password = ''

        # Entone Boot ini path
        self._ini_path = entone_boot_ini

        self._rest_api = ESTBRESTAPI(self)

        # WiFi model properties
        self._wifi = ESTBWiFi(self)

        # System functions and properties
        self._system = ESTBSystem(self)

        # Player functions and properties
        self._player = ESTBPlayer(self)

        # Recorder functions and properties
        self._recorder = ESTBRecorder(self)

        # Browse functions and properties
        self._browse = ESTBBrowse(self)

        # Tuner functions and properties
        self._tuner = ESTBTuner(self)

        self._time_control = ESTBTimeControl(self)

        # INI file for Upgrade/Downgrade soak testing
        self._INI = "new"
        self._ini_dir = "/var/www/entone/<PLATFORM>"




    def __del__(self):
        self.close_ssh_connection()
        self.close_all()

    #-------------
    # ESTB WiFi Test
    #-------------
    def print_wifi_config(self):
        print self._wifi.get_config_string()

    def test_commit_wifi_config(self,ssid = None,akm = None,key = None):
        self._wifi.set_config(ssid = ssid, akm = akm, key = key)
        print self._wifi.get_config_string()
        self._wifi.commit_config()
        return self._wifi.verify_config()

    def test_connect_wifi(self):
        if self._wifi.scan(expected_ssid=self._wifi.ssid):
            return self._wifi.join()
        else:
            return False
    #-------------
    # End of ESTB WiFi Test
    #-------------
    #-------------
    # ESTB AV Test
    # AV test implemented here can only use in:
    # ETV Release, Minerva Release
    #-------------

    def forget_wifi_connection(self):
        """
        Remove existing wifi connection setting using REST API.

        Author: Victor.WU
        Date:   2DEC16

        Returns True if it is successful,
        return False if it is not successful.

        Examples:-
        | ${res}= | forget wifi connection |
        """
        return self._wifi.forget_wifi_connection()

    def send_curl_command_and_return_output(
        self, method, url, data, need_status_code, send_method):
        """
        Use SSH connection or Debug connection to send REST API command
        to the stb.

        Available arguments:
            method: GET, POST, PUT, DELETE
            need_status_code: True, False
            send_method: ssh, console

        Author: Mike.GUO
        Date:   28SEP16

        Returns a string of curl command return output from stb.

        Examples:-
        | ${res}= | send curl command and return output | POST | player | "{\"window_type\":\"main\"}" | ${True} | ssh |
        """
        return self._rest_api.send_curl_command_and_return_output(
            method, url, data, need_status_code, send_method)

    def send_curl_command_and_expect_200(
        self, method, url, data, send_method, explain_str):
        """
        Use SSH connection or Debug connection to send REST API command
        to the stb and returns if the result contains "HTTP/1.1 200 OK",
        and log the explain_str to log file if return False.

        Available arguments:
            method: GET, POST, PUT, DELETE
            send_method: ssh, console

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the curl command result contains
        "HTTP/1.1 200 OK".

        Examples:-
        | ${res}= | send curl command and expect 200 | "POST" | "player/1/open" | "{\"src\":\"udp://233.22.133.12:8110\",\"pltbuf\":\"3600\"}" | "ssh" | "Open source" |
        """
        return self._rest_api.send_curl_command_and_expect_200(
            method, url, data,send_method, explain_str)

    def send_curl_command_and_expect_json(
        self, method, url, data, send_method, explain_str):
        """
        Use SSH connection or Debug connection to send REST API command
        to the stb and try to resolve the result to a json object,
        and log the explain_str to log file if can not resolve the result as
        json.

        Available arguments:
            method: GET, POST, PUT, DELETE
            send_method: ssh, console

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Dict of json data if resolve is successful, return False if
        resolve is not successful.

        Examples:-
        | ${res}= | send curl command and expect json | "GET" | "player/1" | "audio" | "ssh" | "Get audio languages" |
        """
        return self._rest_api.send_curl_command_and_expect_json(
            method, url, data, send_method, explain_str)

    def hnr_console_password(self):
        """
        Use Pyhnr to simulate remote press console unlock password to try to
        unlock the console.

        Need system EVN VAR:
        UNLOCKSECUREINIT_CMD: The path of estb featured pyhnr program and the
                              unlock console password separated by a space.
        JENKINS_USERNAME: The username of jenkins machine running the
                          pyhnr program.
        JENKINS_PW: The password of jenkins machine running the
                    pyhnr program.

        Author: Mike.GUO
        Date:   28SEP16

        No return
        """
        return self._system.hnr_console_password()

    def reboot_stb_using_debug(self):
        """
        Reboot the stb by sending "reboot" to stb console then expect "S99"
        which indicates the stb is up and ready for console, then try hnr
        unlock the console. Try login both console and ssh, try close the
        splash and start EntoneWebEngine. Return True if non of these steps
        get error, False if error.

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the reboot and init is successful in 150s.
        """
        return self._system.reboot_stb_using_debug()

    def reboot_to_stop_boot(self, method="ssh", init_test=True):
        """
        Use SSH connection or Debug connection to send reboot command and
        let the stb to reboot to stopboot mode by setting bootMethod=1.
        Returns true if ping good in 180s and correctly logged in(ssh)/Find
        "S99" in 150s and correctly logged in(debug), false if timeout or
        error while login.

        Available arguments:
            method: ssh, console
            init(Whether to close the splash and start EntoneWebEngine): True, False

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the reboot and init is successful in 180s.

        Examples:-
        | ${res}= | reboot to stop boot | "ssh" | ${True} |
        """
        return self._system.reboot_to_stop_boot(method, init_test)

    def check_stop_boot(self):
        """
        Check if the stb is in stop boot mode.

        Author: Victor.WU
        Date:   25OCT16

        Returns True if stb is in stop boot mode,
        return False if it is not.
        """
        return self._system.check_stop_boot()

    def reboot_to_normal_boot(self, method="ssh"):
        """
        Use SSH connection or Debug connection to send reboot command and
        let the stb to reboot to normalboot mode by setting bootMethod=0.
        Returns true if ping good in 180s and correctly logged in(ssh)/Find
        "S99" in 150s and correctly logged in(debug), false if timeout or
        error while login. This function not try to init for tests after login.

        Available arguments:
            method: ssh, console

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the reboot is successful in 180s.

        Examples:-
        | ${res}= | reboot to normal boot | "ssh" |
        """
        return self._system.reboot_to_normal_boot(method)

    def get_first_player(self):
        """
        Get the first player in players list using REST API.

        Author: Mike.GUO
        Date:   28SEP16

        Returns a string of player id if resolve is successful,
        return False if resolve is not successful or no player available.
        """
        return self._player.get_first_player()

    def open_a_new_player(self, src, pltbuf=3600, window_type="main"):
        """
        Create a new player using REST API and return its player id.

        Available arguments:
            src: A string following "[protocol]://[id or frequency]:[port]/[program id]"
            pltbuf: An integer indicates PLTV buffer size, in seconds
            window_type: main, pip

        Author: Mike.GUO
        Date:   28SEP16

        Returns a string player id if resolve is successful,
        return False if resolve is not successful or no player available.

        Examples:-
        | ${res}= | open a new player | "dvbc://558000000/1?symbolRate=6875000" | 3600 | "pip" |
        """
        return self._player.open_a_new_player(src, pltbuf, window_type)

    def change_player_src(self, player_id, src, playnow=1):
        """
        Change a player's playing url using REST API and return if the change
        is successful.

        Available arguments:
            player_id: A string of player id
            src: A string following "[protocol]://[id or frequency]:[port]/[program id]"
            playnow: 1(Play immidiately after changing the url), 0(don't play)

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the changing is successful.

        Examples:-
        | ${res}= | change player src | "1" | "dvbc://558000000/1?symbolRate=6875000" | 1 |
        """
        return self._player.change_player_src(player_id, src,  playnow)

    def change_player_param(self, player_id, x=0, y=0, z=0, h=0, w=0):
        """
        Change a pip player's parameter using REST API and return if the change
        is successful.

        Available arguments:
            player_id: A string of player id
            x,y,z: coordinates of the pip window
            h,w: height and width of the pip window

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the changing is successful.

        Examples:-
        | ${res}= | change player param | "1" | 0 | 0 | 9 | 800 | 600 |
        """
        return self._player.change_player_param(player_id, x, y, z, h, w)

    def player_command_play(self, player_id, speed=1):
        """
        Send a command to let a player start to play using REST API and return
        if the command is successful.

        Available arguments:
            player_id: A string of player id
            speed: Playing speed, >1 is FF, <0 is REWIND

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | player command play | "1" | 50 |
        """
        return self._player.player_command_play(player_id, speed)

    def player_command_pause(self, player_id):
        """
        Send a command to let a player pause playing using REST API and return
        if the command is successful.

        Available arguments:
            player_id: A string of player id

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | player command play | "1" |
        """
        return self._player.player_command_pause(player_id)

    def player_command_seek(self, player_id, seek_value, mode=0):
        """
        Send a command to let a player seek a position using REST API and return
        if the command is successful.

        Available arguments:
            player_id: A string of player id
            seek_value: A string of time position
            mode: How to seek this position:
                0 - absolute,
                1 - relative to current position,
                2 - relative to start of stream/buffer,
                3 - relative to end of stream,
                4 - by real time in UTC,
                128 - stop, play,
                129 - switch to live

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | player command seek | "1" | 3600s | 2 |
        """
        return self._player.player_command_seek(player_id, seek_value, mode)

    def get_available_audio_langs(self, player_id):
        """
        Get available audio tracs and thier languages of a player
        using REST API and return the audio language list.

        Available arguments:
            player_id: A string of player id

        Author: Mike.GUO
        Date:   28SEP16

        Returns a List of languages if successful, False if resolve json failed.

        Examples:-
        | ${res}= | get available audio langs | "1" |
        """
        return self._player.get_available_audio_langs(player_id)

    def change_audio_lang(self, player_id, lang):
        """
        Change the audio language of a player using REST API and return if
        the command is successful.

        Available arguments:
            player_id: A string of player id
            lang: A string of language name

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | change audio lang | "1" | "deu" |
        """
        return self._player.change_audio_lang(player_id, lang)

    def set_AC3(self, value):
        """
        Send a command to set AC3 set value 0 for disable 1 for enable
        and return if the command is successful.

        Author: Victor.WU
        Date:   24NOV16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | set AC3 | 1 |
        | ${res}= | set AC3 | 0 |
        """
        return self._system.set_AC3(value)


    def enable_subtitle(self):
        """
        Send a command to enalbe subtitle on PAL mode stb and return
        if the command is successful.

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | enable subtitle |
        """
        return self._player.enable_subtitle()

    def set_subtitle_preferred_lang(self, lang):
        """
        Set subtitle preferred language audio in system
        using REST API and return if the command succeeded.

        Available arguments:
            lang: A string of language name

        Author: Victor.WU
        Date:   21NOV16

        Returns a Bool indicates if the command succeeded.

        Examples:-
        | ${res}= | set subtitle preferred lang | "nor" |
        """
        return self._player.set_subtitle_preferred_lang(lang)

    def get_available_subtitle_langs(self, player_id):
        """
        Get available audio tracks and thier languages of a player
        using REST API and return the subtitle language list.

        Available arguments:
            player_id: A string of player id

        Author: Mike.GUO
        Date:   28SEP16

        Returns a List of languages if successful, False if resolve json failed.

        Examples:-
        | ${res}= | get available subtitle langs | "1" |
        """
        return self._player.get_available_subtitle_langs(player_id)

    def change_subtitle_lang(self, player_id, lang):
        """
        Change the subtitle language of a player using REST API and return if
        the command is successful.

        Available arguments:
            player_id: A string of player id
            lang: A string of language name

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | change subtitle lang | "1" | "deu" |
        """
        return self._player.change_subtitle_lang(player_id, lang)

    def enable_cc(self, player_id):
        """
        Send a command to enalbe cc on NTSC mode stb and return
        if the command is successful.

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | enable cc |
        """
        return self._player.enable_cc(player_id)

    def change_cc_on(self, mode):
        """
        Change the cc source using REST API and return if the command is
        successful.

        Available arguments:
            player_id: A string of player id
            mode: A string indicating which cc type should be used. Available:
                  "off", "On TV", "Analog CC1", "Analog CC2", "Analog CC3",
                  "Analog CC4", "Digital CC1", "Digital CC2", "Digital CC3",
                  "Digital CC4", "Digital CC5", "Digital CC6"

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | change cc on | "1" | "Digital CC1" |
        """
        return self._player.change_cc_on(mode)

    def get_hdmi_supported_resolution(self):
        """
        Get supported resolution of current hdmi setting using REST API and
        return the subtitle language list.

        Author: Mike.GUO
        Date:   28SEP16

        Returns a list of strings indicating available resolutions if
        successful, False if resolve json failed.

        Examples:-
        | ${res}= | get hdmi supported resolution |
        """
        return self._system.get_hdmi_supported_resolution()

    def change_resolution(self, resolution):
        """
        Change the current resolution using REST API and return if the command
        is successful.

        Available arguments:
            resolution: A string indicating resolution be used. Available:
                "1080p24", "1080p30", "1080p50", "1080p60", "1080i","720p", "576p",
                  "576i", "480p", "480i", "4kp24", "4kp25", "4kp30", "4kp50", "4kp60",
                  "unchange", "max_opt"

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | change resolution | "1080p24" |
        """
        return self._system.change_resolution(resolution)

    def change_aspect_ratio(self, ratio):
        """
        Change the current aspect ratio using REST API and return if the
        command is successful.

        Available arguments:
            ratio: A string indicating aspect ratio be used. Available:
                  "16:9 Pillar", "16:9 Wide", "16:9 Zoom", "16:9 Panorama",
                  "4:3 Crop", "4:3 Letterbox", "4:3 Squeeze", "14:9"

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | change aspect ratio | "16:9 Pillar" |
        """
        return self._system.change_aspect_ratio(ratio)

    def change_hdmi_hotplug_mode(self, mode):
        """
        Change the current HDMI hotplug mode using REST API and return if the
        command is successful.

        Available arguments:
            mode: A string indicating HDMI hotplug mode be used. Available:
                  "default", "mode1", "mode2", "mode3", "mode4"

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | change hdmi hotplug mode | "mode2" |
        """
        return self._system.change_hdmi_hotplug_mode(mode)

    def change_system_audio(self, right_volume, left_volume=-1, mute="false"):
        """
        Change the current system volume using REST API and return if the
        command is successful.

        Available arguments:
            right_volume: A integer from 1 to 100 indicating the right volume
            right_volume: A integer from 1 to 100 indicating the left volume,
                          it will be the same as right volume if not inputed
            mute: "false" or "true" indicating mute or not

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | change system audio | "100" | "50" | "true" |
        """
        return self._system.change_system_audio(right_volume, left_volume, mute)

    def change_front_panel_params(
            self, display_mode, display_brightness, front_panel_led,
            clock_mode="AUTO"):
        """
        Change the system's front panel parameter using REST API and return if
        the change is successful.

        Available arguments:
            display_mode: ESS_DISPLAY_MODE_SINGLE: 1, ESS_DISPLAY_MODE_DUAL: 2
            display_brightness: integer indicating led brightness
            front_panel_led: EFP_MODE_ON: 1 , EFP_MODE_OFF: 2, EFP_MODE_ON_OFF: 3
            clock_mode: AUTO, 12, 24

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the changing is successful.

        Examples:-
        | ${res}= | change player param | 1 | 50 | 2 | 3 | "AUTO" |
        """
        return self._system.change_front_panel_params(
            display_mode, display_brightness, front_panel_led, clock_mode)

    def change_color_system(
            self, color_system, force_reboot=True, init_test=True):
        """
        Change the system's color system using writeHWBLK and return if the
        change is successful.

        Available arguments:
            color_system: NTSC, PAL
            force_reboot: whether to reboot the stb if the color system do not
                          need to change
            init_test: whether to close the splash and start entoneWebEngine

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the changing is successful.

        Examples:-
        | ${res}= | change color system | NTSC | ${True} | ${False} |
        """
        return self._system.change_color_system(
            color_system, force_reboot, init_test)

    def get_cpu_idle(self):
        """
        Get the system's CPU idle percentage using iostat and return if the
        change is successful.

        Author: Mike.GUO
        Date:   28SEP16

        Returns a String of percentage of CPU idle.
        """
        return self._system.get_cpu_idle()

    def get_process_running(self, process_name):
        """
        Get if a process is currently running using ps and return the running
        status.

        Author: Mike.GUO
        Date:   28SEP16

        Available arguments:
            process_name: a string of process name

        Returns a bool indicating is the process is available in ps list.
        """
        return self._system.get_process_running(process_name)

    def write_cpu_idle_list_to_csv(self, filename, cpu_idle_list, total_time):
        """
        Write the system's CPU idle percentage list to a local file stored in
        $WORKSPACE with no return value.

        Author: Mike.GUO
        Date:   28SEP16

        Available arguments:
            filename: csv filename to write in $WORKSPACE
            CPU_Idle_List: A list of integer of CPU idle percentage
            total_time: Total time used to capture the CPU idle list in seconds

        Examples:-
        | ${res}= | write cpu idle list to csv | "idle.csv" | ${idle_list} | 10 |
        """
        return self._system.write_cpu_idle_list_to_csv(
            filename, cpu_idle_list, total_time)

    def set_fan_on_off(self, on_off):
        """
        Set the fan running or stop of the current stb.

        Author: Mike.GUO
        Date:   18OCT16

        Available arguments:
            on_off: A boolean variable, True to turn on the fan, False to turn off

        Return a bool indicating if the command status is successful.

        Examples:-
        | ${res}= | set fan on off | ${False} |
        """
        return self._system.set_fan_on_off(on_off)

    def get_standby_mode(self):
        """
        get the Standby Mode of the DUT.


        Returns the DUT's standby mode setting in human readable form
        stored in sys_config.txt or the string "error" if there was a
        problem getting the standby mode.

        Examples:-
        | ${res}= | get standby mode |
        """
        return self._system.get_standby_mode()

    def set_standby_mode(self, standby_mode="quick"):
        """
        Set the Standby Mode of the DUT to "quick" or "deep".


        Returns a bool indicating if the command status is successful or not.

        Examples:-
        | ${res}= | set standby mode |
        | ${res}= | set standby mode | quick |
        | ${res}= | set standby mode | deep  |
        """
        return self._system.set_standby_mode(standby_mode)


    def get_network_status(self):
        """
        Get the system's network status for all ethernet nics and return the
        json object.

        Author: Mike.GUO
        Date:   27OCT16

        Return a json object of nic configs if successful, False if failed.
        """
        return self._system.get_network_status()

    def get_current_active_wan(self):
        """
        Get the name of the active wan and return it.

        Author: Mike.GUO
        Date:   27OCT16

        Return a string of the wan name if successful, False if failed.
        """
        return self._system.get_current_active_wan()

    def get_current_active_nic(self):
        """
        Get the system's network status for the active ethernet nic and return
        the json object.

        Author: Mike.GUO
        Date:   27OCT16

        Return a json object of nic configs if successful, False if failed.
        """
        return self._system.get_current_active_nic()

    def get_entone_env(self):
        """
        Get the system's environment variables that related to entone INI.

        Author: Mike.GUO
        Date:   27OCT16

        Return a json object of the env vars if successful, False if failed.
        """
        return self._system.get_entone_env()

    def get_storage_space_info(self, specific=""):
        """
        Get the system's storage info for pvr and media.

        Author: Mike.GUO
        Date:   27OCT16

        Available arguments:
            specific: "", "pvr", "media"

        Return a json object of the storage info if successful, False if failed.

        Examples:-
        | ${res}= | get storage space info | "pvr" |
        """
        return self._system.get_storage_space_info(specific)

    def get_standby_info(self):
        """
        Get the system's standyby information.

        Author: Mike.GUO
        Date:   27OCT16

        Return a json object of the standyby information if successful, False
        if failed.
        """
        return self._system.get_standby_info()

    def get_syslog_info(self):
        """
        Get the system's syslog information.

        Author: Mike.GUO
        Date:   27OCT16

        Return a json object of the syslog information if successful, False
        if failed.
        """
        return self._system.get_syslog_info()

    def set_syslog_config(self, log_level, log_facility, log_mode, log_server):
        """
        Set the system's syslog configs.

        Author: Mike.GUO
        Date:   27OCT16

        Available arguments:
            log_level: An int variable, 1~7
            log_facility: An int variable, 1~3
            log_mode: A string, "RAM" or "HDD"
            log_server: A string, should be an IP address

        Return a bool indicating if the command status is successful.

        Examples:-
        | ${res}= | set fan on off | 7 | 3 | "RAM" | "10.0.33.179" |
        """
        return self._system.set_syslog_config(log_level, log_facility, log_mode,
            log_server)

    def open_a_new_recorder(self, src, assetname):
        """
        Create a new recorder using REST API and return its recorder id.

        Available arguments:
            src: A string following "[protocol]://[id or frequency]:[port]/[program id]"
            assetname: A string of the asset name you want to restore the ts.

        Author: Mike.GUO
        Date:   28SEP16

        Returns a string recorder id if resolve is successful,
        return False if resolve is not successful or no recorder available.

        Examples:-
        | ${res}= | open a new recorder | "dvbc://558000000/1?symbolRate=6875000" | "testAsset1" |
        """
        return self._recorder.open_a_new_recorder(src, assetname)

    def change_recorder_src(self, recorder_id, src, assetname):
        """
        Change a recorder's playing url using REST API and return if the change
        is successful.

        Available arguments:
            recorder: A string of recorder id
            src: A string following "[protocol]://[id or frequency]:[port]/[program id]"
            assetname: A string of the asset name you want to restore the ts.

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the changing is successful.

        Examples:-
        | ${res}= | change recorder src | "1" | "dvbc://558000000/1?symbolRate=6875000" | "testAsset1" |
        """
        return self._recorder.change_recorder_src(recorder_id, src,assetname)

    def recorder_command_start(self, recorder_id):
        """
        Send a command to let a recorder start to record using REST API and
        return if the command is successful.

        Available arguments:
            recorder_id: A string of recorder id

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | recorder command start | "1" |
        """
        return self._recorder.recorder_command_start(recorder_id)

    def recorder_command_stop(self, recorder_id):
        """
        Send a command to let a recorder to stop record using REST API and
        return if the command is successful.

        Available arguments:
            recorder_id: A string of recorder id

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | recorder command stop | "1" |
        """
        return self._recorder.recorder_command_stop(recorder_id)

    def find_asset(self, assetname):
        """
        Find if an asset exist using REST API and return the list of the asset's
        attribute if the command is successful.

        Available arguments:
            assetname: A string of the asset name you want to restore the ts.

        Author: Mike.GUO
        Date:   28SEP16

        Returns a list of the asset's attribute if the command is successful,
        return False if json resolve error.

        Examples:-
        | ${res}= | find asset | "testAsset1" |
        """
        return self._recorder.find_asset(assetname)

    def delete_asset(self, assetname):
        """
        Send a command to delete an asset using REST API and return if the
        command is successful.

        Available arguments:
            assetname: A string of the asset name you want to delete.

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the command is successful.

        Examples:-
        | ${res}= | delete asset | "testAsset1" |
        """
        return self._recorder.delete_asset(assetname)

    def get_available_browse_dev(self):
        """
        Get available browsealbe devices of current system using REST API and
        return the devices list.

        Author: Mike.GUO
        Date:   28SEP16

        Returns a list of strings indicating available devices if successful,
        False if resolve json failed.

        Examples:-
        | ${res}= | get available browse dev |
        """
        return self._browse.get_available_browse_dev()

    def browse_path(self, device, path):
        """
        Browse a device path using REST API and return the list of files if the
        path is a dir, the content of file if the path is file, False if the
        command if not successful.

        Available arguments:
            device: A string of the device name you want browse.
            path: A string of the reletive path of you destination to root dir
                  of the device.

        Author: Mike.GUO
        Date:   28SEP16

        Returns a list of files if the path is a dir, a string of the content
        of file if the path is file, False if the command if not successful.

        Examples:-
        | ${res}= | browse path | "usb" | "test.txt" |
        """
        return self._browse.browse_path(device, path)

    def open_a_new_tuner(self, standard, symbol_rate, frequency):
        """
        Create a new tuner using REST API and return its tuner id.

        Available arguments:
            standard: atsc, dvbc, ocqam, dvbt, dvbt2, dvbs, dvbs2, ntsc, isdbt
            symbol_rate: A string of the symbol rate defined by source provider
            frequency: A string of the frequence defined by source provider

        Author: Mike.GUO
        Date:   28SEP16

        Returns a string tuner id if resolve is successful,
        return False if resolve is not successful or no tuner available.

        Examples:-
        | ${res}= | open a new tuner | "dvbc | "6875000" | "558000000" |
        """
        return self._tuner.open_a_new_tuner(standard, symbol_rate, frequency)

    def change_tuner_setting(self, tuner_id, standard, symbol_rate, frequency):
        """
        Change a tuner's parameter using REST API and return if the change
        is successful.

        Available arguments:
            tuner_id: A string of tuner id
            standard: atsc, dvbc, ocqam, dvbt, dvbt2, dvbs, dvbs2, ntsc, isdbt
            symbol_rate: A string of the symbol rate defined by source provider
            frequency: A string of the frequence defined by source provider

        Author: Mike.GUO
        Date:   28SEP16

        Returns a Bool indicates if the changing is successful.

        Examples:-
        | ${res}= | change player param | "0" | "dvbc | "6875000" | "558000000" |
        """
        return self._tuner.change_tuner_setting(
            tuner_id, standard, symbol_rate, frequency)

    def get_tuner_property(self, tuner_id):
        """
        Get a tuner's properties of current system using REST API and
        return the json result in dict format.

        Author: Mike.GUO
        Date:   28SEP16

        Available arguments:
            tuner_id: A string of tuner id

        Returns a dict of strings indicating the tuner's properties if
        successful, False if resolve json failed.

        Examples:-
        | ${res}= | get tuner property | "0" |
        """
        return self._tuner.get_tuner_property(tuner_id)

    def get_current_time(self):
        """
        Get the current system time using python datetime and
        return the datetime object.

        Author: Mike.GUO
        Date:   28SEP16

        Returns an object of detatime type.
        """
        return self._time_control.get_current_time()

    def convert_time_delta(self, time_delta):
        """
        Get a string in format "hh:mm" to a datetime.timedelta object.

        Author: Mike.GUO
        Date:   28SEP16

        Available arguments:
            time_delta: A string in format "hh:mm"

        Returns an object of datetime.timedelta type.

        Examples:-
        | ${res}= | convert time delta | "02:30" |
        """
        return self._time_control.convert_time_delta(time_delta)

    def datetime_add(self, datetime1, datetime2):
        """
        Do add operation to two datetime objects or datetime.timedelta.

        Author: Mike.GUO
        Date:   28SEP16

        Available arguments:
            datetime1, datetime2: A datetime or datetime.timedelta object

        Returns an object of datetime type.

        Examples:-
        | ${res}= | datetime add | datetime.datetime(2016,9,16,11,19,54) | datetime.timedelta(hours=10) |
        """
        return self._time_control.datetime_add(datetime1, datetime2)

    def datetime_substract(self, datetime1, datetime2):
        """
        Do substract operation to two datetime objects or datetime.timedelta.

        Author: Mike.GUO
        Date:   28SEP16

        Available arguments:
            datetime1, datetime2: A datetime or datetime.timedelta object

        Returns an object of datetime type.

        Examples:-
        | ${res}= | datetime substract | datetime.datetime(2016,9,16,11,19,54) | datetime.timedelta(hours=10) |
        """
        return self._time_control.datetime_substract(datetime1, datetime2)

    def datetime_less_than(self, datetime1, datetime2):
        """
        Compare two datetime objects and return if datetime1 is less than
        datetime2.

        Author: Mike.GUO
        Date:   28SEP16

        Available arguments:
            datetime1, datetime2: A datetime or datetime.timedelta object

        Returns an object of datetime type.

        Examples:-
        | ${res}= | datetime less than | datetime.datetime(2016,9,16,11,19,54) | datetime.datetime(2016,10,16,11,19,54) |
        """
        return self._time_control.datetime_less_than(datetime1, datetime2)

    #-------------
    # End of ESTB AV Test
    #-------------

    def get_robotwebfiles_url(self):
        """
        Returns the url of this robot's robotwebfiles folder, so it is possible to wget files from there

        RIDE Example:-
        | ${webfiles}= | UUT.Get Robotwebfiles Url |

        Python Example:-
        | url = uut.get_robotwebfiles_url() |


        """
        import socket
        myhostname = socket.gethostname()
        return "http://%s/robotwebfiles" % myhostname



    def install_etv_channel_list(self, channel_list, suppress_reboot=False):
        """
        Takes a channel list and the necessary script from the robotwebfiles/etv_channels folder in this robot PC
        and installs them on a STB.

        The channel list will not become active without a reboot which will happen by default.

        You can change this behaviour with the option 'suppress_reboot=${True}'

        Examples:-
        | UUT.Install ETV Channel List | default_channels.txt | |
        | UUT.Install ETV Channel List | reduced_channels.txt | suppress_reboot=${True} |

        """

        # Get the address of the local PC

        rwf_url = self.get_robotwebfiles_url()


        logger.info("Getting 'channel_import_tool.sh' from %s/etv_channels" % rwf_url)

        ret, rc = self.send_command_and_return_output_and_rc(
            "wget %s/etv_channels/channel_import_tool.sh" % rwf_url)

        if int(rc) != 0:
            raise ESTBError(
                "Unable to locate 'channel_import_tool.sh' at location '%s/etv_channels'.  Please ensure robotwebfiles is mapped to your local web instance correctly (which is done by install.sh)" %
                rwf_url)

        logger.info("Getting the channel list '%s' from %s/etv_channels" % (channel_list, rwf_url))

        ret, rc = self.send_command_and_return_output_and_rc(
            "wget %s/etv_channels/%s" % (rwf_url, channel_list))

        if int(rc) != 0:
            raise ESTBError("Unable to locate '%s' at location '%s/etv_channels'.  Please ensure you supplied a valid filename and that robotwebfiles is mapped to your local web instance correctly (which is done by install.sh)" % (channel_list, rwf_url))

        logger.info("Installing channel list '%s'" % channel_list)


        ret, rc = self.send_command_and_return_output_and_rc(
            "chmod +x channel_import_tool.sh; ./channel_import_tool.sh localhost %s" % channel_list)

        if int(rc) != 0:
            raise ESTBError("Error running the channel import tool on the target device.")
        else:
            logger.info("Installed %s as the new channel list." % channel_list)


        if not suppress_reboot:
            logger.info("Rebooting STB to use new channel list.")
            self.reboot_stb()




    def _robust_ssh_login_and_keep_ssh_open(self):
        """
        Make ssh login more robust as during soak tests there are random failures
        that can be cured by a simple retry.
        This function retries a maximum of 'maxAttempts-1' times before giving up completely.
        """

        maxAttempts = 6
        attemptCnt  = 1
        while attemptCnt < maxAttempts:
            try:
                self.login_and_keep_ssh_open()
            except (RuntimeError, NoValidConnectionsError):
                logger.debug("_robust_ssh_login_and_keep_ssh_open: Failed to login via ssh! Attempt %d" % attemptCnt)
                attemptCnt = attemptCnt + 1
                if attemptCnt == maxAttempts:
                    raise RuntimeError("_robust_ssh_login_and_keep_ssh_open:  exceeded max login attempts!")
                time.sleep(2)
            else:
                # Force loop to terminate on 'success'.
                logger.debug("_robust_ssh_login_and_keep_ssh_open: login via ssh SUCCESS! Attempt %d" % attemptCnt)
                attemptCnt = 6

    def check_sw_version(self, app, bbl=None, pbl=None, ufs=None):
        """
        Takes an App (and optionally PBL, BBL and UFS) tag and checks if that is currently installed.

        Returns TWO values, a boolean result and a string explaining it (which will be empty if the result was True)

        Example:-
        | ${ret} | ${reason}= | Check SW Version | 14.5.0_eng12-etv-vas--opera4 |                    |
        | ${ret} | ${reason}= | Check SW Version | 14.5.0_eng12-etv-vas--opera4 | bbl=14.7.0_eng7-bb |

        """

        ret = True  # Assume ok unless an assertion fails
        reason = ''

        # App

        current_app = self.send_command_and_return_output("cat app_identinfo.txt | grep '$TAG' | awk '{print $2}'")

        if app != self.get_installed_app():
            ret = False
            reason += "APP does not match.\n"

        if not bbl is None:
            if bbl != self.get_installed_bbl():
                ret = False
                reason += "BBL does not match.\n"

        if not pbl is None:
            if pbl != self.get_installed_pbl():
                ret = False
                reason += "PBL does not match.\n"

        if not ufs is None:
            if ufs != self.get_installed_ufs():
                ret = False
                reason += "UFS does not match.\n"

        return ret, reason

    def get_installed_app(self):
        ret = self.send_command_and_return_output(
            "cat app_identinfo.txt | grep '$TAG' | awk '{print $2}'").strip().strip('\r\n')
        logger.info("Installed APP = %s" % ret)
        return ret

    def get_installed_bbl(self):
        ret = self.send_command_and_return_output(
            "cat bbl_identinfo.txt | grep '$TAG' | awk '{print $2}'").strip().strip('\r\n')
        logger.info("Installed BBL = %s" % ret)
        return ret

    def get_installed_pbl(self):
        ret = self.send_command_and_return_output(
            "cat pbl_identinfo.txt | grep '$TAG' | awk '{print $2}'").strip().strip('\r\n')
        logger.info("Installed PBL = %s" % ret)
        return ret

    def get_installed_ufs(self):
        ret = self.send_command_and_return_output(
            "(nvram_env -l 2> /dev/null) | grep 'fufs' | awk -F'=' '{print $2}'").strip().strip('\r\n')
        logger.info("Installed UFS = %s" % ret)
        return ret

    def _send_ssh_command(self, command, interface=-1, ansi_escape=True):
        """     Sends a single SSH command and returns the output
        """
        logger.debug('_send_ssh_command: Running Command: %s' % (command))

        stb_ip = self._get_iface_ip(interface)

        if not self._keep_ssh_open:
            self._ssh_login(stb_ip)

        output = self.ssh_conn.write(command)

        output += self.ssh_conn.read_until_regexp(self._ssh_cmd_prompt)

        if self._keep_ssh_open:
            # When the SSH connection is maintained running multiple commands
            # we need to read again with a small delay to ensure we catch the
            # whole output of the command using another read
            output += self.ssh_conn.read(delay="0.5 seconds")

        if ansi_escape:
            # pybot doesn't cope well with colour chars,
            # remove them if the flag is set
            output = ANSI_ESCAPE.sub('', output)

        # Strip prompt from the command output
        output = re.sub(self._ssh_cmd_prompt, '', output)

        # Extra newlines and tildes are left in the response, remove them
        output = output.replace('\r\n~', '')

        # Strip the original command from the output
        output = output.replace(command, '')

        logger.debug('_send_ssh_command: Command Returned: %s' % (output))

        if not self._keep_ssh_open:
            self.close_ssh_connection()

        return output


    def _getINI(self):
        return(self._INI)

    def _setINI(self, ini_setting):
        self._INI = ini_setting

    def _get_ini_dir(self):
        return(self._ini_dir)

    def set_ini_dir(self, iniDir):
        """     Set the INI file directory path

        Examples:
        | ESTB.Set ini dir  | /var/www/entone/A160 |
        | ESTB.Set ini dir  | /var/www/entone/K500 |
        """

        self._ini_dir = iniDir

    def updowngrade_swap_ini(self, thisESN):
        """     Swap the INI file being used in the updowngrade soak test

        Examples:
        | ESTB.Updowngrade swap ini | ${ESN} |
        """

        ini_dir = self._get_ini_dir()
        symlinkname = ini_dir + "_" + thisESN + "_link.ini"
        curr_ini = self._getINI()

        cmd1 = "sudo rm -f " + symlinkname

        cmd2 = "sudo ln -s " + ini_dir + "_" + thisESN + "_"
        if curr_ini == "new":
            cmd2 = cmd2 + "old"
            self._setINI("old")
        else:
            cmd2 = cmd2 + "new"
            self._setINI("new")
        cmd2 = cmd2 + ".ini " + symlinkname

        thisCmd = cmd1 + "; " + cmd2

        logger.debug("INI cmd1='%s'" % (cmd1))
        logger.debug("INI cmd2='%s'" % (cmd2))
        logger.debug("thisCmd='%s'" % (thisCmd))

        logger.info("thisCmd='%s'" % (thisCmd))
        os.system(thisCmd)

    def set_ssh_keyfile_path(self, keypath):
        """  Set SSH Keyfile Path - Provides a path for the key used by SSH.
        Normally used in the estb definition file.
        """
        self._ssh_keyfile = keypath

    def _ssh_login(self, stb_ip):
        """     Creates a new SSH connection to the STB
        """
        if self._ssh_keyfile == None:
            raise RuntimeError('No keyfile set in ESTB defintion file')

        #self.ssh_conn.open_connection(stb_ip, prompt=self._ssh_login_prompt,
        #                           newline=self._ssh_newline,
        #                           timeout=self._ssh_timeout, port=10022)
        #
        #self.ssh_conn.login_with_public_key(self._ssh_user, self._ssh_keyfile)

        # Add a retry count to make ssh login more robust.
        maxAttempts = 6
        attemptCnt  = 1
        while attemptCnt < maxAttempts:
            try:
                self.ssh_conn.open_connection(stb_ip, prompt=self._ssh_login_prompt,
                                           newline=self._ssh_newline,
                                           timeout=self._ssh_timeout, port=10022)

                self.ssh_conn.login_with_public_key(self._ssh_user, self._ssh_keyfile)
            except (RuntimeError, NoValidConnectionsError):
                logger.debug("_ssh_login: Failed to login via ssh! Attempt %d" % attemptCnt)
                attemptCnt = attemptCnt + 1
                if attemptCnt == maxAttempts:
                    raise RuntimeError("_ssh_login: exceeded max login attempts!")
                time.sleep(2)
            else:
                # Force loop to terminate on 'success'.
                logger.debug("_ssh_login: login via ssh SUCCESS! Attempt %d" % attemptCnt)
                attemptCnt = 6


    def close_ssh_connection(self):

        """

        Close SSH Connection - Closes any open SSH connections and sets 'Keep SSH Open' to False


        """
        logger.debug('close_ssh_connection: closing all SSH connections')

        self._keep_ssh_open = False

        self.ssh_conn.close_all_connections()

    def wait_for_debug_inactivity(self, inactivefor, timeout='10 minutes'):
        """
        Wait for Debug Inactivity

        NOTE: This keyword requires debug capture to be active

        Using this keyword you can halt execution of the test until the output of debug
        has been inactive for a set time, or a timeout has been reached.

        This is useful for ensuring that a complex upgrade process, with several reboots,
        can corectly idenify when the full process has completed, i.e. output of debug has been
        inactive for 3 minutes, so lets check if the upgrade was successful.

        Examples:-
        | ${ret}=	| Wait for debug inactivity	| 3 minutes	|

        """

        timeout = utils.timestr_to_secs(timeout)
        inactivefor = utils.timestr_to_secs(inactivefor)

        start = time.time()

        timedout = True

        while time.time() < (start + timeout):
            # check the debug time

            try:
                if self._debug.get_time_since_last_read() > inactivefor:
                    timedout = False
                    break
            except AttributeError:
                raise ESTBError("Debug connection not open!")

            time.sleep(1)

        if timedout:
            logger.warn("Timed out while waiting for a period of debug inactivity")
        else:
            logger.info("Debug inactivity exceeded wait time.")




    def read_disk_space_levels(self):
        """
        NOT YET SUPPORTED FOR ESTB - Track in USS-169
        Need to port to use the SSH connection as well as to the enable commands

        Author: S. Housley
        Date:   21FEB14

        Returns a list of "total", "available" and "low" disk space levels as read from streamerctl

        Examples:-
        | ${disk_levels}=	| Read Disk Space Levels |
        """
        self._enable_warn()
        return

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
        NOT YET SUPPORTED FOR ESTB - Track in USS-169
        Needs to be ported to use the SSH connection for command running

        Author: S. Housley
        Date:   29JAN14

        Returns a LOW_DISK_SPACE_LEVEL value in Kbytes for a given percentage figure.

        Examples:-
        | Get Low Disk Space Level | 30%        |
        """
        self._enable_warn()
        return

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


    def detect_video_playback(self):
        """
        This keyword returns true if video playback is detected on the ESTB. This is achieved by SSHing into the STB and reading the number of
	decoded bytes twice at an interval of 5 seconds. If the second value is different to the first (can wrap around!) video is playing so
        0 is returned. Otherwise 1 is returned as video has not been detected.

	Examples:-
	| ${vid_playing} | ${retcode}= | Detect Video Playback |

        """ 

        result=0
        # Split the commands up. Hopefully this will resolve any issues with 'no output'?? especially for cmd1.
        cmd1 = "cat /tmp/dbg/decoder/*video* > /tmp/x.txt"
        cmd2 = "grep numBytes /tmp/x.txt > /tmp/y.txt"
        cmd3 = "cut -d \: -f 4 /tmp/y.txt | tr -d ' '"

        retcodes = self.send_commands(cmd1,cmd2)
        if retcodes[0]!=0 or retcodes[1]!=0:
            logger.warn("Command sequence failure #1 1st=%d 2nd=%d" % (retcodes[0], retcodes[1]))
            result = 1
            retcode = '1'
        else:
            first_val, retcode=self.send_command_and_return_output_and_rc(cmd3)
            if retcode=='0':
                first_val=int( first_val)
                logger.info("First Byte Count: %d" % first_val)
                time.sleep(5)

                retcodes = self.send_commands(cmd1,cmd2)
                if retcodes[0] != 0 or retcodes[1] != 0:
                    logger.warn("Command sequence failure #2 1st=%d 2nd=%d" % (retcodes[0], retcodes[1]))
                    result = 1
                    retcode = '1'
                else:
                    second_val, retcode=self.send_command_and_return_output_and_rc(cmd3)
                    if retcode=='0':
                        second_val=int(second_val)
                        logger.info("Second Byte Count: %d" % second_val)
                        if (second_val != first_val):
                            result=0
                        else:
                            result=1

        return result, retcode


    def fill_pvr(self, target_percent):
        """

        NOT YET SUPPORTED FOR ESTB - Track in USS-169
        Will need to be ported to use the SSH connection

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
        self._enable_warn()
        return

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
        | ESTB.Add Debug Listener    | AC_BOOT   |

        """
        logger.debug('add_debug_listener: adding listener "%s"' % (listener))

        if listener not in self._debug._listeners:
            self._debug.add_listener(listener)

    def remove_debug_listener(self, listener):
        """  Remove a text string to 'listen' for on the debug interface

        Opposite action to adding with `Add debug listener`.

        NOTE: The listener must exist in the listeners list or an error with be thrown

        Examples:
        | ESTB.Remove Debug Listener | AC_BOOT   |

        """
        if listener in self._debug._listeners:
            self._debug._listeners.remove(listener)
        else:
            raise ESTBError("ERROR: Trying to remove a listener that is not in the listeners list")


    def check_debug_listeners(self, reset=False):
        """  Check if any listener has been heard

        A list object is returned with information of which listeners were heard and at what time

        Optionally you can reset this list of 'heard' listeners to avoid getting the same information later

        Examples:
        | ${heards}= | ESTB.Check debug listeners |               |
        | ${heards}= | ESTB.Check debug listeners | reset=True    |

        """

        ret = self._debug.check_listeners()

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
                # We also don't want to know how long it took
                return 0
            else:
                raise ESTBError("Listener '%s' not heard within %s" % (listener, timeout))
        else:
            logger.debug("Listener '%s' heard in %ss" % (listener, seccount))
            return seccount

    def convert_seconds_to_timestring(self, seconds):
        seconds = int(seconds)
        return utils.secs_to_timestr(seconds)

    def send_command_over_debug(self, command, suppresslogin=False, timeout="30 seconds"):

        """  Sends a command over the serial debug connection

        This does not return any value, it sends the command blindly so it does not interrupt debug capture.

        A `Capture Debug` keyword must have been called earlier (in suitesetup normally) to be able to send
        commands over the serial interface.


        Examples:
        | Send command over debug   | rm -rf /PVR/0000000001    |

        """
        logger.debug('send_command_over_debug: Sending cmd: "%s"' % (command))
        self._debug.send_command(str(command), suppresslogin=suppresslogin, timeout=timeout)

    def send_commands_over_debug(self, *commands):

        """

        Sends multiple commands over the serial debug connection

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
        """     NOT YET SUPPORTED IN ESTB - Track in USS-171

        Set the wifi parameters

        This gives access, through keywords, to all elements of the radio interface
        """
        self._enable_warn()
        return

    def send_command_over_debug_and_return_output(self, command, timeout="3 seconds",
                                                    strip_newlines=False):
        """  Sends a command over the serial debug connection and waits for a response

        This will interrupt the debug handler (by stopping the syslogd process on the stb) while it
        waits to complete the command.  Command completion is assumed when the command prompt is seen.

        Debug will be re-enabled upon completion

        A `Capture Debug` keyword must have been called earlier (in suitesetup normally) to be able to send
        commands over the serial interface.

        A timeout (defaults to 3 seconds) will be applied when waiting for the prompt, ensure this is long enough
        when sending commands which take a while to complete.

        Examples:
        | ${ret}=   | Send command over debug and return output | cat /etc/version  |                       |
        | ${ret}=   | Send command over debug and return output | ls /mnt/nv        | timeout=20 seconds    |
        """
        if self._debug == None:
            logger.warn('Trying to send command over debug without capture!!!')
            return

        self.stop_logread()
        self._logread_is_running = False

        ret = self._debug.send_command_and_return_output(str(command), self._debugprompt, timeout, regex=True)

        logger.debug(ret)
        self.start_logread()

        if strip_newlines:
            logger.debug('stripping newlines')

            strp_ret = []
            for line in ret.split('\r\n'):
                if line != '':
                    strp_ret.append(line)

            ret = '\r\n'.join(strp_ret)

        return ret

    def stop_logread(self):
        """     Stops logread on the serial console to capture debug
        """
        self.send_command_over_debug('killall -q logread')
        time.sleep(0.2)

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

        NOTE: Deprecated in favour of `Send Key`

        Examples:
        | Send IR   | MENU  |


        """

        self._ir.send_ir(self._ir_port, code)

    def send_ir_codes(self, *codes, **kwargs):
        """
        Send any number of key codes to IR Blaster

        NOTE: Deprecated in favour of `Send Keys`

        :param codes: List of codes to send
        :param kwargs: IR Blaster kwargs

        """
        self._ir.send_ir_codes(self._ir_port, *codes, **kwargs)

    def send_keys(self, *codes, **kwargs):
        """
        Send a list of keys to HNRKey by default, or IR Blaster if configured in device file

        :param codes: any number of keys
        :param kwargs: pause: set the pause time between key presses

        Example:
        | UUT.Send_Keys	| DOWN	| RIGHT	| RIGHT	| pause=1 second	|

        """

        if self._ir_port is None:
            # IR Blaster is not set, pipe to HNRKey
            # Check it's a valid HNRKey
            self.send_hnrkeys(*codes, **kwargs)
        else:
            self.send_ir_codes(*codes, **kwargs)


    def set_ir_blaster(self, ir_host, ir_port, ir_remote):
        """  Sets the IR Net Box to blast IR at STB

        Requires ir_host (IP address), ir_port (1 to 16) & ir_remote (filename of remote codes)


        Examples:
        | Set ir blaster    | 10.172.241.147    | 1 | resources/remotes/RCU_AMINO_WILLOW.txt    |

        """
        self._ir_port = ir_port

        self._ir = InfraRedBlaster(ir_host)
        self._ir.load_remote(ir_remote)


    def send_key(self, key):
        """
        Sends a key code to HNRKey by default, but will redirect to IR Blaster if it is configured in the device file

        :param key - The key code to send

        Example:
        | UUT.Send Key	| DOWN	|

        """


        if self._ir_port is None:
            # IR Blaster is not set, pipe to HNRKey
            # Check it's a valid HNRKey
            if not key in self.list_hnrkeys():
                raise ESTBError("Invalid HNRKey value '%s'" % key)
            else:
                self.send_hnrkey(key)
        else:
            # Pipe to IRBlaster
            self.send_ir(key)


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
            raise ESTBError("Unable to reach STB with ping after %s" % timeout)
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
        """     Ping an IP, return 0 if the host is alive
        raise PingResponseError if the host is down
        """
        retcode = self._os.run_and_return_rc("ping -c 1 " + target)
        if retcode != 0:
            raise PingResponseError
        else:
            return 0

    def reboot_stb(self, pingtimeout="2 minutes", nocheck="1"):
        """  Reboots the STB using SSH over the active interface.
        It then uses `Ping STB Until Alive`, passing the 'pingtimeout'
        value as the timeout. A debug listener is also incorporated to
        check for the end of the boot up from the debug being output.
        To use this listener, set 'nocheck' to 0.

        If the SSH port was being held open it will be reopened after
        the wait period. If stb stats were being collected they will
        be halted and restarted after the wait period. A debug capture
        will stay open.

        This keyword will return the number of whole seconds it took
        for the STB to become responsive to ping if 'nocheck' is set to
        1. Else it returns the ping response time including the time
        time is took for the debug listener to be heard.

        Examples:
        | ${time}=           | ESTB.Reboot STB          |
        | ESTB.Reboot STB    | pingtimeout=3 minutes    |
        | ESTB.Reboot STB    | pingtimeout=3 minutes    | nocheck="0"   |


        """

        # Handle old method
        try:
            if pingtimeout.startswith("waitfor"):
                pingtimeout = pingtimeout.split("=")[1]
        except:
            logger.debug('reboot_stb: Failed to determine time string')

        restart_ssh = False
        restart_stats = False
        restart_debug = False

        # Force an HNR tunnel close
        try:
            self._fakekey.close()
        except:
            pass

        if (self._keep_ssh_open) and (self.ssh_conn != None):
            restart_ssh = True

        if self.stats_collection != None:
            restart_stats = True
            self.stats_collection.pause_stats_for_reboot()

        if (self._logread_is_running) and (self._debug != None):
            # No need to stop it, it will stop when rebooted
            self._logread_is_running = False
            restart_debug = True

        # Reboot box
        logger.info('reboot_stb: Rebooting STB now....')


        try:
            self._send_ssh_command('reboot')
            self.close_ssh_connection()
            start = time.time()
        except (RuntimeError, NoValidConnectionsError):
            logger.info('reboot_stb: Failed to open SSH, trying over debug...')
            self.send_commands_over_debug('reboot')

        logger.info('reboot_stb: Waiting for STB to restart.....')
        time.sleep(30)
        pingtimetaken = self.ping_stb_until_alive(timeout=pingtimeout)
        if nocheck=="1":
            logger.debug('reboot_stb: STB responded in: "%ss"' % (pingtimetaken))
            logger.info('reboot_stb: STB responded in: "%ss"' % (pingtimetaken))
            logger.debug('reboot_stb: waiting for 30 seconds before commencing')
            timer = time.time() - start
            if restart_ssh:
                logger.info('reboot_stb: Reopening SSH connection')
                # self.login_and_keep_ssh_open()
                self._robust_ssh_login_and_keep_ssh_open()

            if restart_debug:
                self.enable_console(extraINPkey=True)
                self.start_logread()

            if restart_stats:
                logger.info('reboot_stb: Restarting stats capture')

                self.stats_collection.restart_stats_after_reboot()
            self._stateflags = {}
            logger.info('reboot_stb: STB rebooted in: %ss' % (timer))
            return str(int(timer))

        elif nocheck=="2":
            logger.debug('reboot_stb: STB responded in: %ss' % (pingtimetaken))
            logger.info('reboot_stb: STB responded in: %ss' % (pingtimetaken))
            timer = time.time() - start
            self._stateflags = {}
            logger.info('reboot_stb: STB rebooted in: %ss' % (timer))
            return str(int(timer))

        else:

            time.sleep(1)
            pingtimetaken=int(pingtimetaken)
            print pingtimetaken
            logger.debug('reboot_stb: STB responded in: "%ss"' % (pingtimetaken))
            logger.debug('reboot_stb: waiting for 30 seconds before commencing')

            time.sleep(90)
            self._builtin.wait_until_keyword_succeeds(name='check_for_browser', retry_interval='1s', timeout='3minutes')
            self.check_for_browser()
            pingtimetaken=int(pingtimetaken)
            print pingtimetaken
            timetaken= pingtimetaken + 30
            timer = time.time() - start
            reboot_time = timer
            logger.debug('reboot_stb: STB responded in: "%ss"' % (timetaken))
            logger.info('reboot_stb: Total reboot time: "%ss"' % (reboot_time))
            print reboot_time

        # Now restart all the stuff that was stopped
            if restart_ssh:
                logger.info('reboot_stb: Reopening SSH connection')
                #self.login_and_keep_ssh_open()
                self._robust_ssh_login_and_keep_ssh_open()

            if restart_debug:
                self.enable_console(extraINPkey=True)
                self.start_logread()

            if restart_stats:
                logger.info('reboot_stb: Restarting stats capture')

                self.stats_collection.restart_stats_after_reboot()

                self._stateflags = {}

        # Time to ping + time slept accross the key word
            return str(int(reboot_time))

    def reboot_stb_twice(self, pingtimeout="2 minutes"):
        """     Reboot the STB twice to apply an entone boot ini setting

        The named parameter pingtimeout is passed directly through to the
        reboot_stb method

        Examples:
        | UUT.Reboot Stb Twice      |                           |
        | UUT.Reboot Stb Twice      | pingtimeout="5 minutes"   |
        """

        logger.debug('reboot_stb_twice: called')

        self.reboot_stb(pingtimeout=pingtimeout)
        self.reboot_stb(pingtimeout=pingtimeout)


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

        restart_stats = False
        restart_ssh = False
        restart_debug = False

        powerip = self._powerip_port.split(":")[0]
        powerport = self._powerip_port.split(":")[1]

        if self._powerip_type == "netbooter":
            try:
                self._ping(powerip)
            except PingResponseError:
                logger.warn("No response from powerip device on ip '" + powerip + "'.  Unable to power cycle STB")
                return

        if (self._keep_ssh_open) and (self.ssh_conn != None):
            restart_ssh = True

        if self.stats_collection != None:
            restart_stats = True
            self.stats_collection.pause_stats_for_reboot()

        if self._logread_is_running and (self._debug != None):
            # No need to stop logread process, it will die on reboot
            self._logread_is_running = False
            restart_debug = True

        # Power cycle box

        logger.info("Power cycling STB now....")

        if self._powerip_type == "netbooter":
            self._power_ip_netbooter(powerip, powerport, 0)
            time.sleep(utils.timestr_to_secs(downtime))
            self._power_ip_netbooter(powerip, powerport, 1)
        elif self._powerip_type == "usb-rly16":
            self._power_ip_usbrly16(powerip, powerport, 0)
            time.sleep(utils.timestr_to_secs(downtime))
            self._power_ip_usbrly16(powerip, powerport, 1)

        logger.info("Waiting for STB to restart (%s)" % (waitfor))
        sleeptime = utils.timestr_to_secs(waitfor)
        time.sleep(sleeptime)
        self.ping_stb_until_alive(timeout=sleeptime)


        # Now restart all the stuff that was stopped
        if restart_ssh:
            logger.info('Reopening SSH connection')
            #self.login_and_keep_ssh_open()
            self._robust_ssh_login_and_keep_ssh_open()

        if restart_stats:
            logger.info('Restarting stats capture')
            self.stats_collection.restart_stats_after_reboot()

        if restart_debug:
            logger.info('Restarting logread process')
            self.start_logread()

        self._stateflags = {}

    def quick_power_cycle(self, downtime="1 second"):
        """  Quick Power cycle of the STB that waits for nothing.

        You will need to handle closing of telnet connects and stats collection in the script (or it will fail)

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

        powerip = self._powerip_port.split(":")[0]
        powerport = self._powerip_port.split(":")[1]


        if self._powerip_type == "netbooter":
            try:
                self._ping(powerip)
            except:
                logger.warn("No response from powerip device on ip '" + powerip + "'.  Unable to power cycle STB")
                return

        # Power cycle box
        logger.info("Power cycling STB now....")
        if self._powerip_type == "netbooter":


            self._power_ip_netbooter(powerip, powerport, 0)
            time.sleep(utils.timestr_to_secs(downtime))
            self._power_ip_netbooter(powerip, powerport, 1)

        elif self._powerip_type == "usb-rly16":
            self._power_ip_usbrly16(powerip, powerport, 0)
            time.sleep(utils.timestr_to_secs(downtime))
            self._power_ip_usbrly16(powerip, powerport, 1)


    def _power_ip_usbrly16(self, powerip, powerport, state, max_attempts=3):
        try:
            con = serial.Serial(port=powerip, baudrate=19200, bytesize=8, parity='N', stopbits=2)
        except OSError:
            raise ESTBError("Unable to contact powerip device on '%s'" % powerip)

        powerport = int(powerport)


        if isinstance(state, int):
            state = 'on' if(state==1) else 'off'

        state = state.lower()

        attempts = 1
        successful = False

        logger.debug("powerip=%s powerport=%d" % (powerip, powerport))

        while attempts <= max_attempts:
            try:
                if (powerport != 0):
                    currentstate = self._power_ip_usbrly16_read(con, powerport)

                    if state == currentstate:
                        logger.debug("Not setting power as it is already '%s'" % state)
                    else:
                        con.write(USB_RLY16[state][powerport])
                        time.sleep(0.5)
                        currentstate = self._power_ip_usbrly16_read(con, powerport)
                        if state != currentstate:
                            raise ESTBError("Unable to set power state!")
                else:
                    con.write(USB_RLY16[state][0])
                    time.sleep(0.5)
                successful = True
                break
            except ESTBError:
                logger.debug("Failed attempt #%s at power cycling setting relay, retrying" % str(attempts))
                time.sleep(random.randint(10,100)/100)
                attempts += 1

        if not successful:
            raise ESTBError("Unable to set power state!")


        con.close()


    def _power_ip_usbrly16_read(self, powerip, powerport, max_attempts=10):
        # Open the port.  If the 'powerip' is a Serial instance assume it is open and use that, otherwise create one

        con = None
        keepopen = False


        if isinstance(powerip, serial.Serial):
            con = powerip
            keepopen = True
        else:
            con = serial.Serial(port=powerip, baudrate=19200, bytesize=8, parity='N', stopbits=2)

        con.write(USB_RLY16['read'])

        time.sleep(0.1)

        statehex = con.read(con.inWaiting())

        if not keepopen:
            con.close()

        try:
            state = struct.unpack('<B', statehex)[0]
        except:
            logger.debug("_power_ip_usbrly16_read: Power relay read issue? May require Robot PC reboot to fix!")
            raise ESTBError()

        if powerport == 0:
            return state
        else:
            powerport = powerport -1

            if (state) & 2**powerport:
                return 'on'
            else:
                return 'off'




    def _power_ip_netbooter(self, powerip, powerport, state, max_attempts=3):
        if state == self._power_ip_netbooter_read(powerip, powerport, max_attempts):
            logger.info("Power IP already in state %s.  No action" % state)
        else:
            self._os.run_and_return_rc('curl --user admin:admin http://' + powerip + '/cmd.cgi?rly=' + powerport + ' >/dev/null 2>&1')
            counter = 0
            while int(state) != int(self._power_ip_netbooter_read(powerip, powerport, max_attempts)):
                counter = counter + 1
                if counter > max_attempts:
                    raise ESTBError("Could not set rly to state %s on powerip %s" % (state, powerip))
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
                raise ESTBError("Unable to ping powerip on %s" % powerip)
            else:
                logger.info("Ping powerip failed... retrying")
                time.sleep(0.5)

        counter = 0

        try:
            root = ET.fromstring(self._os.run('curl -s --user admin:admin http://%s/status.xml' % powerip))
        except Exception as inst:
            logger.warn('Power Ip Error: %s' % (inst))
            raise ESTBError("Unable to read status of powerip on %s" % powerip)

        return root.find('rly%s' % powerport).text

    # Fakekey methods (public)
    def send_fakekey(self, key, pause=None, repeatcount=1):
        """  Sends a fakekey code converted to hnr

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

    def list_hnrkeys(self):
        """ TODO: HELP """
        if self._fakekey is None:
            self._open_fakekey()

        return self._fakekey._cmd_array.values()

    def send_hnrkey(self, key, pause=None, repeatcount=1, hold=None):
        """  Sends a key code, using Pyhnr (Enable stack)

        If a keycode is sent as a keydown only, this state will persist until the
        corresponding keyup is sent later.  This is how you achieve key holds (for
        operations such as CTRL+A).

        Manitory argument:
        - keycode   - The key code as mapped in the active mapping file

        Optional arguments:
        - pause     - Provides a pause in thread execution immediately after sending
        - repeatcount   - Send the same keycode (and pause, if appropriate) multiple times as if pressed multiple times
        - hold     - A robot time value indicating how long to hold the key down for, with repeat rate set with estb property hnr_repeat_rate

        NOTE: Deprecated in favour of `Send Key`

        Examples:
        | Send hnrkey  | MENU          |                   |               |
        | Send hnrkey  | ${mykey}      | pause=1 second    |               |
        | Send hnrkey  | ${mykey}      | pause=0.5 second  | repeatcount=3 |
        | Send hnrkey  | ${mykey}      | hold=10 seconds   |               |
        """

        try:
            self._open_fakekey()
            self._fakekey.send_hnrkey(key, pause, repeatcount, hold)
        except LookupError as l:
            logger.warn(l.__str__())
            raise l

        except Exception as e:
            if "Broken pipe" in e.__str__():
                logger.warn("HNRKey SSH Tunnel broken pipe...   re-opening")

                self._fakekey.close()
                try:
                    self._open_fakekey()
                    self._fakekey.send_hnrkey(key, pause, repeatcount, hold)
                except Exception as e:
                    raise e
            elif e.__str__() != "Execution terminated by signal":
                logger.warn("Unable to connect to UDB hnr on STB.")
                raise e

    def send_hnrkeys(self, *codes, **kwargs):
        """
        Send a list of HNRKeys
        :param codes: any number of keys
        :param kwargs: pause: set the pause time between key presses

        NOTE: This is deprecated in favour of `Send Keys`

        Example:
        | UUT.Send_HNRKeys	|

        """


        if 'pause' in kwargs:
            pause = kwargs['pause']
        else:
            pause = "0.5 seconds"

        pause = utils.timestr_to_secs(pause)
        for key in codes:
            if isinstance(key, types.ListType):
                for subkey in key:
                    self.send_hnrkey(subkey, pause)
            else:
                self.send_hnrkey(key, pause)




    def run_fakekey_script(self, filename, repeats=-1, timeout=None):
        """  Runs a standard fakekey script, converting to hnr

        Compatible with original format fakekey scripts containing either keycodes,
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

    # Fakekey methods (private) Adapted for Enable
    def _open_fakekey(self):
        """     Opens a connection for sending spoofed IR commands via HNR
        """

        try:
            if self._fakekey._connected:

                return
            else:

                self._fakekey._connect()
        except AttributeError:

            self._fakekey = HNRKey.HNRKey(ipaddress=self.get_interface_attribute(),
                                      #port=self._fakekey_port,
                                      hnr_repeat_rate=self._hnr_repeat_rate,
                                      ssh_tunnel_user=self._ssh_tunnel_user,
                                      ssh_tunnel_password=self._ssh_tunnel_password)

    def hnr_connect(self):
        """ Explicitly opens a HNR connection

        Best used when you need to ensure SSH tunneling happens in advance of key presses as
        the tunneling process my take a few seconds

        Example:
        | ESTB.HNR Connect|


        """
        max_attempts = 5
        attempts = 1
        while attempts <= max_attempts:
            try:
                self._open_fakekey()
                self._fakekey._connect()
            except HnrError:
                logger.debug("Hnr Connect FAIL %d of %d attempts!" % (attempts,max_attempts))
            else:
                logger.debug("SUCCESS: Hnr Connect after %d of %d attempts!" % (attempts, max_attempts))
                break

            time.sleep(5)
            attempts = attempts + 1

        if attempts > max_attempts:
            raise ESTBError("FAIL: Hnr Connect FAILED, exiting")

        # Original code below.
        #self._open_fakekey()
        #self._fakekey._connect()


    def hnr_ssh_tunnel_config(self, user, password, interface = -1):
        """ Set hnr reverse ssh tunnel user name and password

        Used to set user name and password for hnr ssh tunnel

        Example:
        | ESTB.HNR ssh tunnel config | jenkins | entonehd |
        | ESTB.HNR ssh tunnel config | jenkins | entonehd | 1 |

        """
        self._ssh_tunnel_user = user
        self._ssh_tunnel_password = password
        if interface != -1:
            self.set_active_interface(interface)
            self._fakekey = None


    # STATS methods (public)
    def stop_stb_statistics(self):
        """  Stops gathering STB statistics and removes the collection thread

        If you need to re-start the stats collection, then you should call
        ESTB.Capture Stb Statistics

        NOTE: This key word joins the stats collection thread and it will
              pause execution until the stats collection loop exits

        Example:
        | ESTB.Stop stb statistics   |

        """
        self.stats_collection.stop_stats_collection()

        # Join the Thread until the worker method loop exits
        self.stats_collection.join()

        del self.stats_collection

        self.stats_collection = None

    def capture_stb_statistics(self, mem=True, cpu=True, wifi=False,
                             iostat=False, hdd=False, interval="10 seconds"):
        """     Starts gathering STB statistics

        By default this will start gathering CPU IDLE and FREE MEMORY.
        Optionally wifi signal stats can also be collected.

        Log files are stored in the output directory with the naming convention:-
        ${SUITENAME}_${STB_SHORTNAME}_{mem|cpu|wifi}.log
        (This makes the scope of a logfile suite based)

        Optional arguments:
        - mem={True|False}  - Capture 'free memory' stats (defaults to True)
        - cpu={True|False}  - Capture 'cpu idle' stats (defaults to True)
        - wifi={True|False} - Capture 'wifi signal' stats (defaults to False)
        - iostat={True|False} - Capture HDD stats from the output of iostat
        - hdd={True|False} - Capture HDD stats from the output of df
        - interval      - Set the time between captures (default 10 seconds)

        Examples:
        | Capture STB Statistics    |                |             | # Start capturing CPU and MEM at 10 second intervals  |
        | Capture STB Statistics    | mem=False      | wifi=True   | # Start capturing CPU and WIFI at 10 second intervals |

        """

        logger.info('Starting stats collection')

        if self.stats_collection != None:
            logger.warn('Cannot start stats collection when already running!')
            return
        else:
            self.stats_collection = StatCollection.StatCollection(self)

            self.stats_collection.set_stats_interval(interval)

            self.stats_collection.start_stats_collection(mem=mem, cpu=cpu,
                                                    wifi=wifi, iostat=iostat, hdd=hdd)

        return

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

    def capture_debug(self, debugport="default", suffix=None, dieonfail=True, compressed=False, setdebugpassword='', tryalternativepasswords=False, suppresslogread=False):
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

        Part of capturing debug on an Enable build involves lauching the logread command.  Doing this requires
        logging in to the command line over debug which will require the root password.
        That password can be set here (using setdebugpassword) or defined in the STB definition file.

        If you are not sure what the password needs to be (for example, during AVS runs where the previous build
        may have a different password to the one you plan to flash on) you can use the tryalternativepasswords flag
        which will ignore if the set password is wrong and try all the ones known to the Debug library.

        It is also possibleto suppress the standard call to start log read (if you are only interested in debug capture of boot)

        Examples:
        | Capture debug |                                        |
        | Capture debug | debugport=/dev/ttyUSB0                 |
        | Capture debug | suffix=UUT                             |
        | Capture debug | dieonfail=${False}                     |
        | Capture debug | compressed=${True}                     |
        | Capture debug | tryalternativepasswords=${True}        |
        | Capture debug | suppresslogread=${True}                |

        NOTE:  The current user MUST have access rights to serial ports!  To acheive this
        add the user to the 'dialout' group using:-

        sudo usermod -a -G dialout USERNAME

        NOTE: It is good practice to mark the debug log when starting a new test case, using the
        `Debug marker` keyword.
        """

        if setdebugpassword != '':
            # Need to perminantly amend the debug_password
            self._debug_password = setdebugpassword

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
                raise ESTBError("Debug capture failed")
            else:
                return
        try:
            self._debug = Debug.Debug(appendsuffix=suffix,
                                      password=self._debug_password,
                                      tryalternativepasswords=tryalternativepasswords)

            self._debug.open_connection(commport=self._debugport,
                                        compressed=compressed,
                                        prompt=self._debugprompt,
                                        prompt_regex=self._debugprompt_regex)

            logger.info("Serial debug capture %sstarted on '%s'" % (comp, self._debugport))
        except Debug.DebugError as err:
            logger.warn("Unable to capture debug on port '%s'. %s" %
                         (self._debugport, err.__str__()))
            if dieonfail:
                raise ESTBError("Debug capture failed")
        except Exception as err:
            logger.warn("Unable to capture debug on port '%s'. Check it exists and you have permission to use it. %s"
                         % (self._debugport, err.__str__()))
            if dieonfail:
                raise ESTBError("Debug capture failed")

        if not suppresslogread:
            self.start_logread()


    def start_logread(self, raise_on_fail=True):
        """     Starts logread -f on the serial console to capture debug
        """

        try:
            logger.info('start_logread: starting "logread -f &"')
            self.stop_logread()
            self.send_command_over_debug('logread -f &')
            self._logread_is_running = True
            return True
        except Debug.DebugError:
            if raise_on_fail:
                self.close_all()
                raise Debug.DebugError('Failed to start logread -f')
            else:
                return False


    def get_property(self, property):
        # type: (object) -> object
        """  Get a STB property at runtime

        Note: To get interface attributes you must use `Get Interface Attribute`

        Examples:
        | ${serial}=    | Get property  | serialnumber  |
        | ${family}=    | Get property  | family        |

        """
        property = '_' + property.lower()
        try:
            return getattr(self, property)
        except AttributeError:
            return None


    def set_property(self, property, value):
        """  Set a STB property at runtime

        Note: You can not set individual interface attributes during runtime, only
        add a new interface with `Create interface`

        Available properties (and their defaults) are:-

        === STB properties ===
        - shortname         = 'stb_unknown'
        - serialnumber      = None
        - family            = 'HDB72'
        - active_interface  = None          # Note becomes 0 when first is added

        === SSH Properties ===
        - ssh_user          = 'root'
        - ssh_newline       = '\r\n'
        - ssh_keyfile       = './resources/keys/entone_ssh_system_rsa_20130306_000001.openssh_private'
        - ssh_login_prompt  = ' #'
        - ssh_cmd_prompt    = '(\/.* #|~ #)'
        - keep_ssh_open     = False

        === Debug properties ===
        - debugport = debugport

        === Fakekey properties ===
        - fakekey_port        = 894
        - fakekey_keymapfile  = None
        - hnr_repear_rate     = '0.12'

        === Power IP port settings ===
        - powerip_port      = None
        - powerip_type      = "netbooter"

        === INI Settings ===
        - ini_path          = None

        Examples:
        | Set property  | serialnumber  | J12121991829812   |
        | Set property  | family        | ${family}         |

        """
        property = '_' + property
        setattr(self, property, value)

    def check_if_powerip_supported(self):
        if self._powerip_port is None:
            return False
        else:
            return True


    def close_all_but_debug(self):
        """ Closes all open connectons except debug
        Best used when upgrading or rebooting

        Example:
        | Close all but debug   |
        """
        try:
            self.stats_collection.pause_stats_for_reboot()
        except:
            pass

        try:
            self.close_ssh_connection()
        except:
            pass

        try:
            self._fakekey.close()
        except:
            pass


    def close_all(self):
        """ Closes all open connectons including debug, telnet, stats and fakekey

        Example:
        | ESTB.Close all |
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

    def get_interface_attribute(self, attributename='ip', interface=-1):
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

    def enable_console(self,extraINPkey=False):
        """     use HNRKey to enable the console output

        To remove the dependency on the INI setting 'HDxxx_BROWSER_DISABLE_VIRTUAL_KEYBOARD=1' (see S725X-4459)
        the parameter 'extraINPkey' should be set to ${True} for browser builds e.g. ETV, opera4.

        Examples:
        |  Enable Console  |                     | # Use default sequence for non-browser APPs e.g. MVN                        |
        |  Enable Console  | extraINPkey=${True} | # Use extra INPUT key in sequence for ETV browser builds including opera4   |

        """


        """
        ip_address = self.get_interface_attribute('ip')
        ssh_user = self.get_property('ssh_tunnel_user')
        ssh_pass = self.get_property('ssh_tunnel_password')

        max_attempts = 20
        attempts = 1
        while attempts <= max_attempts:
            proc = subprocess.Popen(['ping', '-c', '1', ip_address],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)

            # Wait for ping to complete
            proc.communicate()

            if proc.returncode != 0:
                attempts = attempts + 1
            else:
                if attempts == 1:
                    attemptStr = "attempt"
                else:
                    attemptStr = "attempts"
                print("SUCCESS: Contact made with IP Address after %d %s!") % (attempts, attemptStr)
                break

        if attempts > max_attempts:
            raise ESTBError("FAIL: Unable to contact provided IP Address, exiting")

        # conn = HNRKey(ipaddress=ip_address)
        conn = HNRKey(ipaddress=ip_address, ssh_tunnel_user=ssh_user, ssh_tunnel_password=ssh_pass)

        key_presses = ['INPUT', '7', '3', '6', '6', '8', '3']

        for key in key_presses:
            self.send_key(key)
            time.sleep(0.1)
        """

        if extraINPkey:
            # For browser APPs e.g. ETV, opera4.
            key_presses = ['INPUT', 'INPUT', '7', '3', '6', '6', '8', '3']
        else:
            # For MVN APPs.
            key_presses = ['INPUT', '7', '3', '6', '6', '8', '3']

        for key in key_presses:
            self.send_key(key)
            time.sleep(0.1)

        # How do I check it worked?


    def login_and_keep_ssh_open(self, interface=-1):
        """     Login to the STB via SSH and maintain the SSH connection
        """

        stb_ip = self._get_iface_ip(interface)

        self._ssh_login(stb_ip)

        self._keep_ssh_open = True

    def set_ssh_timeout(self, timeout):
        """     Set the command timeout over the SSH connection

        NOTE: This will only work when you open a new SSH connection is
        opened after the timeout is set. If an SSH session is kept open
        using "Login And Keep Ssh Open", it will not be applied to the
        active session

        Examples:
        | ESTB.Set Ssh Timeout  | 15 seconds    |
        | ESTB.Set Ssh Timeout  | 2 minutes     |
        | ESTB.Set Ssh Timeout  | 2 minutes     |
        """
        logger.debug('set_ssh_timeout: set to: %s' % (timeout))

        self._ssh_timeout = timeout

    def _get_iface_ip(self, interface_index):
        if interface_index == -1:
            return self.get_interface_attribute()
        else:
            return self.get_interface_attribute('ip', interface_index)

    def send_command_and_return_output(self, command, interface=-1):
        """   Send ssh command and return output

        Sends a single command over SSH and returns the output received until the next prompt

        Examples:
        | ${ret}=   | Send command and return output    | ls /tmp           |                   | # This sends the command to the active interface                          |
        | ${ret}=   | Send command and return output    | cat /etc/hosts    | ${wifi_interface} | # Sends command to interface index saved in ${wifi_interface} variable    |

        """
        stb_ip = self._get_iface_ip(interface)

        output = self._send_ssh_command(command)
        logger.debug("output = %s" % output)

        return output

    def send_commands(self, *commands):
        """     Send a list of commands over SSH on the active interface

        returns a list of return codes

        Examples:
        | Send commands | ls /mnt/nv    | cp log.temp / | rm log.temp       |
        | @{rcodes}=    | Send commands | cd /root      | mv log.txt /home  |
        """
        close_ssh = False

        if not self._keep_ssh_open:
            # If we don't already have an open SSH connection, create one and leave
            #  it open, and set a flag to shut it down once the commands have run
            
            # ssh login with repeat until success or max attempts exceeded.
            #self.login_and_keep_ssh_open()
            self._robust_ssh_login_and_keep_ssh_open()
            close_ssh = True

        ret = []

        for command in commands:
            self._send_ssh_command(command)
            ret_code = self._send_ssh_command('echo $?')

            # Strip the integer from the returned string
            ret.append(int(ret_code))

        if close_ssh:
            self.close_ssh_connection()

        return ret

    def record_pvr_asset_and_check_level(self, url, rectime, level_event='Low'):
        """   Records a PVR asset for given url and checks for a disk space level event

        RELIES on streamerctl, NOT SUPPORTED IN ENABLE STACK
        Will need to be ported to use the SSH connection when the time comes


        returns True if disk space level detected otherwise False


        Examples:
        | ${warnseen}= | record pvr asset | igmp://239.255.250.22:2002 | 600 |                    |
        | ${warnseen}= | record pvr asset | igmp://239.255.250.22:2002 | 600 | level_event='Low'  |
        | ${fullseen}= | record pvr asset | igmp://239.255.250.22:2002 | 900 | level_event='Full' |
        """
        self._enable_warn()
        return

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
        """     Send command and return output and rc

        Sends a single command over Telnet and returns the output received until the next prompt, and the return code

        Examples:
        | ${ret}    | ${rc}=    | Send command and return output and rc | ls /tmp           |                   |
        | ${ret}    | ${rc}=    | Send command and return output and rc | cat /etc/hosts    | ${wifi_interface} |
        """

        close_ssh = False

        if not self._keep_ssh_open:
            close_ssh = True
            #self.login_and_keep_ssh_open()
            self._robust_ssh_login_and_keep_ssh_open()

        output = self._send_ssh_command(command, interface=interface)

        ret_code = self._send_ssh_command('echo $?')
        ret_code = ret_code.replace('\r\n', '')
        ret_code = ret_code.replace(' ', '')

        ip = self._get_iface_ip(interface)

        if close_ssh:
            self.close_ssh_connection()

        return output, ret_code

    def get_browser_pid(self):
        """     Gets the Browser PID

        if the browser is running the PID of the browser is returned,
        else 0 is returned


        Examples:
        | ${browser_pid}= | ESTB.Get Browser Pid |
        """

        brow_pid = self._send_ssh_command('pidof browser')

        # Ensure we are just returning the pid as an integer
        try:
            ret = [int(s) for s in brow_pid.split() if s.isdigit()][0]
        except IndexError:
            ret = 0

        return ret

    def take_vnc_snapshot_image(self, img_name=None):
        """     Take a jpg snapshot the STB VNC graphics plane

        This keyword will by default use a timestamp to uniquely identify the
        snapshot, however an optional parameter can be passed to add a name
        to the snapshot image name.

        Examples:
        | ${img_path_1}=  | ESTB.Take Vnc Snapshot Image  | browser_loaded |
        | ${img_path_2}=  | ESTB.Take Vnc Snapshot Image  |                |
        """

        # Get the debug path, and cut the debug file off the path
        dbg_path = self.get_debug_filepath()
        out_dir = '/'.join(dbg_path.split('/')[:-1])

        time_stamp = time.strftime("%Y%m%d_%H-%M-%S")

        if img_name:
            path = '%s/snapshot_%s_%s.jpg' % (out_dir, time_stamp, img_name)
        else:
            path = '%s/snapshot_%s.jpg' % (out_dir, time_stamp)

        logger.debug('outputting vnc snap to %s' % (path))

        cmd = ['vncsnapshot', '-passwd', './resources/keys/vncpasswd',
               '%s::15900' % (self.get_interface_attribute('ip')), path]

        # Make the command by joining the arguments list
        snp_rc, snp_out = self._os.run_and_return_rc_and_output(' '.join(cmd))

        logger.debug('vncsnapshot rc     %s' % (snp_rc))
        logger.debug('vncsnapshot stdout %s' % (snp_out))

        if snp_rc == 0:
            logger.debug('snapshot was successful')
        else:
            logger.warn('VNC snapshot failed with rc: %s' % (snp_rc))

        return path

    def get_dhcp_init_args(self):
        """     Get the required arguments for initialising the DHCP library

        This function returns a list of attributes of the STB object which are
        used in initialising the DHCP server library, it returns a 3 element
        list which consists of the following data:
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

    def check_igmp_stream(self, igmp_url, interface='eth0'):
        """     Check to see if an IGMP group or UDP is joined on the STB, by the
        checking if there is packet info found in tcpdump

        Examples:
        | ${ret_igmp}= | ESTB.Check Igmp Stream | igmp://233.22.133.1:8110 |
        | ${ret_igmp}= | ESTB.Check Igmp Stream | udp://233.22.133.1:8110 |
        """

        self.send_command_over_debug(
                'tcpdump -i %s > /tmp/igmp_check' % interface
                , False, "5 seconds")
        ip = re.sub(".*://", "", igmp_url)
        ip = re.sub(":.*", "", ip)
        port = re.sub(".*://.*:", "", igmp_url)
        command = "if grep -q %s.%s /tmp/igmp_check; then echo True; \
                else echo False; fi" % (ip, port)
        ret = self.send_command_over_debug_and_return_output(command, "15 seconds")
        ret = re.sub("if.*True", "", ret)
        logger.debug(ret)
        if "True" in ret:
            return True
        else:
            if not "False" in ret:
                logger.debug("Failed to send command.")
            return False

    def check_igmp_stream_via_SSH(self, igmp_url):
        """     Check to see if an IGMP group or UDP is joined on the STB, by quering tcpdump via SSH on  STB and
                comparing the returned info with

                Examples:
                | ${ret_igmp}= | ESTB.Check Igmp Stream | igmp://233.22.133.1:8110 |
                | ${ret_igmp}= | ESTB.Check Igmp Stream | udp://233.22.133.1:8110 |
                """

        # Use 'send_command_and_return_output_and_rc' to get a return code.
        cmd1 = "tcpdump -i eth0 -c 1024 > /tmp/igmp_check &"
        ret,rc = self.send_command_and_return_output_and_rc(cmd1)

        # Occasionally rc contains both the command status and a second line(?) with '[1]+  Done' due to '&' in command line.
        # To ensure we are only checking against the return code need to get the first char of the overall rc string!!!
        logger.debug("check_igmp_stream_via_SSH: rc=%s" % rc)
        rcode = rc[0]
        logger.debug("check_igmp_stream_via_SSH: rcode=%s" % rcode)
        if rcode != '0':
            logger.warn("check_igmp_stream_via_SSH: tcpdump command failed!")
            return False
        time.sleep(10)

        # DO NOT grep for 'dvbstreamer' as this is too specfic and does NOT work for e.g. MVN CH691!!
        ip = re.sub(":.*", "", re.sub(".*://", "", igmp_url))
        ip = re.sub(":.*", "", ip)
        port = re.sub(".*://.*:", "", igmp_url)
        logger.debug("ip=%s port=%s" % (ip, port))
        temp = ip.split(".")
        #Use: grep -E \"\> <ip.port>" -m 1 /tmp/igmp_check
        grepCMD =  "grep -E \"> " + temp[0] + "\." + temp[1] + "\." + temp[2] + "\." + temp[3] + "\." + port + "\" -m 1 /tmp/igmp_check"
        logger.debug("grepCMD=%s" % grepCMD)
        impg_stream_message,rc = self.send_command_and_return_output_and_rc(grepCMD)
        # Next line incase rc contains more than just the return code number. Refer to earlier usage.
        rcode = rc[0]
        if rcode != '0':
            logger.warn("check_igmp_stream_via_SSH: grep for '<ip addr>.<port>' failed!")
            dumpFile = self.send_command_and_return_output("head -n 100 /tmp/igmp_check")
            logger.debug("check_igmp_stream_via_SSH: tcpdump output is:\n\n%s\n\n" % dumpFile)
            return False

        # Will get here if grep command is satisfied correctly.
        # Log the output from the grep command for debug purposes so we can see what stream it found.
        logger.debug("check_igmp_stream_via_SSH: grep output: %s" % impg_stream_message)

        rest = str(impg_stream_message[int(impg_stream_message.find("> "))+2 : int(impg_stream_message.find(": "))])
        igmp_address = rest.split(".")
        portNo = igmp_address.pop()
        IPAddress = ".".join(igmp_address)
        logger.debug("".join(["igmp stream detected with address: ",IPAddress, " and port: ",portNo]))

        ip = re.sub(":.*", "", re.sub(".*://", "", igmp_url))
        ip = re.sub(":.*", "", ip)
        port = re.sub(".*://.*:", "", igmp_url)

        if IPAddress == ip and portNo == port:
            return True
        else:
            logger.warn("Detected igmp stream is NOT the expected one!")
            return False


    def find_igmp_stream(self, igmp_url, interface=-1):
        """     Check to see if an IGMP group is joined on the STB, by the
        output of /proc/net/igmp

        NOTE: Please use check_igmp_stream instead of find_igmp_stream for Enable

        The igmp_url parameter can be passed as an igmp:// url, a udp:// url,
        or a plain igmp address group. This can be used to determine if a
        group has been joined correctly, and that it is correctly left, when
        the STB is put into standby, for example.

        Examples:
        | ${ret_igmp}= | ESTB.Find Igmp Stream | igmp://239.255.250.1:11111 |
        | ${ret_udp}=  | ESTB.Find Igmp Stream | udp://239.255.250.1:11111  |
        | ${ret_bare}= | ESTB.Find Igmp Stream | 239.225.250.1              |
        """

        try:
            igmp_address = igmp_url.split('://')[1].split(':')[0]
        except IndexError:
            igmp_address = igmp_url

        addr_parts = igmp_address.split('.')
        addr_parts.reverse()

        igmp_hex = ''
        for part in addr_parts:
            igmp_hex += '{0:02x}'.format(int(part))

        igmp_hex = igmp_hex.upper()

        logger.debug('find_igmp_stream: looking for hex {0}'.format(igmp_hex))

        proc_igmp = self.send_command_and_return_output('cat /proc/net/igmp',
                                                    interface=interface)

        # 8 char HEX value, which doesn't start with a colon
        hexa_regex = r'(?<!:)([0-9a-fA-F]{8})'

        joined_groups = re.findall(hexa_regex, proc_igmp)

        logger.debug('Found IGMP groups: {}'.format(str(joined_groups)))

        return igmp_hex in joined_groups

    def get_qoemon_value(self, value="VPTS", videowindow="0"):
        """     NEVER WILL BE SUPPORTED IN ESTB - To be removed
        AmiNET configuration keyword, stub left for compatibility
        of soak test scripts with the enable stack
        """
        self._enable_warn()
        return


    def get_snapshot(self, interface=-1, saveaslog=False):
        """     WILL NEVER BE SUPPORTED IN ESTB

        AmiNET configuration keyword, stub left for compatibility
        of soak test scripts with the enable stack
        """
        self._enable_warn()
        return

    def reboot_after_libconfig_set(self, value):
        """     WILL NEVER BE SUPPORTED IN ESTB

        AmiNET configuration keyword, stub left for compatibility
        of soak test scripts with the enable stack
        """
        self._enable_warn()
        return

    def send_libconfig_set_commands(self, *commands):
        """     WILL NEVER BE SUPPORTED IN ESTB
        AmiNET configuration keyword, stub left for compatibility
        of soak test scripts with the enable stack
        """
        self._enable_warn()
        return

    def send_libconfig_get_command(self, command):
        """     WILL NEVER BE SUPPORTED IN ESTB

        AmiNET configuration keyword, stub left for compatibility
        of soak test scripts with the enable stack
        """
        self._enable_warn()
        return

    def send_libconfig_dump_command(self, group=""):
        """     WILL NEVER BE SUPPORTED IN ESTB

        AmiNET configuration keyword, stub left for compatibility
        of soak test scripts with the enable stack
        """
        self._enable_warn()
        return

    def login_and_keep_telnet_open(self):
        """     WILL NEVER BE SUPPORTED IN ESTB

        AmiNET configuration keyword, stub left for compatibility
        of soak test scripts with the enable stack
        """
        self._enable_warn()
        return

    def _enable_warn(self):
        cur = inspect.currentframe()
        call = inspect.getouterframes(cur,2)[1][3]
        keyword = call.replace('_',' ').capitalize()
        logger.warn("Keyword '%s' is not supported with the enable stack" % keyword)

    def check_ETV_is_running(self):
        """

        This keyword checks that ETV is running.
        It returns a count of processes containing 'EntoneWebEngine'. This must be 1 or more.

        Example:
        | ${ret} | ${rc}= | ESTB.check_ETV_is_running |

        """

        ret,rc = self.send_command_and_return_output_and_rc("top -n1 > /tmp/x.txt &")
        if rc[0] != '0':
            logger.warn("check_ETV_is_running: 'top' command failed!")
            ret=int(0)
            return ret,rc[0]
        time.sleep(10)

        ret,rc = self.send_command_and_return_output_and_rc("grep -c 'EntoneWebEngine' /tmp/x.txt")
        if rc[0] != '0':
            logger.warn("check_ETV_is_running: 'grep' command failed!")
            psOutput = self.send_command_and_return_output("cat /tmp/x.txt")
            logger.debug("check_ETV_is_running: 'ps' command output:\n%s" %  psOutput)
            ret=int(0)
            return ret,rc[0]

        # Commands worked ok.
        ret=int(ret)
        return ret,rc

    def check_MVN_is_running(self):
        """

        This keyword checks that MVN is running.
        It returns a count of processes containing 'think'. This must be 1 or more.

        Example:
        | ${ret} | ${rc}= | ESTB.check_MVN_is_running |

        """

        ret,rc = self.send_command_and_return_output_and_rc("top -n1 > /tmp/x.txt &")
        if rc[0] != '0':
            logger.warn("check_MVN_is_running: 'top' command failed!")
            ret=int(0)
            return ret,rc[0]
        time.sleep(10)

        ret,rc = self.send_command_and_return_output_and_rc("grep -c 'think' /tmp/x.txt")
        if rc[0] != '0':
            logger.warn("check_MVN_is_running: 'grep' command failed!")
            psOutput = self.send_command_and_return_output("cat /tmp/x.txt")
            logger.debug("check_MVN_is_running: 'ps' command output:\n%s" %  psOutput)
            ret=int(0)
            return ret,rc[0]

        # Commands worked ok.
        ret=int(ret)
        return ret,rc[0]

    def check_APP_has_YTTV_installed(self):
        """

        This keyword checks that the APP has the YTTV component installed.
        Note that the INI file does NOT necessarily have to have YTTV INI settings in order for it to return 'True'
        when the APP contains YTTV component.

        It returns True or False.

        Example:
        | ${ret} | ${rc}= | ESTB.check_APP_has_YTTV_installed |

        """

        ret,rc = self.send_command_and_return_output_and_rc("ps > /tmp/x.txt &")
        if rc[0] != '0':
            logger.warn("check_APP_has_YTTV_installed: 'ps' command failed!")
            ret = False
            return ret,rc[0]
        time.sleep(10)

        # Note that rc[0] will NOT be '0' if the APP does not support YTTV!
        ret,rc = self.send_command_and_return_output_and_rc("grep -E \"\/usr\/bin\/dialserver \-\-yttv on \-W off\" /tmp/x.txt")
        if rc[0] != '0':
            logger.warn("check_APP_has_YTTV_installed: 'grep' command failed!")
            psOutput = self.send_command_and_return_output("cat /tmp/x.txt")
            logger.debug("check_APP_has_YTTV_installed: 'ps' command output:\n%s" %  psOutput)
            # Must force rc[0] to be returned as '0'!!!
            ret = False
            return ret,'0'

        # Note that rc[0] will be '0' if the APP DOES support YTTV!
        ret = True
        return ret,rc[0]

    def check_APP_has_TR069_installed(self):
        """

        This keyword checks that the APP has the TR069 component installed.

        It returns True or False.

        Example:
        | ${ret} | ${rc}= | ESTB.check_APP_has_TR069_installed |

        """

        ret,rc = self.send_command_and_return_output_and_rc("ps > /tmp/x.txt &")
        if rc[0] != '0':
            logger.warn("check_APP_has_TR069_installed: 'ps' command failed!")
            ret = False
            return ret,rc[0]
        time.sleep(10)

        # Note that rc[0] will NOT be '0' if the APP does not support TR69!
        ret,rc = self.send_command_and_return_output_and_rc("grep -E \"S70cwmpd\" /tmp/x.txt")
        if rc[0] != '0':
            logger.warn("check_APP_has_TR069_installed: 'grep' command failed!")
            psOutput = self.send_command_and_return_output("cat /tmp/x.txt")
            logger.debug("check_APP_has_TR069_installed: 'ps' command output:\n%s" %  psOutput)
            # Must force rc[0] to be returned as '0'!!!
            ret = False
            return ret,'0'

        # Note that rc[0] will be '0' if the APP DOES support TR69!
        ret = True
        return ret,rc[0]

    def check_APP_has_AGAMA_installed(self):
        """

        This keyword checks that the APP has the AGAMA component installed.

        It returns True or False.

        Example:
        | ${ret} | ${rc}= | ESTB.check_APP_has_AGAMA_installed |

        """

        ret,rc = self.send_command_and_return_output_and_rc("ps > /tmp/x.txt &")
        if rc[0] != '0':
            logger.warn("check_APP_has_AGAMA_installed: 'ps' command failed!")
            ret = False
            return ret,rc[0]
        time.sleep(10)

        # Note that rc[0] will NOT be '0' if the APP does not support AGAMA!
        ret,rc = self.send_command_and_return_output_and_rc("grep -ic \"agama\" /tmp/x.txt")
        if rc[0] != '0':
            logger.warn("check_APP_has_AGAMA_installed: 'grep' command failed!")
            psOutput = self.send_command_and_return_output("cat /tmp/x.txt")
            logger.debug("check_APP_has_AGAMA_installed: 'ps' command output:\n%s" %  psOutput)
            # Must force rc[0] to be returned as '0'!!!
            ret = False
            return ret,'0'

        # Note that rc[0] will be '0' if the APP DOES support YTTV!
        # Count must be 2 or more for success (must exclude grep -ic "agama" in ps output)
        count = int(ret)
        if count > 1:
            ret = True
        else:
            ret = False,'0'
        return ret,rc[0]

    def check_APP_has_VUDU_installed(self):
        """

        This keyword checks that the APP has the VUDU component installed.
        Have to rely on 'ls' command as for 'ps' command to be useful user
        must be logged into Vudu account.

        It returns True or False.

        Example:
        | ${ret} | ESTB.check_APP_has_VUDU_installed |

        """

        ret,rc = self.send_command_and_return_output_and_rc("ls /usr/vudu/bin")
        if rc[0] != '0':
            logger.warn("check_APP_has_VUDU_installed: 'ls /usr/vudu/bin' command failed!")
            ret = False
        else:
            logger.warn("check_APP_has_VUDU_installed: 'ls /usr/vudu/bin' command successful!")
            ret = True
        return ret


    def check_APP_has_VMX_installed(self):
        """

        This keyword checks that the APP has the VMX component installed.
        Note that the INI file does NOT necessarily have to have VMX INI settings in order for it to return 'True'
        when the APP contains VMX component.

        It returns True or False.

        Example:
        | ${ret} | ${rc}= | ESTB.check_APP_has_VMX_installed |

        """

        ret,rc = self.send_command_and_return_output_and_rc("ps > /tmp/x.txt &")
        if rc[0] != '0':
            logger.warn("check_APP_has_VMX_installed: 'ps' command failed!")
            ret = False
            return ret,rc[0]
        time.sleep(10)

        # Note that rc[0] will NOT be '0' if the APP does not support VMX!
        ret,rc = self.send_command_and_return_output_and_rc("grep -E \"security_handler\" /tmp/x.txt")
        if rc[0] != '0':
            logger.warn("check_APP_has_VMX_installed: 'grep' command failed!")
            psOutput = self.send_command_and_return_output("cat /tmp/x.txt")
            logger.debug("check_APP_has_VMX_installed: 'ps' command output:\n%s" %  psOutput)
            # Must force rc[0] to be '0'!!!
            ret = False
            return ret,'0'

        # NB: Must check that irdeto is NOT running before concluding this is a VMX build!!
        # Note that rc[0] will be '0' if the APP DOES support VMX!
        ret,rc = self.send_command_and_return_output_and_rc("grep -E \"irdeto\" /tmp/x.txt")
        if rc[0] == '0':
            logger.warn("check_APP_has_VMX_installed: 'grep' command failed: Other DRM process(es) running!")
            psOutput = self.send_command_and_return_output("cat /tmp/x.txt")
            logger.debug("check_APP_has_VMX_installed: 'ps' command output:\n%s" %  psOutput)
            # Must force rc[0] to be '0'!!!
            ret = False
            return ret,'0'
        
        # Only gets here if no other DRM detected!!!
        # Must force rc[0] to be '0'!!!
        ret = True
        return ret,'0'

    def check_APP_has_IRDETO_installed(self):
        """

        This keyword checks that the APP has the IRDETO component installed.

        It returns True or False.

        Example:
        | ${ret} | ${rc}= | ESTB.check_APP_has_IRDETO_installed |

        """

        ret,rc = self.send_command_and_return_output_and_rc("ps > /tmp/x.txt &")
        if rc[0] != '0':
            logger.warn("check_APP_has_IRDETO_installed: 'ps' command failed!")
            ret = False
            return ret,rc[0]
        time.sleep(10)

        # Note that rc[0] will NOT be '0' if the APP does not support IRDETO!
        ret,rc = self.send_command_and_return_output_and_rc("grep -E \"irdetoDaemon\" /tmp/x.txt")
        if rc[0] != '0':
            logger.warn("check_APP_has_IRDETO_installed: 'grep' command failed!")
            psOutput = self.send_command_and_return_output("cat /tmp/x.txt")
            logger.debug("check_APP_has_IRDETO_installed: 'ps' command output:\n%s" %  psOutput)
            # Must force rc[0] to be '0'!!!
            ret = False
            return ret,'0'

        # Note that rc[0] will be '0' if the APP DOES support IRDETO!
        ret = True
        return ret,rc[0]

    def check_APP_has_nanocdn_installed(self):
        """

        This keyword checks that the APP has the nanoCDN component installed.

        It returns True or False.

        Example:
        | ${ret} | ${rc}= | ESTB.check_APP_has_nanocdn_installed |

        """

        ret,rc = self.send_command_and_return_output_and_rc("ps > /tmp/x.txt &")
        if rc[0] != '0':
            logger.warn("check_APP_has_nanocdn_installed: 'ps' command failed!")
            ret = False
            return ret,rc[0]
        time.sleep(10)

        # Note that rc[0] will NOT be '0' if the APP does not support nanoCDN!
        ret,rc = self.send_command_and_return_output_and_rc("grep -E \"nanocdn\" /tmp/x.txt")
        if rc[0] != '0':
            logger.warn("check_APP_has_nanocdn_installed: 'grep' command failed!")
            psOutput = self.send_command_and_return_output("cat /tmp/x.txt")
            logger.debug("check_APP_has_nanocdn_installed: 'ps' command output:\n%s" %  psOutput)
            # Must force rc[0] to be '0'!!!
            ret = False
            return ret,'0'

        # Note that rc[0] will be '0' if the APP DOES support nanoCDN!
        ret = True
        return ret,rc[0]


    def etv_browser_type(self):
        """

        This keyword determines the type of ETV browser - currently 'webkit' or 'opera4'.

        It returns 'webkit' or 'opera4' or 'unknown' if unable to determine browser type.

        Example:
        | ${browser}= | ESTB.etv_browser_type |

        """

        ret,rc = self.send_command_and_return_output_and_rc("top -n1 > /tmp/x.txt &")
        if rc[0] != '0':
            logger.warn("etv_browser_type: 'top' command failed!")
            return 'unknown'
        time.sleep(10)

        # Is the browser 'webkit'?
        # grep based on analysis of ps output for K650 etv build.
        ret,rc = self.send_command_and_return_output_and_rc("grep -E \"\.\/browser -geometry\" /tmp/x.txt")
        if rc[0] == '0':
            return 'webkit'

        # Is the browser 'opera4'?
        # grep based on analysis of ps output for K650 etv opera4 build.
        ret,rc = self.send_command_and_return_output_and_rc("grep -E \"\/usr\/opera4\/bin\/browser \" /tmp/x.txt")
        if rc[0] == '0':
            return 'opera4'

        # Getting here suggests 'ps' output does not show any browser?
        logger.warn("etv_browser_type: 'grep' commands failed!")
        psOutput = self.send_command_and_return_output("cat /tmp/x.txt")
        logger.debug("etv_browser_type: 'ps' command output:\n%s" %  psOutput)

        return 'unknown'

    def is_server_alive(self, serverIP):

        """
        This keyword checks whether a server e.g. 'CODEC License Site' is alive by
        pinging the IP address of the server.

        It returns True or False so that the calling script can make the decision as
        to what action to take.

        Example:
        | ${serverIsAlive}= | ESTB.is_server_alive | 10.0.34.14 |

        """

        retcode = self._os.run_and_return_rc("ping -c 1 " + serverIP)

        if retcode != 0:
            return False
        else:
            return True

    def convert_to_lower(self, inStr):
        """
        This keyword converts a string to lowercase.

        Example:
        | ${lowerStr}= | ESTB.convert_to_lower | ${myString}|

        """
        return(inStr.lower())

    def check_for_browser(self, return_error=True):
        '''
        Checks if the device has the browser running.
        :param bool return_error: True to raise error if False
        :return: True or False
        :rtype: Bool
        '''
        ret = self.send_command_and_return_output("ps -w | grep -v grep | grep \"middlewa.*browser \"")
        if "browser" in ret.strip():
            return True
        if return_error:
            raise RuntimeError('No browser currently running')
        return False

    def clear_hdd(self):
        '''
        Deletes the HDD's folder containing recordings. Used for soak tests
        Reboots STB. On reboot the STB creates the folder again.


        '''
        serialnum = self.get_property('serialnumber')
        serialnum = serialnum + "1"
        print serialnum
        self.send_command_and_return_output("rm -rf /mnt/hdd/%s" % serialnum)
        self.reboot_stb()



class KernelPanicError(RuntimeError):
    ROBOT_EXIT_ON_FAILURE = True
    pass

class PingResponseError(RuntimeError):
    pass


def _DEBUG(msg):
    if DEBUG:
        print "DEBUG: %s" % str(msg)

class ESTBError(RuntimeError):
    pass
