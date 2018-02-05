# Robot libraries
from robot.api import logger
from robot.version import get_version
from robot import utils

import time

from libraries.LinuxBox import LinuxBox

__version__ = "0.1 beta"

class AttenuatorControl(LinuxBox):

    """ Amino Attenuator Control Library by Frazer Smith.

    This library is designed for use with Robot Framework.

    This is an extension of the LinuxBox library with specific attenuator commands
    for use with RF tests such as WiFi.

    Any number of attenuators can be added to the library, then they can be controlled
    all together or individually.

    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):

        LinuxBox.__init__(self)
        self._ac_attenuators=[]
        self._ac_path_to_binary=None

    def add_attenuator(self, serial):
        """ Add an attenuator to the list of devices to enable direct control

        This will return the index of the new attenuator

        Examples:
        | ${att_input}=	| Add attenuator	| 3992	|
        """

        self._ac_attenuators.append(serial)
        return len(self._ac_attenuators)-1

    def set_ac_binary_path(self, path):

        """  Set the Attenuator Control binary path (the path for the sqa-atten binary file on the host)

        Example:
        | Set ac binary path	| /home/fsmith/temp/sqa-atten	|
        """

        self._ac_path_to_binary = path

    def set_attenuator(self, attenuation, index=-1):
        """ Sets the attenuation value of all attenuators by default, or a single one by index

        Examples:
        | Set attenuator	| 30	|		|
        | Set attenuator	| 10	| index=1	|

        """
        index = int(index)
        if index==-1:
            serial = "all"
        else:
            if attencount < (index+1):
                raise AttenuatorError("Index out of range.")
            else:
                serial = self._ac_attenuators[index]

        output = self.execute_command(self._ac_path_to_binary + " " + serial + " -a " + str(attenuation) + " 2>&1", return_rc=True)
        if int(output[1]) != 0:
            raise AttenuatorError("Attenuator return code non-zero")

        actuals=self.read_attenuator(index)
        for actual in actuals:
            if float(actual)!=float(attenuation):
                raise AttenuatorError("Failed to set attenuation! - Expected " + str(attenuation) + " but got " + str(actual))        

         
        

    def read_attenuator(self, index=-1, value="current attenuation"):
        """  Returns a value from the sqa-atten utility

        The 'index' (zero based) of the device can be defined, if not a list of all found devices
        will be returned, even if they are not defined, so this can be used to instantiate at runtime.

        Defaults to 'current attenuation' but could also be:-
        - serial	- Serial number of the device
        - Device	- The device type
        - max		- The max allowed attenuation
        - min           - The min allowed attenuation
        - step          - The step size

        Examples:
        | ${atten}=	| Read attenuator	| index=0		|			|
        | ${serial}=	| Read attenuator	| index=1		| value="serial"	|
        | ${serials}=	| Read attenuator	| value=serial		|			|
        
        """

        index = int(index)
        attencount = len(self._ac_attenuators)
        if index==-1:
            serial = "all"
        else:
            if attencount < (index+1):
                raise AttenuatorError("Index out of range.")
            else:
                serial = self._ac_attenuators[index]

        output = self.execute_command(self._ac_path_to_binary + " " + serial + " 2>&1 | grep 'current attenuation'", return_rc=True)
        if int(output[1]) != 0:
            raise AttenuatorError("Attenuator return code non-zero")

        ret=[]
        lines=output[0].split("\n")
        for line in lines:
            parts = line.split(";")
            for part in parts:
                if part.find(value)!=-1:
                    words=part.split()
                    ret.append(self._convert_type(words[len(words)-1], value))
        return ret

    def _convert_type(self, original, value):
        if value.find("current")!=-1 or value.find("max")!=-1 or value.find("min")!=-1:
            return float(original)
        else:
            return original

class AttenuatorError(RuntimeError):
    pass

