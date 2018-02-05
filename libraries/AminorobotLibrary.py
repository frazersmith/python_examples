# Robot libraries
from robot.version import get_version
from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn
from robot import utils

# Standard libraries
import errno
import os
import time
import datetime

# Memory leak checking
from pympler import muppy, summary
import types
import sys
import os
from contextlib import contextmanager


DEBUG=False


__version__ = "0.1 beta"


class AminorobotLibrary(object):
    """
    Abstract baseclass for Aminorobot Libraries providing generic functions.
    
    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()


    def __init__(self, working_directory=None, override_inherit=False):
        self.subclass = self.__class__.__name__
        self.running_outside_robot = None
        self.bounds_data = None
        self.debug = True if DEBUG else False
        self.mem_debug_counter = 0
        self.mem_file = None
        self.last_mem_stats = None






        if self.subclass == 'AminorobotLibrary':
            if not override_inherit:
                raise AminorobotLibraryError("This abstract class must be inherited.")
            else:
                self._log("Overriding the need to inherit AminorobotLibrary", 'warn' if DEBUG else 'info')

        try:
            outdir = BuiltIn().replace_variables('${OUTPUT_DIR}')
            suitename = BuiltIn().replace_variables('${SUITE_NAME}')
            self.running_outside_robot = False
        except Exception, e:
            if working_directory is None:
                self._log("Running library outside of aminorobot --- Using temp log location /tmp", 'warn' if DEBUG else 'info')
                outdir = "/tmp"
            else:
                self._makedir_p(working_directory)
                self._log("Running library outside of aminorobot --- Using custom working directory '%s'" % working_directory, 'warn' if DEBUG else 'info')
                outdir = working_directory


            suitename = "DEBUG"
            self.running_outside_robot = True

        self._outputpath = outdir
        self._suitename = suitename

    @contextmanager
    def redirect_stdout(self, new_target):
        old_target, sys.stdout = sys.stdout, new_target  # replace sys.stdout
        try:
            yield new_target  # run some code with the replaced stdout
        finally:
            sys.stdout = old_target  # restore to the previous value

    def output_memory_data(self, diff_only=False):

        self.mem_debug_counter += 1
        if self.mem_file is None:
            self.mem_file = os.path.join(self._outputpath, "memory_data.txt")

        sum = summary.summarize(muppy.get_objects())

        if not diff_only:
            with open(self.mem_file, 'a') as f:
                with self.redirect_stdout(f):
                    print "Outputting mem data '%s'" % str(self.mem_debug_counter)
                    summary.print_(sum)
                    print "\n\n"

        if not self.last_mem_stats is None:
            with open(self.mem_file, 'a') as f:
                with self.redirect_stdout(f):
                    print "Outputting mem diff '%s' vs '%s'" % (str(self.mem_debug_counter), str(self.mem_debug_counter-1))
                    diff = summary.get_diff(self.last_mem_stats, sum)
                    summary.print_(diff)
                    print "\n\n"

        self.last_mem_stats = sum

    def _log(self, msg, level='info'):
        if DEBUG or self.debug:
            print "LOG[%s]: %s" % (level.lower(), msg)

        level=level.lower()

        try:
            exec('logger.%s("""%s""")' % (level, msg))
        except AttributeError:
            raise AminorobotLibraryError("[%sError]: Incorrect Logging Level '%s'" % (self.subclass, level))

    @staticmethod
    def _slog(msg, level='info'):
        if DEBUG or level.lower() == 'debug':
            print "LOG[%s]: %s" % (level.lower(), msg)

        level=level.lower()

        try:
            exec('logger.%s("""%s""")' % (level, msg))
        except AttributeError:
            raise AminorobotLibraryError("[%sError]: Incorrect Logging Level '%s'" % ("[SharedMethod]", level))


    def _makedir_p(self,path):
        try:
            os.makedirs(path)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise AminorobotLibraryError("Unable to create path '%s'" % path)

    def convert_time_to_secs(self, time_in):
        """
        [Inherited from AminorobotLibrary]

        Accepts either a Robot TimeString (e.g. "3 minutes" or "1 day" etc) or an integer representing seconds and returns an integer representing seconds.

        :param time_in: Robot TimeString or Integer (seconds)
        :return: Integer (seconds)

        """
        try:
            return int(time_in)
        except ValueError:
            return utils.timestr_to_secs(time_in)

    def get_timestamp(self, for_filename=False):
        """     Get a timestamp for the current time
        """
        time_stamp = time.time()
        time_str = ""

        if for_filename:
            time_str = datetime.datetime.fromtimestamp(time_stamp).strftime(
                '%Y-%m-%d_%H-%M-%S.%f')[:-3]
        else:
            time_str = datetime.datetime.fromtimestamp(time_stamp).strftime(
                                            '%Y-%m-%d %H:%M:%S.%f')[:-3]
        return time_str

    def check_for_stop_notification(self):
        """
        Check if a file named 'STOP' exists in the outputdir.  This will gracefully end the test run with an AminorobotLibraryError

        Call this function from the main test at a suitable point, i.e. at the most frequent part of a multiple or nested loop

        NOTE: Avoid putting the call inside a try/except block to ensure it triggers a fatal error

        """
        if os.path.isfile("%s/STOP" % self._outputpath):
            raise AminorobotLibraryError("User STOP detected")


    """
    Data bounds.
    
    The '__setattr__' and '_check_bounds' methods, along with self.bounds_data provide a way to whitelist and/or blacklist and/or truthtable
    to validate any values which are set.
    
    For example, our AudioPresenceParameters class inherits from AminorobotLibrary, so every time an attribute is changed
    the __setattr__ method is called in it's super class.
    
    When called it checks through the self.bounds_data for a keyword that matches the attribute, for example 'testcriteria_channels'
    
    If, when __init__ is called on the AudioPresenceParameters class we set our bounds_data with either a whitelist, blacklist, truthtable or all
    it will test the validity of the 'value' against it.
        
    The bounds_data variable is a dict of keywords for the attributes to test, the value of which is a dictionary containing 
    'whitelist' for a list of lists of good values, or 'blacklist' for a list of lists of bad values, or 'truthtable' which is a list of strings
    that will be evaluated after replacing {value} with the value.
    
    e.g.
    
    self.bounds_data = {
        "testcriteria_channels":
            {"whitelist": [
                range(-1,200),[-3,-6,-7],
            ]},            
            {"blacklist": [
                [10,11],
            ]},
            {"truthtable": [
                "{value} > 100 and {value} < 200",
            ]},
    }       
    They are validated in the order: whitelist, blacklist, truthtable

    """

    def __setattr__(self, key, value):

        if key in self.__dict__:
            self._check_bounds(key, value)
            obj = self.__dict__.get(key)
            if obj and type(obj) is AminorobotLibrary:
                return obj.__set__(self, value)

        return super(AminorobotLibrary, self).__setattr__(key, value)

    def _check_bounds(self, key, value):

        try:
            if not self.bounds_data is None:
                pass
        except AttributeError:
            return

        if not self.bounds_data is None:

            if key in self.bounds_data.keys():

                if "whitelist" in self.bounds_data[key].keys():
                    in_whitelist = False
                    for whitevalues in self.bounds_data[key]["whitelist"]:

                        if value in whitevalues:
                            in_whitelist = True
                    if not in_whitelist:
                        raise AttributeError("Data bounds error.  Key '%s' does not accept value '%s'" % (str(key), str(value)))

                if "blacklist" in self.bounds_data[key].keys():
                    in_blacklist = False
                    for blackvalues in self.bounds_data[key]["blacklist"]:

                        if value in blackvalues:
                            in_blacklist = True
                    if in_blacklist:
                        raise AttributeError(
                            "Data bounds error.  Key '%s' does not accept value '%s'" % (str(key), str(value)))

                if "truthtable" in self.bounds_data[key].keys():

                    for truth in self.bounds_data[key]["truthtable"]:
                        if isinstance(value, basestring):
                            truth = truth.replace("'{value}'", value)
                        else:
                            truth = truth.replace("{value}", str(value))
                        if not (bool(eval(truth))):
                            raise AttributeError("Data bounds error.  Key '%s' does not meet truth '%s'" % (str(key), "%s %s" % (str(value), str(truth))))



class AminorobotLibraryError(RuntimeError):
    pass
