"""
Classes:
    HttpRest -
"""
# Robot libraries
from robot.api import logger
from robot.version import get_version

import ast
import json
import requests

__version__ = "0.1"

class HttpRest(object):
    """     Amino HttpRest Class

    Designed to be a library of abstracted methods providing access and control
    to the entone media player on a STB through the REST API.
    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):
        self._stb_ip = None
        self._base_url = None

    def set_stb_ip(self, ip_addr):
        """     Set the IP address of the STB under test
        """

        self._stb_ip = ip_addr
        self._base_url = 'http://%s:10080' % (ip_addr)

        logger.debug('Set STB IP to   : %s' % (self._stb_ip))
        logger.debug('Set base url to : %s' % (self._base_url))

    def _check_config(self):
        """     Checks that the STB IP is set, raises an error if it is not
        """

        if self._stb_ip == None:
            raise RuntimeError('Cannot do HTTP request without setting STB IP')

    # Start base HTTP methods

    def http_get(self, path, payload=None, expect_status_code=200):
        """     Send a HTTP GET
        """

        self._check_config()

        http = requests.get('%s%s' % (self._base_url, path), data=payload)

        if http.status_code != expect_status_code:
            logger.warn('Didnt get the expec ted status code')

        return http.text

    def http_post(self, path, payload=None, expect_status_code=200):
        """     Sends an HTTP POST to the STBs
        """

        self._check_config()

        http = requests.post('%s%s' % (self._base_url, path), data=payload)

        if http.status_code != expect_status_code:
            logger.warn('got an HTTP status code we didnt expect')

        return http.text

    def http_put(self, path, payload=None, expect_status_code=200):
        """     docstring
        """

        self._check_config()

        http = requests.put('%s%s' % (self._base_url, path), data=payload)

        if http.status_code != expect_status_code:
            logger.warn('got an HTTP status code we didnt expect')

        return http.text

    # Start abstracted video methods

    def get_player_list(self):
        """     Return the list of players on the STB
        """

        players = self.http_get('/player')
        player_list = ast.literal_eval(players)

        return player_list

    def start_video_stream(self, stream_url):
        """     Starts a video strem via the STB REST API
        """

        player_list = self.get_player_list()

        if len(player_list) == 0:
            player_id = self.http_post('/player')

        else:
            player_id = player_list[0]

        http_payload = {'src': stream_url, 'playnow': 1, 'id': player_id}

        start_req = self.http_post('/player/%s/open' % (player_id),
                                    payload=http_payload)

        logger.debug('/player/%s/open returned %s' % (player_id, start_req))

    def get_available_audio_languages(self):
        """     Returns a list of the available audio languages in the
        currently playign stream on the unit under test.
        """

        player_id = self.get_player_list()[0]

        ret_text = self.http_get('/player/%s?audio' % (player_id))

        lang_list = [x['lang'] for x in json.loads(ret_text)['audio']['info']]

        logger.debug('Got language list: %s' % (lang_list))

        return lang_list

    def set_subtitles_state(self, enable):
        """

        Examples:
        | ${success_1}=  | HttpRest.Set Subtitles State  | ${1}  | # enable  |
        | ${success_2}=  | HttpRest.Set Subtitles State  | ${0}  | # disable |
        """

        if int(enable) not in [0, 1]:
            logger.warn('set_subtitles_state: param needs to be 0 or 1')

        payload = {"subtitle": {"enable": int(enable)}}

        ret_raw = self.http_put('/system', payload=json.dumps(payload))

        return json.loads(ret_raw)['subtitle']['enable']

    def set_closed_captions_state(self, enable):
        """

        Examples:
        | ${success_1}=  | HttpRest.Set Closed Captions State  | ${1}  |
        | ${success_2}=  | HttpRest.Set Closed Captions State  | ${0}  |
       """

        if int(enable) not in [0, 1]:
            logger.warn('set_subtitles_state: param needs to be 0 or 1')

        cur_player = self.get_player_list()[0]

        payload = "{\"closed_caption\": {\"enable\": %d}}" % (int(enable))

        ret_raw = self.http_put('/player/%s' % (cur_player), payload=payload)

        return ret_raw


    def get_supported_hdmi_resolutions(self):
        """     Get a list of the currently supported HDMI resolutions
        """

        ret_raw = self.http_get('/system/hdmi')

        res_list = json.loads(ret_raw)['supported_resolution']

        return res_list
