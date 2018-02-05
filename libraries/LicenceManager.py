"""
Classes:
    LicenceManager - Test library to test the AmiNET licence manager

Functions:
    _get_robot_lib_instance - gets an instance of a robot library
    _get_should_contains    - gets list of media events thatshould be seen
"""

# Robot Framework imports
from robot.api import logger
from robot.version import get_version
from robot.libraries.BuiltIn import BuiltIn
from robot.libraries.Dialogs import execute_manual_step

# Standard python imports
import time

# Aminorobot imports
from resources.variables.LicenceTestClips import FEATURES
from resources.variables.LicenceTestClips import MOUNT_COMMAND
from resources.variables.LicenceTestClips import MOUNT_HAS_KEY

TEST_PAGE_URL = 'http://qa-test2/testpages/auto/av/stream_test.html'
STB_LOG_FILE = '/mnt/nv/logfile.txt'

__version__ = '0.0'

class LicenceManager(object):
    """     Licence Manager aminorobot test library

    A group of keywords to test the licence file can be set in
    flash config, and that the consequent libconfig settings
    are honoured by mediad raising the correct media events
    based on whether the codecs are licenced or not.

    This library relies on having 2 other libraries initialised
    prior to importing this one, which is an instance of the STB
    library with the alias 'UUT' and an instance of the STBRC
    library with the alias 'STBRC'. The aliases can be overridden
    using the init named parameters 'stb_instance' and
    'stbrc_instance'
    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, stb_instance='UUT', stbrc_instance='STBRC'):
        self.uut = _get_robot_lib_instance(stb_instance)

        self.stbrc = _get_robot_lib_instance(stbrc_instance)

        self.feature_list = FEATURES.keys()

        self.hw_fam = None

        self._check_codecs()

        self.file_root = '/mnt/pc/test/%s' % (self.hw_fam)

    def get_testable_licence_list(self):
        """     Get a list of the codecs supported on the platform under test

        This is dictated by the logic in the _check_codecs method of the
        library. e.g. Ax5x does not support HEVC or 4K so they are not
        used for testing

        Examples:
        | @{TESTS}= | LM.Get Testable Licence List |            |           |
        | :FOR      | ${test}                      | IN         | @{TESTS}  |
        | \         | LM.Test Feature Licence      | ${test}    |           |
        """
        logger.debug('LM: get testable licence list')

        return self.feature_list

    def list_licence_stats(self):
        """     Development test method to list codecs available

        Quick checker to ensure the data is imported correctly and
        the url and types of each codecs are available.

        Examples:
        | LM.List Licence Stats |
        """
        for feature in self.feature_list:
            logger.debug('Feature: %s' % (feature))
            for inf in FEATURES[feature].keys():
                logger.debug('attr: %s val: %s' % (inf, FEATURES[feature][inf]))

    def test_feature_licence(self, feature_name, manual_check=False):
        """
        docstring
        """

        logger.debug('LM: testing feature licence "%s"' % (feature_name))

        self.uut.login_and_keep_telnet_open()

        self._clear_media_events_file()

        is_licensed = self.get_is_feature_licensed(feature_name)

        try:
            feature_type = FEATURES[feature_name]['type']
            feature_url = FEATURES[feature_name]['url']
        except KeyError:
            logger.warn('LM: unable to test feature: %s' % (feature_name))
            return

        self._clear_media_events_file()

        self.stbrc.send_stbrc_changepage("%s?src=%s" %
                                         (TEST_PAGE_URL, feature_url))

        logger.debug('LM: sleeping for 10 seconds to allow stream to start')
        time.sleep(10)

        should_contains = _get_should_contains(feature_type, is_licensed)
        media_events = self.uut.send_command_and_return_output('cat %s' %\
                                                               (STB_LOG_FILE))

        event_has_fired = False
        for event in should_contains:
            if event in media_events:
                event_has_fired = True

        if not event_has_fired:
            if not 'DATA_STARTED' in media_events:
                logger.warn('LM: No data in stream %s' % feature_url)
            else:
                mesg = 'LM: missing media event for %s licensed:%s event:%s' % \
                       (feature_name, is_licensed, str(should_contains))
                logger.warn(mesg)
                BuiltIn().fail(mesg)

        if manual_check:
            if is_licensed == 'Y':
                is_msg = 'should'
            elif is_licensed == 'N':
                is_msg = 'should not'

            manual_msg = 'TEST for licenced feature: %s\n\n' % (feature_name)
            manual_msg += '%s should %s be playing' % (feature_type, is_msg)

            execute_manual_step(manual_msg, 'Manual licence failed')

        self._clear_media_events_file()

    def get_is_feature_licensed(self, feature_name):
        """     Get the libconfig value for a feature licence

        Returns the value of the libconfig LICENCE.xxx using libconfig-get
        using the send_libconfig_get_command method from the STB library.

        Parameter feature_name must just be the feature name, as is it in
        libconfig

        Examples:
        | ${HEVC_LICENCE}=   | LM.Get Is Feature Licenced   | HEVC      |
        | ${MPEG_2_LICENCE}= | LM.Get Is Feature Licenced   | MPEG_2    |
        """

        logger.debug('LM: getting feature licence: %s' % (feature_name))

        ret = self.uut.send_libconfig_get_command('LICENCE.%s' % (feature_name))

        logger.debug('LM: LICENCE.%s = "%s"' % (feature_name, ret))

        return ret

    def _check_codecs(self):
        """     Removes unsupported codecs based on the hardware family

        Args:
            None
        Returns:
            Nothing
        """
        self.hw_fam = self.uut.get_property('family')

        if self.hw_fam == 'Ax5x':
            logger.debug('LM: platform is Ax5x, removing [HEVC, 4K]')
            self.feature_list = [x for x in self.feature_list if x != 'HEVC']
            self.feature_list = [x for x in self.feature_list if x != '4K']
        elif self.hw_fam == 'Ax6x':
            logger.debug('LM: platform is Ax6x, removing [4K]')
            self.feature_list = [x for x in self.feature_list if x != '4K']

    def set_licence_file(self, file_name):
        """
        licence_file_name needs to be relative to
        it-000390:/nfs/<hmfamily>/licence/
        e.g.
        licence file is:
        it-000390:/nfs/Ax5x/licence/factory-licence-no-audio.signed

        so parameter would be:
        'factory-licence-no-audio.signed'
        """
        self.uut.send_commands('/etc/init.d/rc.opera stop')

        self.uut.send_commands(MOUNT_COMMAND)

        has_key = self.uut.send_commands(MOUNT_HAS_KEY)

        if (has_key[0] == '1') or (has_key[0] == 1):
            logger.warn('LM: No licence key found! tests wont work!')
            raise RuntimeError('No Licence key')

        set_lic = self.uut.send_commands(self._make_licence_set_cmd(file_name))

        if set_lic[0] != '0':
            raise RuntimeError('LM: Failed to set licence file!!!')
        else:
            self._safe_reboot()
            time.sleep(2.5)

    def _get_licence_hex_location(self):
        """     Gets the hex location of LICENCE_FILE in flash_config

        Args:
            None
        Returns:
            (str)  - hex location on success else raises RuntimeError
        """

        if self.hw_fam == 'Ax5x':
            return '0x011E3F1E'
        else:
            raise RuntimeError('LM: Unsupported hw family!')

    def _make_licence_set_cmd(self, file_name):
        """         Makes the command to set the licence file using flash_config

        It pulls together the absolute path to the flash_config binary based on
        the platform under test, the hex location of the licence file in
        flash_config, and the licence file name.

        Args:
            file_name (str) - the name of the file, relative to
                              it-000390:/nfs/<platform>/licence/
        Returns:
            command   (str) - full command to set the licence file
        """
        logger.debug('LM: making set command for file: %s' % file_name)

        command = ''
        command += '%s/flash_config set ' % (self.file_root)
        command += '%s ' % (self._get_licence_hex_location())
        command += 'file:%s' % (self.file_root)
        command += '/licence/%s' % (file_name)

        logger.debug('LM: created command: %s' % (command))

        return command

    def _safe_reboot(self):
        """     Does a STB reboot, ensuring no unexpected files are on NAND

        Args:
            None
        Returns:
            Nothing
        """
        logger.debug('LM: Doing safe STB reboot')

        self.stbrc.send_stbrc_changepage('http://qa-test2')
        self._clear_media_events_file()
        self.uut.close_all_but_debug()
        self.uut.reboot_stb()

    def _clear_media_events_file(self):
        """
        docstring
        """
        self.uut.send_commands('rm -f %s' % (STB_LOG_FILE))

def _get_robot_lib_instance(instance_name):
    """     Returns an object of a robot library instance, based on it's alias

    Args:
        instance_name (str) - The alias of the library to get, for example the
                              STB library is often aliased to 'UUT'
    Returns:
        ret           (obj) - The robot library instance object, public methods
                              are then available to the Licence manager library
                              via the library instance variable
    """

    logger.debug('LM: Getting STB lib instance name %s' % instance_name)

    ret = None

    try:
        ret = BuiltIn().get_library_instance(instance_name)
    except RuntimeError:
        logger.warn('LM: Failed to get libary instance: %s' % instance_name)
    return ret

def _get_should_contains(feature_type, is_licensed):
    """     Gets a list of events which should be seen on attempting playback

    Gets a list of media events based on the type of codec being tested and
    if that particular codec is licenced.

    Args:
        feature_type (str) - type of codec beign tested 'audio' and 'video'
        is_licensed  (str) - is codec under test licenced according to the
                             'Y' or 'N' libconfig LICENCE key
    """
    ret = []

    if is_licensed == 'N':
        if feature_type == 'video':
            ret.append('UNSUPPORTED_VIDEO_CODEC')
        elif feature_type == 'audio':
            ret.append('UNSUPPORTED_AUDIO_CODEC')

    elif is_licensed == 'Y':
        if feature_type == 'video':
            ret.append('VIDEO_STARTED')
        elif feature_type == 'audio':
            ret.append('AUDIO_STARTED')

    if len(ret) == 0:
        logger.debug('LM: unable to determine media events')
    else:
        logger.debug('LM: Should hear events: %s' % str(ret))

    return ret
