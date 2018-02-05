"""
Classes:
    Streamer - aminorobot library for dynamically starting IGMP streams
"""
# Robot libraries
from robot.api import logger
from robot.version import get_version

import time
import requests

__version__ = "0.1 beta"

class Streamer(object):
    """     Amino Streamer Class - Video streaming library

    This class wraps the stream4 http interface to dynamically start
    IGMP streams, and to get the URL for use within aminorobot tests

    To see available clips from this server, navigate a browser to:
    http://stream4/null?action=list

    The library scope is TEST SUITE, so any streams started by this
    instance of the library will be stopped when the suite it is
    contained in finishes. Although stream stopping will be done
    automatically on the library destructor, it is best practice
    to start the required streams in SUITESETUP and to stop each
    stream manually in the SUITETEARDOWN
    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):
        self._streams_started = []

    def __del__(self):
        self.stop_all_stream4_igmp()

    def start_stream4_igmp(self, filename, die_on_already_running=False):
        """     Start a single IGMP stream, using clip path from the clip list

        This keyword starts a clip identified by the filename parameter, this
        string should be equal to one from the clip list, which is relative to
        /home/media on stream4. The keyword then returns the full IGMP URL to
        the stream.

        If you want the stream to always start from the beginning, then pass
        the name parameter die_on_already_running=${True} (see example), this
        will raise an exception if the stream is already running when trying
        to start it.

        Clip List URL: http://stream4/null?action=list

        Examples:
        | ${clip_name}=               | Set Variable                | testcard-4x3-480P60-H264.ts    |
        | ${stream_url}=              | Streamer.Start Stream4 Igmp | ${clip_name}                   |
        | STBRC.Send stbrc Changepage | ${stream_url}               |                                |
        | Streamer.Start Stream4 Igmp | testcard-4x3-480P60-H264.ts | die_on_already_running=${True} |
        """
        count = requests.get('http://stream4/%s?action=count' % (filename))

        if count.status_code == 200:
            logger.debug('Stream run count: %s' % (count.text))

            if die_on_already_running:
                if int(count.text) > 0:
                    raise RuntimeError('Stream is already running')

        logger.debug('Starting Stream: %s' % (filename))

        http = requests.get('http://stream4/%s?action=start' % filename)

        if http.status_code != 200:
            ret = False
            raise RuntimeError('Stream not started! %s' % filename)
        else:
            ret = 'igmp://%s:11111' % http.text
            logger.debug('Stream returned URL: %s' % ret)
            self._streams_started.append(filename)
        return ret

    def stop_stream4_igmp(self, filename):
        """     Stops a previously started stream

        Uses a single parameter to stop a stream started by the streamer library,
        the key word will warn if trying to stop a stream which was not started by
        this instance of the library

        Examples:
        | ${clip_name}=               | Set Variable                | testcard-4x3-480P60-H264.ts |
        | Streamer.Stop Stream4 Igmp  | ${clip_name}                |                             |
        """
        logger.debug('Stopping Stream: %s' % (filename))

        if not any(filename in s for s in self._streams_started):
            logger.warn('Stopping stream not started by this instance')

        http = requests.get('http://stream4/%s?action=stop' % filename)

        ret = False
        if (http.status_code != 200) or (http.text == 'NOT RUNNING'):
            logger.warn('Stream not Stopped! : %s' % filename)
        else:
            ret = True
            logger.debug('Stopped stream successfully!')
            self._streams_started.remove(filename)
        return ret

    def stop_all_stream4_igmp(self):
        """     Stops all streams started by this instance of the library

        Examples:
        | Streamer.Stop All Stream4 Igmp |
        """
        logger.debug('Stop All Stream4 Igmp called')

        tmp_streams = self._streams_started[:]

        for stream in tmp_streams:
            self.stop_stream4_igmp(stream)
            time.sleep(0.5)
