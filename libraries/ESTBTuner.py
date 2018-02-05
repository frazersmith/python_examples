# Robot libraries
from robot.api import logger
from robot.version import get_version

# Standard libraries
import weakref

# AminoEnable Libraries
import ESTB


__version__ = "0.1 beta"

DEBUG = False


class ESTBTuner(object):
    """ Tuner Control API Provided by Enable STB

    This library is designed for control tuner status in enable stb.

    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, estb):
        if isinstance(estb, ESTB.ESTB):
            self.estb = weakref.proxy(estb)
        else:
            raise Exception("Only create ESTBTuner instance in ESTB")

    def open_a_new_tuner(self, standard, symbol_rate, frequency):
        tuner_id = self.estb.send_curl_command_and_return_output(
            "POST", "tuner", "", False, "ssh")
        tuner_id = tuner_id.strip()
        if len(tuner_id) < 1:
            logger.debug("can't create a new tuner")
            return False
        if self.change_tuner_setting(
                tuner_id, standard, symbol_rate, frequency):
            return tuner_id
        return False

    def change_tuner_setting(self, tuner_id, standard, symbol_rate, frequency):
        standard_dict = {"ATSC": 1, "DVB-C": 2, "US Cable": 4, "DVB-T": 8,
                         "DVB-S": 16, "DVB-S2": 32, "SCTE-55-2": 64,
                         "NTSC": 128, "QAM": 256, "ISDB-T": 512,
                         "DOCSIS": 1024, "DVB-T2": 2048}
        if self.estb.send_curl_command_and_expect_200(
                "PUT", "tuner/%s" % tuner_id,
                "{\"standard\":\"%d\",\"symbol_rate\":\"%s\",\"frequency\":\"%s\"}"
                % (standard_dict[standard], symbol_rate, frequency),
                "ssh", "Change Tuner Setting"):
            return True
        return False

    def get_tuner_property(self, tuner_id):
        ret = self.estb.send_curl_command_and_expect_json(
            "GET", "tuner/%s" % tuner_id, "", "ssh", "Get Tuner Properties")
        return ret
