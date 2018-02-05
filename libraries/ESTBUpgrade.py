# Robot libraries
from robot.version import get_version

# Standard libraries
import time
import weakref
import os

# AminoEnable Libraries
import ESTB


__version__ = "0.1 beta"

DEBUG = False


class ESTBUpgrade(object):
    """ Upgrade helper for Enable software


    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, estb):
        if isinstance(estb, ESTB.ESTB):
            self.estb = weakref.proxy(estb)
        else:
            raise Exception("Only create ESTBUpgrade instance in ESTB")

        self.upgrade_app = None
        self.upgrade_pbl = None
        self.upgrade_bbl = None
        self.upgrade_ufs = None

    def set_upgrade_app(self, binfile):
        self.upgrade_app = binfile

    def set_upgrade_pbl(self, binfile):
        self.upgrade_pbl = binfile

    def set_upgrade_bbl(self, binfile):
        self.upgrade_bbl = binfile

    def set_upgrade_ufs(self, binfile):
        self.upgrade_ufs = binfile

    def upgrade_all(self, expect_fail=False):
        pass

    def upgrade_app(self, expect_fail=False):
        pass

    def upgrade_bbl(self, expect_fail=False):
        pass
        # wget, unzip, run ./upgrade.sh
        # Do we need to boot into any special mode? Can it happen from app.
        # if upgrade.sh fails, report and fatal out
        # May be risky?
        # Will rollback protection need zapping?        

    def get_bbl_version(self):
        ret = self.estb.send_command_and_return_output("cat bbl_identinfo.txt | grep '$TAG' | awk '{print $2}'").strip("\r\n").strip("\r\n ")
        return ret

    def get_app_version(self):
        ret = self.estb.send_command_and_return_output("cat app_identinfo.txt | grep '$TAG' | awk '{print $2}'").strip("\r\n").strip("\r\n ")
        return ret

    def get_pbl_version(self):
        ret = self.estb.send_command_and_return_output("cat pbl_identinfo.txt | grep '$TAG' | awk '{print $2}'").strip("\r\n").strip("\r\n ")
        return ret

    def check_bbl_version(self, binexpected):
        pass
        # Need to accept a build name or a full binpath
        # Use cat bbl_indentinfo.txt over debug
        # Return True if they match

    def check_app_version(self, binexpected):
        pass
        # Need to accept a build name or a full binpath
        # Use cat app_indentinfo.txt over debug
        # Return True if they match

    def check_pbl_version(self, binexpected):
        pass
        # Need to accept a build name or a full binpath
        # Use cat pbl_indentinfo.txt over debug
        # Return True if they match

    def check_ufs_version(self, binexpected):
        pass
        # Need to accept a build name or a full binpath
        # Use nvram_env -l over debug
        # Return True if they match


"""
Note: when trying to read the current values, try to do so 
without rebooting the STB first.  If that does not work try
a standard reboot.  If that doesn't work try a reboot to stop?

"""

