# Robot libraries
from robot.api import logger
from robot.version import get_version

# Standard libraries
import weakref

# AminoEnable Libraries
import ESTB


__version__ = "0.1 beta"

DEBUG = False


class ESTBRecorder(object):
    """ Recorder API Provided by Enable STB

    This library is designed for control Recorder status in enable stb.
    And provide managment API to assets.

    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, estb):
        if isinstance(estb, ESTB.ESTB):
            self.estb = weakref.proxy(estb)
        else:
            raise Exception("Only create ESTBRecorder instance in ESTB")

    def open_a_new_recorder(self, src, assetname):
        recorder_id = self.estb.send_curl_command_and_return_output(
            "POST", "recorder", "", False, "ssh")
        recorder_id = recorder_id.strip()
        if len(recorder_id) < 1:
            logger.debug("can't create a new recorder")
            return False
        if self.estb.send_curl_command_and_expect_200(
                "POST", "recorder/%s/open" % recorder_id,
                "{\"src\":\"%s\",\"assetname\":\"%s\"}" % (src, assetname),
                "ssh", "Open source"):
            return recorder_id
        return False

    def change_recorder_src(self, recorder_id, src, assetname):
        if self.estb.send_curl_command_and_expect_200(
                "POST", "recorder/%s/close" % recorder_id,
                "", "ssh", "Close Source"):
            if self.estb.send_curl_command_and_expect_200(
                    "POST", "recorder/%s/open" % recorder_id,
                    "{\"src\":\"%s\",\"assetname\":\"%s\"}" % (src, assetname),
                    "ssh", "Open source"):
                return True
        return False

    def recorder_command_start(self, recorder_id):
        return self.estb.send_curl_command_and_expect_200(
            "POST", "recorder/%s/start" % recorder_id,
            "", "ssh", "Command Start")

    def recorder_command_stop(self, recorder_id):
        return self.estb.send_curl_command_and_expect_200(
            "POST", "recorder/%s/stop" % recorder_id,
            "", "ssh", "Command Stop")

    def find_asset(self, assetname):
        assetname = "pvr://" + assetname
        ret = self.estb.send_curl_command_and_expect_json(
            "GET", "media", "", "ssh", "Find Asset %s" % assetname)

        for asset in ret:
            if asset["media_url"] == assetname:
                return asset["media_id"]
        return False

    def delete_asset(self, assetname):
        asset_id = int(self.find_asset(assetname))
        return self.estb.send_curl_command_and_expect_200(
            "DELETE", "media/%d" % asset_id, "", "ssh", "Delete Asset")
