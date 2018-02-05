class PythonTestWrapperError(RuntimeError):
    pass

DEBUG=False

from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn
from robot.version import get_version


class PythonTestWrapper(object):

    """
    PythonTestWrapper by Frazer Smith

    Allows you to write tests in python and run them through AminoRobot.

    If you are able to code in Python the Robot Framework scripting language will seem cumbersome
    and lacking in features.  Using this wrapper and this documentation you can write your tests
    in Python and still call them with the same Suite/Test structure, tags and reporting methods
    of Robot Framework.

    It is important to understand how to make use of Suite Setup/Teardown, tags, libraries and
    variables.

    == Getting Started ==
    You will need a python file containing a python class (which inherits PythonTestWrapper)
    with the same name which contains your tests as functions.  For example, create MyPythonTests.py,
    declare 'class MyPythonTests(PythonTestWrapper):' and have functions in that class like
    'def this_is_a_test(self):'.  Additionally, you can add functions to your class that you
    will call for Suite Setup and Suite Teardown.

    [MyPythonTests.py]
    | from libraries.PythonTestWrapper import PythonTestWrapper
    | from robot.version import get_version
    | from robot.libraries.BuiltIn import BuiltIn
    |
    | class MyPythonTests(PythonTestWrapper):
    |
    |   ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    |   ROBOT_LIBRARY_VERSION = get_version()
    |
    |   def __init__(self):
    |       PythonTestWrapper.__init__(self)
    |
    |   def S_SETUP(self):
    |       # Get the UUT object (or any other that you need to setup BY NAME)
    |       uut = self.get_lib_instance('UUT')
    |       uut.capture_debug()
    |
    |   def S_TEARDOWN(self):
    |       # Get the UUT object (or any other that you need to setup BY NAME)
    |       uut = self.get_lib_instance('UUT')
    |       uut.close_all()
    |
    |   def this_is_a_test(self):
    |       # Do some stuff
    |       pass
    |

    You will still need to create a test suite in ride which imports your MyPythonTests as a library
    (and giving it an alias):-

    [MyPythonTestSuite.txt]
    | *** Settings ***
    | Suite Setup       S_SETUP
    | Suite Teardown    S_TEARDOWN
    | Library           MyPythonTests.py    WITH NAME    PyTests
    | Library           ../../resources/devices/${uut}.py    WITH NAME    UUT
    |
    | *** Variables ***
    | ${uut}            estb_a1b2c3
    |
    | *** Test Cases ***
    | Run_A_Test
    |   [Tags]    PY9999
    |   PyTests.This Is A Test
    |

    In our example we create the ${uut} variable to allow us to load the correct device file (our standard way
    of defining a uut).  This device is instantiated with the alias UUT.

    In our python S_SETUP and S_TEARDOWN we grab the instance of UUT so we can start and stop debug capture.
    You can do the same in any test with any library that is instantiated, or even import the library
    directly into you python file.  Common robot libraries are:-

    robot.api
    robot.libraries.*
    robot.utils


    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()



    @property
    def suite_variables(self):
        return BuiltIn().get_variables()

    def __init__(self):
        pass



    def get_lib_instance(self, input):
        """

        Use this wrapper method to get an instance of an object/library passed to the script as a parameter

        It will accept either an alias or an instance, and return an instance

        Examples:
            stb = self.get_lib_instance('UUT')

        """

        return self._use_alias_or_instance(input)


    def _use_alias_or_instance(self, input):

        try:
            ret = BuiltIn().get_library_instance(input)
            logger.trace("Passed object '%s' is an alias" % str(input))
        except (AttributeError):
            logger.trace("Passed object '%s' is an instance" % str(input))
            ret = input

        return ret

    def log(self, msg, level='info'):
        """
        Output a message to robot logger and optionally to debug.

        :param msg: The message to output
        :param level: from 'WARN','INFO','DEBUG','TRACE' (not case sensitive)

        """
        if DEBUG:
            print "LOG[%s]: %s" % (level.lower(), msg)

        level=level.lower()

        if level not in ['warn','info','debug','trace']:
            logger.warn("Unrecognised Log Level '%s'.  Assuming 'INFO'" % level.upper())
            level='info'

        try:
            exec('logger.%s("""%s""")' % (level, msg))
        except AttributeError:
            raise PythonTestWrapperError('Incorrect Logging Level' % level)

    def get_suite_variable(self, name):

        """
        Use get_suite_variable to access any variable with Suite scope, i.e. defined in the 'suite' biew in ride
        for example ${uut}

        :param name: variable name in the form ${....}
        :return: the value of that variable

        If the variable is not found an error will be raised
        """

        if (name[:2] <> "${") or (name[-1:] <> "}"):
            raise PythonTestWrapperError("Incorrect variable format '%s'.  Must be like '${variable}'" % name)

        vars = self.suite_variables

        if name not in vars.keys():
            raise PythonTestWrapperError("Variable not found - '%s'" % name)
        else:
            return vars['%s' % name]

