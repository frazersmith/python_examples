# Robot libraries
from robot.version import get_version

# Standard libraries
import weakref
import datetime

# AminoEnable Libraries
import ESTB


__version__ = "0.1 beta"

DEBUG = False


class ESTBTimeControl(object):
    """ Datetime Control API for Robot Framework Test Script

    This library is designed for doing datetime operation inside test script.
    For the robotframework used by aminorobot do not support datetime library

    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, estb):
        if isinstance(estb, ESTB.ESTB):
            self.estb = weakref.proxy(estb)
        else:
            raise Exception("Only create ESTBTimeControl instance in ESTB")

    def get_current_time(self):
        return datetime.datetime.now()

    def convert_time_delta(self, time_delta):
        time_delta = time_delta.split(":")
        if len(time_delta) == 2:
            return datetime.timedelta(
                hours=int(time_delta[0]), minutes=int(time_delta[1]))
        else:
            return False

    def datetime_add(self, datetime1, datetime2):
        return datetime1 + datetime2

    def datetime_substract(self, datetime1, datetime2):
        return datetime1 - datetime2

    def datetime_less_than(self, datetime1, datetime2):
        return datetime1 < datetime2
