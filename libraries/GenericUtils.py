"""
GenericUtils.py

This library is intended as a catch all for python functions we want to use as
robot key words, but do not belong in any of the other libraries.
"""

from robot.api import logger

import subprocess

from datetime import datetime
from dateutil import parser

TEST_TIME = 'Thu Jul  7 20:43:46 GMT+8 2016'
DATE_FMT = '%a %b  %d %H:%M:%S %Z %Y'

# Sets functions which we can use as robot key words
__all__ = ['verify_a_timezone']

def verify_a_timezone(posix_str, date_output):
    """

    NOTE: we use the shell `date` command as it provides the date time
    string in the same format as comes from the STB, using datetime.now
    with a time zone specified is unreliable compared to this method.

    Examples:
    | ${stb_date}=    | Send Command and return output |      |               |
    | ${right_time}=  | Verify A Timezone     | Etc/GMT+2     | ${stb_date}   |
    """

    logger.debug('verify_a_timezone: %s %s' % (posix_str, date_output))

    proc = subprocess.Popen(['TZ=%s date' % posix_str],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, shell=True)

    out = proc.communicate()[0]

    local_time = _get_a_time_obj(out.replace('\n', ''))
    stb_time = _get_a_time_obj(date_output)

    logger.debug(local_time)
    logger.debug(stb_time)

    diff = local_time - stb_time

    logger.debug('seconds diff: {}'.format(diff.total_seconds()))

    # Allow for a 10 minute difference in time, positive or negative
    return diff.total_seconds() < 60 * 10 and diff.total_seconds() > -(60 * 10)

def _get_a_time_obj(time_str):
    """     Returns a datetime object, need to try 2 methods, as not
    all variants of posix time zones work with both.
    """

    try:
        ret = datetime.strptime(time_str, DATE_FMT)
    except ValueError:
        ret = parser.parse(time_str)

    return ret


if __name__ == '__main__':
    verify_a_timezone('Etc/GMT+8', TEST_TIME)
