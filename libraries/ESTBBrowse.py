# Robot libraries
from robot.version import get_version

# Standard libraries
import weakref
import json

# AminoEnable Libraries
import ESTB


__version__ = "0.1 beta"

DEBUG = False


class ESTBBrowse(object):
    """ Browse API Provided by Enable STB

    This library is designed for browse externel device connecting to stb.

    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    devices = []

    def __init__(self, estb):
        if isinstance(estb, ESTB.ESTB):
            self.estb = weakref.proxy(estb)
        else:
            raise Exception("Only create ESTBBrowse instance in ESTB")

    def get_available_browse_dev(self):
        self.devices = self.estb.send_curl_command_and_expect_json(
            "GET", "browse", "", "ssh", "Get Available Device")
        if not self.devices:
            self.devices = []
        return len(self.devices)

    def browse_path(self, device, path):
        if self.get_available_browse_dev() == 0:
            return False
        for device_conf in self.devices:
            if device_conf["type"].lower() == device.lower():
                device_path = device_conf["device"].replace("\/", "/")
                if device_path in path:
                    raw_ret = self.estb.send_curl_command_and_return_output(
                        "GET", "browse/"+device+path, "", False, "ssh")
                    try:
                        dirs = json.loads(raw_ret)
                        return dirs
                    except ValueError:
                        return raw_ret
                else:
                    print("Browse path not right! Do not contain "+device_path)
                    return False
            else:
                print("Browse device not right! Do not contain "+device)
                return False
        return False
