"""
NOTES:
    For the standard Aten, Van Cryst HDMI 8 port switch, model no VS0801H

    Serial port settings of 19200,8N1,No

    Commands to switch are 'sw ixx' where xx is the port to switch to between 01 and 08

    This will prompt a response of 'sw ixx Command OK' where xx is the port

    Locking:
        I think I'll need to create a lock file for a certain serial port so if two
        seperate test processes try to use the same switch it will not happen.

        the best place to unlock it would be the uut, when it's closed as part of suite teardown
        so that means the code needs to exist as part of an ESTB object.

        But can it be initialised on the __init__ (i.e. locked?)

        What would be ideal would be a completely transparent system where we just need to
        init the test, it will lock the serial port and not let go until

"""

# Robot libraries
from robot.api import logger
from robot.version import get_version

# Standard libraries
import weakref
import serial
import os
import time


# AminoEnable Libraries
import ESTB
from libraries.SharedResource import SharedResource

__version__ = "0.1 beta"

DEBUG = False
DEFAULT_HDMI_SWITCH_TYPE = "VS0801Hv2"

class HDMISwitch(SharedResource):


    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):

        super(HDMISwitch, self).__init__()

        self.serialport = None
        self.hdmiport = None
        self.lockfile = None
        self.default_hdmi_switch_type = DEFAULT_HDMI_SWITCH_TYPE
        self.hdmi_switch_type = None



    def set_hdmi_switch(self, serial_and_position, hdmi_switch_type=DEFAULT_HDMI_SWITCH_TYPE):
        try:
            self.serialport = serial_and_position.split(":")[0]
            self.hdmiport = "%02d" % int(serial_and_position.split(":")[1])
            self.hdmi_switch_type = hdmi_switch_type

        except:
            raise HDMISwitchError("Invalid serial:position setting.  Use form '[serialport]:[hdmiport]', e.g. '/dev/ttyUSB0:1'")

        self.shared_resource_lockfile = self.serialport.split('/')[-1]

    def _check_port_set(self):
        if self.hdmiport is None or self.serialport is None:
            raise HDMISwitchError("HDMI serialport or hdmiport not set!")

    def switch_hdmi(self, waitfor="5 minutes", debug=False):
        # Make use of the shared resource
        # the 'waitfor' time


        self._check_port_set()


        if not self._lock_switch():
            return False


        if not debug:
            response = self._send_command("sw i%s\r" % self.hdmiport)

            if "Command OK" not in response:
                self.unlock_switch()

                raise HDMISwitchError("Error switching to HDMI port '%s'" % self.hdmiport)
            else:
                return True
        else:
            self._log("HDMISwitch Debug Mode (not actually setting any ports)")
            return True

    def _send_command(self, command):
        try:
            con = serial.Serial(port=self.serialport, baudrate=19200, bytesize=8, parity='N', stopbits=1)

        except OSError:
            raise HDMISwitchError("Unable to contact powerip device on '%s'" % self.serialport)


        con.write(command.encode())
        con.flushInput()

        time.sleep(0.1)

        response = con.read(con.inWaiting())

        con.close()

        return response


    def read_hdmi_port(self):

        self._check_port_set()

        response = self._send_command("read\r")

        """
        Format of response is:
        read Command OK\r\nInput: port4\r\nOutput: ON\r\nMode: Next\r\nGoto: OFF\r\nF/W: V2.0.197\r\n

        """
        port = int(response.split('\r\n')[1].split('port')[1])
        return port


    def _lock_switch(self):
        self._check_port_set()
        return self.grab_shared_resource(self.hdmiport)


    def unlock_switch(self):
        self._check_port_set()
        self.release_shared_resource(self.hdmiport)


    def __del__(self):
        #Ensure we unlock the port
        time.sleep(3)
        try:
            self.unlock_switch()
        except HDMISwitchError:
            pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        time.sleep(3)
        print "EXIT"

class HDMISwitchError(RuntimeError):
    pass