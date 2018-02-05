"""
EnableIni aminorobot module

Classes:
    EnableIni ( object ) - The Entone boot ini automation library
"""
# Robot libraries
from robot.api import logger
from robot.version import get_version

# Standard python libraries
import shutil
import os

__version__ = '0.1'

ROBOT_IGNORE_TAG = '<ROBOT_IGNORE_AFTER_THIS>'

class EnableIni(object):
    """ Amino EnableIni configuration library by Tim Curtis

    This library is designed for use with Robot Framework.

    Each interaction to the ini file should always read the ini file before
    the operation, and if the ini file contents have been changed, then the
    new contents should always be written out by the keyword, although it
    can be explicitly read or written using 'Read Ini File', and 'Write ini
    File'
    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self, ini_path=None, plat_prefix=None):

        # Absolute path to the ini file on disk
        self._ini_path = ini_path

        # Platform prefix, which replaces HDBCM in ini settings
        self._platform_prefix = plat_prefix

        # A container list for the lines of the ini file
        self._ini_lines = []
        self._ini_ignore = []

        # Settings in the ini file which should not be commented out
        self._comment_exceptions = []

        # Container for lines which have been commented out
        self._commented_lines = []

        # Flag set when reading the ini file, if the ignore tag is in use
        self._ignore_tag_in_use = False

    def __del__(self):
        """     On the destruct, restore the backup file, if it exists
        """

        self.restore_backup_file(quiet=True)

    def set_ini_path(self, path, make_file_backup=True):
        """     Set the entone boot ini path

        This keyword also checks the file exists, we have permission to read
        and to write to the file, without making modification to the ini file,
        using the os.access function.

        Examples:
        | ${ini_path}=                  | UUT.Get Property  | ini_path  |
        | EnableIni.Set Platform Prefix | ${ini_path}       |           |
        """

        # restore the existing path backup file, if it exists
        self.restore_backup_file(quiet=True)

        logger.debug('set_ini_path: Set ini path to {0}'.format(path))


        if not os.path.isfile(path):
            raise EnableIniError('No such file or directory: {0}'.format(path))


        try:
            if not os.access(path, os.R_OK):
                raise EnableIniError('No read permission for file: {0}'.format(path))

            if not os.access(path, os.W_OK):
                raise EnableIniError('No write permission for file: {0}'.format(path))
        except EnableIniError:
            #Change permission
            try:
                os.system("sudo chmod 666 %s" % path)
                logger.info("Added permission to read and write to file %s" % path)
            except:
                raise EnableIniError('No read/write permission for file: {0}'.format(path))



        if make_file_backup:
            ini_file_backup = '{0}.bak'.format(path)
            logger.debug('set_ini_path: ini file backup: {0}'.format(
                                                    ini_file_backup))

            try:
                shutil.copy(path, ini_file_backup)
            except IOError:
                logger.warn('set_ini_path: failed to create backup file')
        else:
            logger.info('set_ini_path: Not making ini file backup')

        self._ini_path = path
        self.comment_existing_ini_lines(only_after_ignore=True)


    def unset_ini_path(self):
        """     Unsets the ini path, largely just used to test the library

        Also, restores the current paths backup file, if it exists.

        Examples:
        | EnableIni.Unset Ini Path |
        """

        self.restore_backup_file()

        logger.debug('unset_ini_file: re-setting ini_path to None')

        self._ini_path = None

    def get_ini_path(self):
        """     Return the path for the entone boot ini file

        Examples:
        | ${ini_path}=  | EnableIni.Get Ini Path    |
        """

        return self._ini_path

    def set_platform_prefix(self, plat_prefix):
        """     Sets the library instance platform prefix

        This attribute can be fetched from the ESTB instance, from the family
        property, providing this is set in the estb_ definition file, and it
        is correct for the hardware under test.

        Examples:
        | ${family}=                    | UUT.Get Property      | family    |
        | EnableIni.Set Platform Prefix | ${family}             |           |
        """

        logger.debug('set_platform_prefix: {0}'.format(plat_prefix))

        self._platform_prefix = plat_prefix

    def get_platform_prefix(self):
        """     Return the platform prefix set in the library instance

        Examples:
        | ${platform_prefix}=   | EnableIni.Get Platform Prefix     |
        """
        return self._platform_prefix

    def read_ini_file(self):
        """     Read the lines of the ini file into self._ini_lines

        This will raise an exception if the path is not set in the
        library instance, or raise an exception if the user does not
        have sufficient permissions to read the ini file

        Examples:
        | EnableIni.Read Ini File   |
        """

        self._ignore_tag_in_use = False

        if not self._ini_path:
            raise EnableIniError('Trying to read file before the path is set')

        # Empty Ini Lines list
        self._ini_lines = []
        # Empty ini ignore list
        self._ini_ignore = []

        try:
            with open(self._ini_path, 'r') as ini_file:
                ini_lines = ini_file.readlines()

                past_ignore_tag = False

                for line in ini_lines:
                    if ROBOT_IGNORE_TAG in line:
                        past_ignore_tag = True
                        self._ignore_tag_in_use = True

                    if not past_ignore_tag:
                        self._ini_lines.append(line)
                    else:
                        self._ini_ignore.append(line)

        except IOError:
            raise EnableIniError('Failed to read entone boot ini')

    def write_ini_file(self):
        """     Write out self._ini_lines to the entone boot ini file

        Examples:
        | EnableIni.Write Ini File  |
        """

        if not self._ini_path:
            raise EnableIniError('Trying to write file before the path is set')

        if not self._ini_lines:
            raise EnableIniError('Trying to write nothing to the file')

        with open(self._ini_path, 'w') as ini_file:
            for line in self._ini_lines:
                ini_file.write(line)

            for line in self._ini_ignore:
                ini_file.write(line)

    def add_ini_item(self, ini_item, ini_value, is_variable=True):
        """     Adds an item to the entone_boot ini, or replaces it in the file
        if it is already present. All ini items will be wrapped with double
        quotes. If the item is present, and commented out, then the key word
        will uncomment the line, and change the value according to the params
        passed.

        Examples:
        | EnableIni.Add Ini Item  | DECODER_APP_FILE      | http://image.bin  |
        | EnableIni.Add Ini Item  | DECODER_APP_VERSION   | 1.2.3_ver_str     |
        """

        logger.debug('add_ini_item: ini_item: {0}'.format(ini_item))
        logger.debug('add_ini_item: ini_value: {0}'.format(ini_value))

        self.read_ini_file()

        var_replaced = False
        var_appended = False

        past_ignore_tag = False

        for ind, line in enumerate(self._ini_lines):
            if ROBOT_IGNORE_TAG in line:
                past_ignore_tag = True

            if (ini_item in line) and (line.replace(' ', '')[0] != '#'):
                if not past_ignore_tag:
                    logger.debug('Replacing line: {0}'.format(line))

                    if is_variable:
                        cur_item = line.split("=")[0]
                        new_ini_line = self._make_ini_line(ini_item, ini_value)
                        logger.debug('New Ini Line: {0}'.format(new_ini_line))

                        self._ini_lines[ind] =  new_ini_line

                        if not cur_item in self._ini_lines[ind]:
                            logger.warn('Setting replaced has been changed')

                        var_replaced = True

        if not var_replaced:
            # The specified ini item is not already in the ini file, add it
            self._ini_lines.append(self._make_ini_line(ini_item, ini_value))
            var_appended = True

        if not var_appended and not var_replaced:
            # We have not replaced a line, or appended something went wrong
            raise EnableIniError('Failed To add ini item: {0}'.format(ini_item))

        self.write_ini_file()

    def remove_ini_item(self, ini_item):
        """     Removes a single ini item from the entone_boot ini file

        Examples:
        | EnableIni.Remove Ini Item     | ITEM_TO_REMOVE            |
        | EnableIni.Remove Ini Item     | REMOVE_ANOTHER_SETTING    |
        """

        logger.debug('remove_ini_item: ini_item: {0}'.format(ini_item))

        self.read_ini_file()

        item_removed = False

        past_ignore_tag = False

        for ind, line in enumerate(self._ini_lines):

            if ROBOT_IGNORE_TAG in line:
                past_ignore_tag = True

            if (ini_item in line) and (line.replace(' ', '')[0] != '#'):
                if not past_ignore_tag:
                    logger.debug('remove_ini_item: removing: {0}'.format(line))

                    del self._ini_lines[ind]

                    item_removed = True
                else:
                    logger.debug('line found after ignore tag, not removed')


        if not item_removed:
            logger.debug('remove_ini_item: Item not removed')

        self.write_ini_file()

    def get_ini_file_as_string(self):
        """     Returns the whole ini file as a string

        Examples:
        | ${all_ini_file}=  | EnableIni.Get Ini File As String  |
        """

        self.read_ini_file()

        ret = ''
        ret += ''.join(self._ini_lines)
        ret += ''.join(self._ini_ignore)

        return ret


    def _make_ini_line(self, ini_item, ini_value):
        """     Generates an ini file variable line

        Parameters:
            ini_item  (str) the setting, without the platform prefix
            iti_value (str) The value fo the setting to be set
        Returns:
            str - line for the entone boot ini file in the format:
                $PREFIX_$ini_item="$ini_value"\n
        """

        logger.trace('_make_ini_line: {0} : {1}'.format(ini_item, ini_value))

        if not self._platform_prefix:
            raise EnableIniError('Attempted make ini line with no platform set')

        ret = '{0}_{1}="{2}"\n'.format(self._platform_prefix,
                                         ini_item, ini_value)

        logger.trace('_make_ini_item: returning: {0}'.format(ret))

        return ret

    def add_comment_exception(self, exception):
        """     Adds an exception to lines to be commented out of the ini file
        """

        self._comment_exceptions.append(exception)

    def clear_comment_exceptions(self):
        """     Removes all comment exceptions from the library instance
        """

        self._comment_exceptions = []

    def comment_existing_ini_lines(self, only_after_ignore=False):
        """     Comments out all existing ini lines not in comment exceptions
        """

        logger.debug('comment_existing_ini_lines: called')

        self.read_ini_file()

        if not only_after_ignore:
            self._ini_lines = self._comment_section(self._ini_lines)

        self._ini_ignore = self._comment_section(self._ini_ignore)

        self.write_ini_file()

    def uncomment_ini_lines(self):
        """     Uncomments the ini file lines which were commented out

        Examples:
        | EnableIni.Uncomment Ini Lines     |
        """

        logger.debug('uncomment_ini_lines: called')

        self.read_ini_file()

        if len(self._commented_lines) == 0:
            raise EnableIniError('Trying to uncomment 0 lines')
        else:

            self.read_ini_file()

            for comment in self._commented_lines:
                logger.trace('Uncommenting Line: "{0}"'.format(comment))

                for ind, line in enumerate(self._ini_lines):
                    if comment in line:
                        # Only removes the first char, assuming it is the hash
                        if line[0] == '#':
                            self._ini_lines[ind] = line[1:]

        # Should have uncommented all commented ini lines, clear the list
        self.clear_comment_exceptions()

        self.write_ini_file()

    def _comment_section(self, list_to_comment):
        """     Comments out a list of entone boot ini settings

        Each item in the list passed has a hash prepended, if it is not already
        commented and if it is not in the comment exceptions list. This is in
        it's own method, as there are 2 lists to comment out, which are before
        and after the global robot ignore tag.
        """

        adapted_list = list_to_comment

        past_ignore_tag = False

        for ind, line in enumerate(adapted_list):

            do_comment = True
            if line.replace(' ', '') == '\n':
                logger.trace('Line is empty, not commenting out')
                do_comment = False
            try:
                base_setting = '_'.join(line.split('_')[1:]).split('=')[0]
            except IndexError:
                # if we can't determine the base setting, then do nothing
                logger.trace('Line is not a setting, not commenting out')
                do_comment = False

            if ROBOT_IGNORE_TAG in line:
                past_ignore_tag = True

            if do_comment and (past_ignore_tag or not self._ignore_tag_in_use):
                logger.trace('BASE_SETTING: {0}'.format(base_setting))
                if base_setting not in self._comment_exceptions:
                    if line.replace(' ', '')[0] != '#':
                        # Only comment if not already commented out
                        logger.trace('Line to be commented: {0}'.format(line))

                        self._commented_lines.append(line)

                        adapted_list[ind] = '#{0}'.format(line)
                else:
                    logger.trace('Setting is an exception, not commenting out')

        return adapted_list

    def restore_backup_file(self, quiet=False):
        """     Restores the backup file to the original ini file path

        The ini path must be set and the backup file must exist for the move
        to take place. This method should not need to be called explicity, as
        the library should take care of making the backup and restoring it to
        the original path when it is finished with the file. Returns boolean
        True if the original file was restored, False if the original was not
        restored.

        Examples:
        | ${was_restored}=  | EnableIni.Restore Backup File     |
        """
        backup_path = '{0}.bak'.format(self._ini_path)

        if self._ini_path != None and os.path.isfile(backup_path):
            if quiet:
                logger.debug('restore_backup_file: restoring {0} to {1}'.format(
                                                backup_path, self._ini_path))
            else:
                logger.info('restore_backup_file: restoring {0} to {1}'.format(
                    backup_path, self._ini_path))

            shutil.move(backup_path, self._ini_path)

            if quiet:
                logger.debug('restore_backup_file: original file restored')
            else:
                logger.info('restore_backup_file: original file restored')
            return True

        else:
            if quiet:
                logger.debug('restore_backup_file: backup file not restored')
            else:
                logger.warn('restore_backup_file: backup file not restored')
            return False

    def output_ini_to_log(self, loglevel='INFO'):
        """  Print the contents of the current INI to the log at a chosen level
        Examples:
        | EnableIni.Output ini to log	|					|
        | EnableIni.Output ini to log	| loglevel='WARN'	|


        """
        inilog = self.get_ini_file_as_string()

        loglevel = loglevel.lower()

        try:
            exec ("logger.%s(\"\"\"%s\"\"\")" % (loglevel, inilog))
        except AttributeError:
            raise EnableIniError("Unknown log entry type: '%s'.  Use TRACE, DEBUG, INFO, WARN, CONSOLE")



    @staticmethod
    def get_app_tag_from_url(build_url):
        """     Get the app tag expected by the STB, from the full FTP URL

        This key word should be used primarily for upgrade downgrade soaks, to
        determine the build tag to be put into the DECODER_APP_VERSION ini
        setting, so that it does not have to be defined as a url and a tag

        Update: This keyword has been improved so it can obtain the correct string
        even if this is a compound binary or both app and a bootloader element.

        Examples:
        | ${BUILD_TAG_A}= | EnableIni.Get App Tag From Url | ${BUILD_URL_A} |
        | ${BUILD_TAG_B}= | EnableIni.Get App Tag From Url | ${BUILD_URL_B} |
        """



        ret = None

        if build_url.endswith('.bin'):

            if "DEVBUILD" in build_url:
                ret = '.'.join(build_url.split('/')[-1].split('.')[1:-3])
                ret = EnableIni._get_app_tag_from_compound_url(ret)

            else:
                ret = '.'.join(build_url.split('/')[-1].split('.')[1:-2])
                ret = EnableIni._get_app_tag_from_compound_url(ret)

        elif build_url.endswith('.aes.tar.gz'):
            ret = '.'.join(build_url.split('/')[-1].split('.')[1:-4])
            ret = EnableIni._get_app_tag_from_compound_url(ret)

        elif build_url.endswith('.tar.gz'):
            ret = '.'.join(build_url.split('/')[-1].split('.')[1:-3])
            ret = EnableIni._get_app_tag_from_compound_url(ret)
        else:
            raise EnableIniError("Unrecognised file type ('.bin', '.aes.tar.gz' and '.tar.gz' only)")
        return ret

    @staticmethod
    def _get_app_tag_from_compound_url(ret):
        # Need to handle compound app binaries that may have a PBL in also
        # Different for etv builds and mvn builds
        if "-mvn-" in ret:
            if ret.count('.') > 7:
                # Assume this is compound as it has more than seven dots in it
                logger.warn(
                    "This build string looks like a compound app and bootloader.  Trying to work out the correct tag....")
                mvn = ret.split("-mvn-")
                mvn[1] = '.'.join(mvn[1].split(".")[:4])
                ret = "-mvn-".join(mvn)
                logger.warn("The best guess for the tag is '%s'" % ret)


        elif "-etv-" in ret:
            if ret.count(".") > 4:
                # Assume this is a compound as it has more than 4 dots in it
                logger.warn(
                    "This build string looks like a compound app and bootloader.  Trying to work out the correct tag....")
                etv = ret.split("-etv-")
                etv[1] = etv[1].split(".")[0]
                ret = "-etv-".join(etv)
                logger.warn("The best guess for the tag is '%s'" % ret)

        elif "-zapper-" in ret:
            if ret.count(".") > 4:
                # Assume this is a compound as it has more than 4 dots in it
                logger.warn(
                    "This build string looks like a compound app and bootloader.  Trying to work out the correct tag....")
                zap = ret.split("-zapper-")
                zap[1] = zap[1].split(".")[0]
                ret = "-zapper-".join(zap)
                logger.warn("The best guess for the tag is '%s'" % ret)
        else:
            raise EnableIniError("This build string does not contain '-mvn-' or '-etv-' or '-zapper' so is not recognised.")

        return ret

    def get_bootloader_tag_from_url(self, build_url):
        """     Get the BBL/PBL/UFS tag expected by the STB, from the full FTP URL

        This key word should be used primarily for upgrade downgrade soaks, to
        determine the build tag to be put into the DECODER_APP_VERSION ini
        setting, so that it does not have to be defined as a url and a tag

        Examples:
        | ${BUILD_TAG_A}= | EnableIni.Get Bootloader Tag From Url | ${BUILD_URL_A} |
        | ${BUILD_TAG_B}= | EnableIni.Get Bootloader Tag From Url | ${BUILD_URL_B} |
        """


        ret = None

        if build_url.endswith('.bin'):
            ret = '.'.join(build_url.split('/')[-1].split('.')[1:-1])

        elif build_url.endswith('.aes.tar.gz'):
            raise EnableIniError("Bootloaders (BBL/PBL/UFS) must be .bin files")

        elif build_url.endswith('.tar.gz'):
            raise EnableIniError("Bootloaders (BBL/PBL/UFS) must be .bin files")

        return ret

class EnableIniError(RuntimeError):
    pass

