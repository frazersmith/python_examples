# Robot libraries
from robot.api import logger
from robot.version import get_version

# Standard libraries
import time
import weakref
import os

# AminoEnable Libraries
import ESTB


__version__ = "0.1 beta"

DEBUG = False


class ESTBSystem(object):
    """ System API Provided by Enable STB

    This library is designed for control STB commonly used functions.
    Including:
        HNR password to unlock console
        Reboot to different state
        Change Resolution/Aspect_Ratio/hdmi_hotplug_mode/audio/color_system
        Running Process Checking and CPU Checking

    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, estb):
        if isinstance(estb, ESTB.ESTB):
            self.estb = weakref.proxy(estb)
        else:
            raise Exception("Only create ESTBSystem instance in ESTB")

    def hnr_console_password(self):
        os.system(
            os.environ['UNLOCKSECUREINIT_CMD'] + ' ' +
            self.estb._interfaces[0][1] + ' ' +
            os.environ['JENKINS_USERNAME'] + ' ' + os.environ['JENKINS_PW'] +
            '> /dev/null 2>/dev/null')

    def reboot_stb_using_debug(self):
        self.estb.close_all_but_debug()
        self.estb.send_command_over_debug("reboot")
        self.estb.add_debug_listener("S99startup:")
        try:
            self.estb.wait_for_debug_listener(
                "S99startup:", timeout="150 seconds")
            self.estb.remove_debug_listener("S99startup:")
            self.hnr_console_password()
            self.estb.login_and_keep_ssh_open()
            self._init_av_test()
            return True
        except ESTB.ESTBError:
            self.estb.remove_debug_listener("S99startup:")
            return False
        except:
            pass

    def _init_av_test(self):
        self.estb.send_command_and_return_output(
            "/etc/splashlc.sh system close")
        if (self.estb._app == "minerva" and
                not self.get_process_running("EntoneWebEngine")):
            self.estb.send_command_and_return_output(
                "EntoneWebEngine > webEnginelog 2>webEngineError &")
            time.sleep(5)
        self.estb.send_command_and_return_output("\n")

    def reboot_to_stop_boot(self, method, init_test):
        self.estb.send_command_and_return_output(
            "sed -i -e \"s/bootMethod=.*$/bootMethod=0/\" " +
            "/mnt/persist/sys_config.txt")
        if method == "ssh":
            self.estb.reboot_stb(pingtimeout="3 minutes")
            self.estb.login_and_keep_ssh_open()
            if init_test:
                self._init_av_test()
            return True
        elif method == "console":
            return self.reboot_stb_using_debug()

    def check_stop_boot(self):
        if (not self.get_process_running("browser")):
            self._init_av_test()
            return True;
        else:
            return False;

    def reboot_to_normal_boot(self, method):
        self.estb.send_command_and_return_output(
            "sed -i -e \"s/bootMethod=.*$/bootMethod=1/\" " +
            "/mnt/persist/sys_config.txt")
        if method == "ssh":
            self.estb.reboot_stb(pingtimeout="3 minutes")
            self.estb.login_and_keep_ssh_open()
            return True
        elif method == "console":
            return self.reboot_stb_using_debug()

    def get_hdmi_supported_resolution(self):
        ret = self.estb.send_curl_command_and_expect_json(
            "GET", "system/hdmi", "", "ssh", "Get Supported Resolution")
        return ret["supported_resolution"]

    def change_resolution(self, resolution):
        # resolution list from EssResolution in EPL/Core/inc/enSystemSettingDefs.h
        resolution_list = ["1080p24", "1080p30", "1080p50", "1080p60", "1080i",
                           "1080i50", "1080i60", "720p", "720p50", "720p60",
                           "576p", "576i", "480p", "480i", "stdp", "stdi",
                           "4kp24", "4kp25", "4kp30", "4kp50", "4kp60",
                           "1080p25", "unchange", "max_opt"]
        supported_resolution_list = self.get_hdmi_supported_resolution()
        if not resolution in supported_resolution_list:
            logger.debug("%s not found in available resolution list\n" % resolution)
            return False
        resolution_num = resolution_list.index(resolution)
        ret = self.estb.send_curl_command_and_expect_json(
            "PUT", "system", "{\"resolution\":\"%d\"}" % resolution_num,
            "ssh", "Change Resolution")
        if ret["resolution"] in resolution_list:
            result_resolution = ret["resolution"]
        else:
            result_resolution = resolution_list[int(ret["resolution"])]

        logger.debug("Target resolution: %s; Result resolution: %s\n"
                % (resolution, result_resolution))
        return result_resolution == resolution

    def change_aspect_ratio(self, ratio):
        ratio_name_dict = {"16:9 Pillar": "ESS_PILLAR",
                           "16:9 Wide": "ESS_WIDE", "16:9 Zoom": "ESS_ZOOM",
                           "16:9 Panorama": "ESS_PANORAMA",
                           "4:3 Crop": "ESS_CROP",
                           "4:3 Letterbox": "ESS_LETTERBOX",
                           "4:3 Squeeze": "ESS_SQUEEZE", "14:9": "ESS_LB_14_9"}
        if not ratio in ratio_name_dict:
            return False
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "system",
            "{\"aspect_ratio\":\"%s\"}" % ratio_name_dict[ratio],
            "ssh", "Change Aspect Ratio")

    def change_hdmi_hotplug_mode(self, mode):
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "system/hdmi", "{\"hotplug_mode\":\"%s\"}" % mode,
            "ssh", "Change HotPlug Mode")

    def change_system_audio(self, right_volume, left_volume, mute):
        if left_volume == -1:
            left_volume = right_volume
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "system/audio",
            "{\"mute\":\"%s\",\"volume\":{\"right\":\"%d\",\"left\":\"%d\"}}"
            % (mute, right_volume, left_volume), "ssh", "Change System Audio")

    def change_front_panel_params(
            self, display_mode, display_brightness,
            front_panel_led, clock_mode):
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "system/front_panel",
            "{\"display_mode\":\"%d\",\"display_brightness\":\"%d\",\"front_panel_led\":\"%d\",\"clock_mode\":\"%s\"}"
            % (display_mode, display_brightness, front_panel_led, clock_mode),
            "ssh", "Change Front Panel Setting")

    def change_color_system(self, color_system, force_reboot, init_test):
        if not force_reboot:
            ret = self.estb.send_command_and_return_output(
                "if [ -e /tmp/%s ]; then echo OK; fi"
                % color_system.lower().strip())
            if "OK" in ret:
                if init_test:
                    self._init_av_test()
                return True

        if color_system == "NTSC":
            stb_color = "N"
        elif color_system == "PAL":
            stb_color = "P"
        else:
            return False

        stb_hwblk_ver = 0
        stb_esn = ""
        stb_hw_model = ""
        stb_board_ver = ""
        stb_secure_type = ""
        stb_dram = ""
        stb_cid = ""
        stb_reqver = ""
        readhwblk_ret = self.estb.send_command_and_return_output("readhwblk")

        for line in readhwblk_ret.split("\n"):
            if line.startswith("Version:"):
                stb_hwblk_ver = int(line.split(":")[1].strip())
            elif line.startswith("ESN:"):
                stb_esn = line.split(":")[1].strip()
            elif line.startswith("HW Model:"):
                stb_hw_model = line.split(":")[1].strip()
            elif line.startswith("Board Version:"):
                stb_board_ver = line.split(":")[1].strip()
            elif line.startswith("Secure Type:"):
                stb_secure_type = line.split(":")[1].strip()
            elif line.startswith("CONSTRAINT_DRAM="):
                stb_dram = line.split("=")[1].strip()
            elif line.startswith("ST - Customer ID:"):
                stb_cid = line.split(":")[1].strip()
            elif line.startswith("ST - Requirement Ver.:"):
                stb_reqver = line.split(":")[1].strip()

        write_string = ("writehwblk " + stb_hw_model + " -esn " + stb_esn +
                        " -boardver \"" + stb_board_ver + "\" -color "
                        + stb_color)
        if stb_hwblk_ver > 3:
            write_string += (" -secure %s" % stb_secure_type)
            if stb_hwblk_ver > 4:
                write_string += (" -dram \"%s\"" % stb_dram)
                if stb_hwblk_ver > 9:
                    write_string += (" -cid %s -reqver %s"
                                     % (stb_cid, stb_reqver))
        self.estb.send_command_and_return_output(write_string)
        self.estb.send_command_and_return_output(
            "rm -f /mnt/persist/force_pal")
        self.estb.send_command_and_return_output(
            "rm -f /mnt/persist/force_ntsc")
        return self.reboot_to_stop_boot("ssh", init_test)

    def get_cpu_idle(self):
        return self.estb.send_command_and_return_output(
            "iostat -c | tail -n1 | awk '{print $NF}'")

    def get_process_running(self, process_name):
        ret = self.estb.send_command_and_return_output(
            "ps | grep %s | grep -v grep" % process_name)
        return process_name in ret

    def write_cpu_idle_list_to_csv(
            self, filename, cpu_idle_list, total_time):
        total_time = total_time.total_seconds()
        with open(os.environ['WORKSPACE']+"/"+filename, "w") as fout:
            num_of_measures = len(cpu_idle_list)
            for i in range(num_of_measures):
                fout.write(str(total_time/num_of_measures*(i+1))+",")
            fout.write("\n")
            for cpu_idle in cpu_idle_list:
                fout.write(cpu_idle.strip()+",")
            fout.write("\n")

    def set_AC3(self, value):
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "system", "{\"digital_audio_output\":\"%s\"}" % value,
            "ssh", "Set AC3")

    def set_fan_on_off(self, on_off):
        fan_speed = 0
        explain_str = "Set fan Off Failed"
        if on_off:
            fan_speed = 1
            explain_str = "Set fan On Failed"
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "system",
            "{\"fan_speed\":\"%d\"}" % fan_speed, "ssh", explain_str)

    def get_network_status(self):
        return self.estb.send_curl_command_and_expect_json(
            "GET", "system/network", "", "ssh", "Get Network Status")

    def get_current_active_wan(self):
        return self.get_network_status()["current_active_wan"]

    def get_current_active_nic(self):
        network_status = self.get_network_status()
        for nic in network_status["nic"]:
            if nic["nic_name"] == network_status["current_active_wan"]:
                return nic

    def get_entone_env(self):
        return self.estb.send_curl_command_and_expect_json(
            "GET", "system/entone_env", "", "ssh", "Get Entone Envs")

    def get_storage_space_info(self, specific):
        if len(specific) > 1:
            specific = "/" + specific
        return self.estb.send_curl_command_and_expect_json(
            "GET", "system/spacemgr" + specific, "", "ssh", "Get storage info")

    def get_standby_info(self):
        return self.estb.send_curl_command_and_expect_json(
            "GET", "system/standby", "", "ssh", "Get standby info")

    def get_standby_mode(self):
        ret,rc = self.estb.send_command_and_return_output_and_rc(
            "cat /mnt/persist/sys_config.txt | grep 'user_standby_mode' | cut -d \= -f 2")

        ret = ret.replace('\r\n','  ')
        ret = ret.replace(' ','')
        result = "error"
        if rc=='0':
            if ret=='0':
                result = "quick"
            elif ret=='1':
                result = "deep"
            else:
                logger.warn("Standby mode obtained=%s not recognised!\n" % ret)
        else:
            logger.warn("Unable to obtain standby mode from DUT!\n")

        return result

    def set_standby_mode(self, standby_mode):
        if standby_mode == "quick":
            smode = 0
        elif standby_mode == "deep":
            smode = 1
        else:
            logger.debug("Standby mode specified=%s not recognised!\n" % standby_mode)
            return False
        ret,rc = self.estb.send_command_and_return_output_and_rc(
            "update_syscfg.sh user_standby_mode %d" % smode)
        return rc

    def get_syslog_info(self):
        return self.estb.send_curl_command_and_expect_json(
            "GET", "system/syslog", "", "ssh", "Get syslog info")

    def set_syslog_config(self, log_level, log_facility, log_mode, log_server):
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "system",
            "{\"log_level\":\"%d\",\"log_facility\":\"%d\",\"log_mode\":\"%s\",\"log_server\":\"%s\"}"
            % (log_level, log_facility, log_mode, log_server), "ssh", "set syslog config failed")
