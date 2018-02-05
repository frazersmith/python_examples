# Robot libraries

from robot.api import logger
from robot.version import get_version

# Standard libraries
import weakref
import json

# AminoEnable Libraries
import ESTB


__version__ = "0.1 beta"

DEBUG = False


class ESTBRESTAPI(object):
    """ REST API is Provided by Enable STB

    This library is designed for sending curl command to stb localhost
    rest api.

    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, estb):
        if isinstance(estb, ESTB.ESTB):
            self.estb = weakref.proxy(estb)
        else:
            raise Exception("Only create ESTBRESTAPI instance in ESTB")

    def send_curl_command_and_return_output(
            self, method, url, data, need_status_code, send_method):
        command = "curl -X %s " % method
        if method in ["POST", "PUT"]:
            command += "-d '%s' " % data
        command += "http://localhost:10080/%s" % url
        if method == "GET" and data != "":
            command += "?%s" % data
        if need_status_code:
            command += " -v"

        if send_method == "ssh":
            return self.estb.send_command_and_return_output(command)
        elif send_method == "console":
            return self.estb.send_command_over_debug_and_return_output(command)
        return False

    def send_curl_command_and_expect_200(
            self, method, url, data, send_method, explain_str):
        ret = self.send_curl_command_and_return_output(
            method, url, data, True, send_method)
        if not "HTTP/1.1 200 OK" in ret:
            logger.debug("%s return code not 200\n%s" % (explain_str, ret))
            return False
        return True

    def send_curl_command_and_expect_json(
            self, method, url, data, send_method, explain_str):
        raw_ret = self.send_curl_command_and_return_output(
            method, url, data, False, send_method)
        try:
            ret = json.loads(raw_ret)
            return ret
        except ValueError:
            logger.debug(explain_str+" failed to resolve to json\n"+raw_ret)
            return False
