# Robot libraries
from robot.api import logger
from robot.version import get_version

# Standard libraries
import weakref

# AminoEnable Libraries
import ESTB


__version__ = "0.1 beta"

DEBUG = False


class ESTBPlayer(object):
    """ Player API Provided by Enable STB

    This library is designed for control Player status in enable stb.
    And change CC/Subtitle Settings.

    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, estb):
        if isinstance(estb, ESTB.ESTB):
            self.estb = weakref.proxy(estb)
        else:
            raise Exception("Only create ESTBPlayer instance in ESTB")

    def _get_available_players(self):
        return self.estb.send_curl_command_and_expect_json(
            "GET", "player", "", "ssh", "Get Available Players")

    def get_first_player(self):
        player_ids = self._get_available_players()
        if (not player_ids) or len(player_ids) == 0:
            return False
        else:
            return self._get_available_players()[0]

    def open_a_new_player(self, src, pltbuf, window_type):
        player_id = self.estb.send_curl_command_and_return_output(
            "POST", "player", "{\"window_type\":\"%s\"}" % window_type,
            False, "ssh")
        player_id = player_id.strip()
        if len(player_id) < 1:
            logger.debug("can't create a new player")
            return False
        if self.estb.send_curl_command_and_expect_200(
                "POST", "player/%s/open" % player_id,
                "{\"src\":\"%s\",\"pltbuf\":\"%d\"}" % (src, pltbuf),
                "ssh", "Open source"):
                return player_id
        return False

    def change_player_src(self, player_id, src, playnow):
        if self.estb.send_curl_command_and_expect_200(
                "POST", "player/%s/open" % player_id,
                "{\"src\":\"%s\",\"playnow\":\"%d\"}" % (src, playnow),
                "ssh", "Open source"):
            return True

    def change_player_param(self, player_id, x, y, z, h, w):
        set_string = '{'
        if x:
            set_string += '"x":"%d"' % x
        if y:
            set_string += '"y":"%d"' % y
        if z:
            set_string += '"z":"%d"' % z
        if h:
            set_string += '"h":"%d"' % h
        if w:
            set_string += '"w":"%d"' % w
        if set_string == '{':
            return False
        set_string += '}'
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "player/%s" % player_id, set_string, "ssh", "Change Param")

    def player_command_play(self, player_id, speed):
        return self.estb.send_curl_command_and_expect_200(
            "POST", "player/%s/play" % player_id,
            "{\"speed\":\"%d\"}" % speed, "ssh", "Command Play")

    def player_command_pause(self, player_id):
        return self.estb.send_curl_command_and_expect_200(
            "POST", "player/%s/pause" % player_id, "", "ssh", "Command Pause")

    def player_command_seek(self, player_id, seek_value, mode):
        return self.estb.send_curl_command_and_expect_200(
            "POST", "player/%s/seek" % player_id,
            "{\"seek_value\":\"%d\",\"mode\":\"%d\"}'" % (seek_value, mode),
            "ssh", "Command Seek")

    def get_available_audio_langs(self, player_id):
        audio_langs = []
        ret = self.estb.send_curl_command_and_expect_json(
            "GET", "player/%s" % player_id,
            "audio", "ssh", "Get audio languages")
        for track in ret["audio"]["info"]:
            audio_langs.append(track["lang"])
        return audio_langs

    def change_audio_lang(self, player_id, lang):
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "player/%s" % player_id,
            "{\"audio\":{\"enabled_stream\":%d}}" % lang,
            "ssh", "Change Language")

    def enable_subtitle(self):
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "system", "{\"subtitle\":{\"enable\":1}}",
            "ssh", "Enable Subtitle")

    def set_subtitle_preferred_lang(self, lang):
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "system", "{\"subtitle\":{\"preferred_lang\":\"%s\"}}" % lang,
            "ssh", "Set Subtitle Preferred Language")

    def get_available_subtitle_langs(self, player_id):
        ret = self.estb.send_curl_command_and_expect_json(
            "GET", "player/%s" % player_id,
            "subtitle", "ssh", "Get subtitle languages")
        return ret["subtitle"]["available_languages"]

    def change_subtitle_lang(self, player_id, lang):
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "player/%s" % player_id,
            "{\"subtitle\":{\"enabled\":1,\"language\":\"%s\"}}" % lang,
            "ssh", "Change Subtitle Language")

    def enable_cc(self, player_id):
        if (self.estb._app == "minerva" and
                not self.get_process_running("EntoneWebEngine")):
            self.estb.send_command_and_return_output(
                "softCCDaemon > cclog 2>ccError &")
        if self.estb.send_curl_command_and_expect_200(
                "PUT", "system", "{\"closed_caption\":{\"enable\":1}}",
                "ssh", "Enable System CC"):
            if self.estb.send_curl_command_and_expect_200(
                    "PUT", "player/%s" % player_id,
                    "{\"closed_caption\":{\"enable\":1}}",
                    "ssh", "Enable Player CC"):
                return True
        return False

    def change_cc_on(self, mode):
        cc_type_dict = ["off", "On TV", "Analog CC1", "Analog CC2",
                        "Analog CC3", "Analog CC4", "Digital CC1",
                        "Digital CC2", "Digital CC3", "Digital CC4",
                        "Digital CC5", "Digital CC6"]
        return self.estb.send_curl_command_and_expect_200(
            "PUT", "system",
            "{\"closed_caption\":{\"type\":%d}}" % cc_type_dict.index(mode),
            "ssh", "Change CC Mode")
