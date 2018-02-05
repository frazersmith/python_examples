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


class ESTBWiFi(object):
    """ WiFi API Provided by Enable STB

    This library is designed for WiFi scanning and control 
    WiFi status in enable stb.
    
    !!Only use these functions if capture debug is enabled.

    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, estb):
        if isinstance(estb, ESTB.ESTB):
            self.estb = weakref.proxy(estb)
            self.ssid = None
            self.akm = None
            self.key = None
        else:
            raise Exception("Only create ESTBWiFi instance in ESTB")

    def commit_config(self):
        wifi_setting_json = {
            "wifi_setting": {
                "ssid": self.ssid,
                "auth": self.akm,
                "passphrase": self.key,
                "key_index": "1"}}
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "system", json.dumps(wifi_setting_json),
            "console", "Committing WiFi Config")

    def set_config(self, ssid=None, akm=None, key=None):
        if ssid:
            self.ssid = ssid
        if akm:
            self.akm = akm
        if key:
            self.key = key

    def get_config(self, choice):
        if choice == "ssid":
            return self.ssid
        elif choice == "akm":
            return self.akm
        elif choice == "key":
            return self.key

    def get_config_string(self):
        return "ssid: %s ,akm: %s ,key: %s\n" % (self.ssid, self.akm, self.key)

    def forget_wifi_connection(self):
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "system/wifi", "{\"ssid\":\"\"}",
            "ssh", "Forget WiFi")

    def verify_config(self):
        self.estb.send_command_over_debug(
            "curl -X GET http://localhost:10080/system/wifi > " +
            "wifisettings.json; echo \"\" >> wifisettings.json")
        raw_setting_result = self.estb.send_command_over_debug_and_return_output(
            "cat wifisettings.json")
        logger.debug(raw_setting_result)
        raw_setting_result = raw_setting_result.split("\n")[-2]
        logger.debug("selected: %s \n" % raw_setting_result)
        get_wifi_result = json.loads(raw_setting_result)
        if (
                get_wifi_result["ssid"] == self.ssid and
                get_wifi_result["auth"] == self.akm and
                get_wifi_result["passphrase"] == self.key):
            return True
        else:
            return False

    def check_associate(self):
        checking_commands = "cat /tmp/network/active/network_type"
        check_result = self.estb.send_command_over_debug_and_return_output(
            checking_commands)
        if "wifi" in check_result:
            if self.estb._wifi_model == "ralink":
                checking_commands = "iwconfig ra0 | grep ESSID"
            check_result = self.estb.send_command_over_debug_and_return_output(
                checking_commands)
            if self.ssid in check_result:
                return True
            else:
                return False
        else:
            return False

    def scan(self, expected_ssid=None):
        ssid_list = []
        if self.estb._wifi_model == "ralink":
            scan_command = "ifconfig ra0 up;iwlist ra0 scanning"
            raw_scan_result = self.estb.send_command_over_debug_and_return_output(
                scan_command)
            raw_scan_result = raw_scan_result.split("ESSID:\"")
            if len(raw_scan_result) > 1:
                for token in raw_scan_result:
                    ssid_list.append(token.split("\"")[0])
        elif self.estb._wifi_model == "quantenna":
            self.estb.send_command_over_debug(
                "qcsapi_sockraw eth1 00:26:86:00:00:00 start_scan wifi0")
            self.estb.send_command_over_debug(
                "qcsapi_sockraw eth1 00:26:86:00:00:00 " +
                "get_results_ap_scan wifi0 > /tmp/scan_result.txt")
            self.estb.send_command_over_debug(
                "i=`cat /tmp/scan_result.txt`;while [[ $i -ge 0 ]]; " +
                "do i=$((i-1));qcsapi_sockraw eth1 00:26:86:00:00:00 " +
                "get_properties_AP wifi0 $i >> /tmp/scan_result.txt; done")
            raw_scan_result = self.estb.send_command_over_debug_and_return_output(
                "cat /tmp/scan_result.txt")

        print "The Scanned SSIDs are: %s" % ",".join(ssid_list)

        if expected_ssid is None:
            return True
        else:
            if expected_ssid in ssid_list:
                return True
            else:
                return False

    def join(self, method="default"):
        if method == "sed":
            auth_mode = self.akm
            encryp_type = None
            if auth_mode == "WEP":
                auth_mode = "WEPAUTO"
                encryp_type = "WEP"
            elif auth_mode == "WPA2PSK":
                encryp_type = "AES"
            elif auth_mode == "WPAPSK":
                encryp_type = "TKIP"
            self.estb.send_command_over_debug(
                "sed -i -e 's/SSID=.*$/SSID=" + self.ssid +
                "/' /mnt/persist/wireless.conf")
            self.estb.send_command_over_debug(
                "sed -i -e 's/AuthMode=.*$/AuthMode=" + auth_mode +
                "/' /mnt/persist/wireless.conf")
            self.estb.send_command_over_debug(
                "sed -i -e 's/EncrypType=.*$/EncrypType=" + encryp_type +
                "/' /mnt/persist/wireless.conf")
            if auth_mode == "WEPAUTO":
                self.estb.send_command_over_debug(
                    "sed -i -e 's/DefaultKeyID=.*$/DefaultKeyID=1/' " +
                    "/mnt/persist/wireless.conf")
                self.estb.send_command_over_debug(
                    "sed -i -e 's/Key1Type=.*$/Key1Type=0/' " +
                    "/mnt/persist/wireless.conf")
                self.estb.send_command_over_debug(
                    "sed -i -e 's/Key1Str=.*$/Key1Str=" + self.key +
                    "/' /mnt/persist/wireless.conf")
            else:
                self.estb.send_command_over_debug(
                    "sed -i -e 's/WPAPSK=.*$/WPAPSK=" + self.key +
                    "/' /mnt/persist/wireless.conf")
        else:
            self.commit_config()
        self.estb.send_command_over_debug(
            "sed -i -e 's/wlan0=.*$/wlan0=14/' /tmp/sys_config.txt")
        self.estb.send_command_over_debug(
            "sed -i -e 's/wlan1=.*$/wlan1=12/' /tmp/sys_config.txt")
        self.estb.send_command_over_debug(
            "ifconfig eth0 down; /etc/init.d/S40network real_time_restart",
            suppresslogin=True, timeout="60 seconds")
        return self.check_associate()
