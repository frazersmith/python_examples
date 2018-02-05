# Robot libraries
from robot.api import logger
from robot.version import get_version
from robot import utils
from robot.libraries.BuiltIn import BuiltIn

# Standard libraries
import time
import math

__version__ = "0.1 beta"

class Chrono(object):

    """ Amino Chrono Library by Frazer Smith.

    This library is designed for use with Robot Framework.

    It provides unlimited timers and countdown.

    'Countdown' counts down to zero then expires.  It can be started, checked for 
    expiry or read for what remains.

    A 'Timer' is a classic stopwatch.  It can be started and read.

    Any number of timers and countdowns may exist as they are all defined by a tag name

   
    """

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()

    def __init__(self):
        self._t = {} #Dictionary of timers
        self._c = {} #Dictionary of countdowns


    def start_countdown(self, tag, duration):
        """  Start (or restart) a countdown with a tag name

        Example:-
        | Start Countdown	| ThisCountdown	| 3 minutes	|

        """        
        expiry = utils.timestr_to_secs(duration) + time.time()
        self._c[tag]=expiry

    def _checkexists(self, tag, dictionary):
        if not tag in dictionary:
            raise ChronoError("Tag '%s' does not exist" % tag)

    def countdown_has_expired(self, tag):
        """  Returns a boolean value checking if the defined countdown (by tag name)
        has expired

        Example:-
        | ${ret}	| Countdown Has Expired	| MyCountdown	|

        """        
        self._checkexists(tag, self._c)
        if time.time() >= self._c[tag]:
            return True
        else:
            return False

    def countdown_remaining(self, tag, timestring=True):
        """  Returns the remaining time in a countdown, by tag name

        The return is a Robot 'Time String' by default but can be float if required

        Examples:-
        | ${retstring}	| Countdown Remaining	| MyCountdown	|			|
        | ${retsecs}	| Countdown Remaining	| MyCountdown	| timestring=${False}	|

        """            
        self._checkexists(tag, self._c)
        ret = self._c[tag] - time.time()
        if ret <= 0:
            if timestring:
                return "Expired"
            else:
                return 0
        else:
            if timestring:
                return utils.secs_to_timestr(ret)
            else:
                return self._round(ret)

    def start_timer(self, tag):
        """  Start (or restart) a timer with a tag name

        Example:-
        | Start Timer	| ChannelChangeTimer	| 


        """    
        self._t[tag] = time.time()

    def read_timer(self, tag, timestring=True):
        """  Read the current timer value by tag name

        The return is a Robot 'Time String' by default but can be float if required
 
        Examples:-
        | ${retstring}=	| Read Timer	| ChannelChangeTimer	| 			|
        | ${retsecs}=	| Read Timer	| ChannelChangeTimer	| timestring=${False}	|


        """    
        self._checkexists(tag, self._t)
        if timestring:
            return utils.secs_to_timestr(time.time() - self._t[tag])
        else:
            return self._round(time.time() - self._t[tag])

    def _round(self, value):
        return (math.ceil(value*1000)/1000)
  
class ChronoError(RuntimeError):
    pass

