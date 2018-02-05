import serial
import threading
import time
import datetime
import os.path
import os
import gzip
import re

from robot.libraries.BuiltIn import BuiltIn

try:
    import pyte
except ImportError:
    pyte = None

from robot.api import logger
from robot import utils
import time

class Debug(object):
    def __init__(self, timeout='3 seconds', newline='\r\n',
                 prompt=None, prompt_is_regexp=False,
                 encoding='UTF-8', encoding_errors='ignore',
                 default_log_level='INFO', window_size='400x100',
                 environ_user=None, terminal_emulation=True,
                 terminal_type="vt100", appendsuffix=None,
                 login="root", password="root2root", tryalternativepasswords=False):

        self._appendsuffix = appendsuffix
        self._timeout = timeout or 3.0
        self._newline = newline or 'CRLF'
        self._prompt = (prompt, bool(prompt_is_regexp))
        self._encoding = encoding
        self._encoding_errors = encoding_errors
        self.__encoding = (encoding.upper(), encoding_errors)
        self._default_log_level = default_log_level
        self._window_size = self._parse_window_size(window_size)
        self._environ_user = environ_user
        self._terminal_emulation = self._parse_terminal_emulation(terminal_emulation)
        self._terminal_type = terminal_type
        self._cache = utils.ConnectionCache()
        self._conn = None
        self._conn_kws = self._lib_kws = None
        self._terminal_emulator = self._check_terminal_emulation(terminal_emulation)
        self._connected = False
        self._outputfile = None
        self._loggedin = False
        self._outputfilequeued = False
        self._redirect_debug = False
        self._buffer_debug = False
        self._rx_buffer = ""
        self._listeners = ['Kernel panic']
        self._lockfilename = None
        self._listeners_heard = []
        self._login = login
        self._password = password
        self._lastread = time.time()
        self._alterative_passwords = ['3n#^(^^#ton3cp3', 'entonehd']
        self._tryalternativepasswords = tryalternativepasswords

        try:
            outdir = BuiltIn().replace_variables('${OUTPUTDIR}')
            testname = BuiltIn().replace_variables('${SUITENAME}')
        except:
            print "Running library outside of aminorobot --- Using temp log location /tmp/DEBUG_debug.log"
            outdir = "/tmp"
            testname = "DEBUG"

        self._outputpath = os.path.join(outdir, testname + '_' + self._appendsuffix + '_debug.log').replace(' ','_')

    def _parse_window_size(self, window_size):
        if not window_size:
            return None
        try:
            cols, rows = window_size.split('x')
            cols, rows = (int(cols), int(rows))
        except:
            raise AssertionError("Invalid window size '%s'. Should be <rows>x<columns>" % window_size)
        return cols, rows

    def _parse_terminal_emulation(self, terminal_emulation):
        if not terminal_emulation:
            return False
        if isinstance(terminal_emulation, basestring):
            return terminal_emulation.lower() == 'true'
        return bool(terminal_emulation)


    def get_time_since_last_read(self):
        # This will return a time value which is the difference between now and the last read available
        # It will raise an error if the debug connection is closed
        if not self._connected:
            raise DebugError("Can't get time since last read as the debug capture is closed.")
        else:
            now = time.time()
            return now - self._lastread


    def open_connection(self, commport="/dev/ttyUSB0", baud="115200", appendsuffix=None, prompt="[root@AMINET]#", compressed=False, prompt_regex=False):
        self._prompt = prompt
        self._prompt_regex = prompt_regex

        logger.debug("prompt=%s, prompt_regex=%s"  % (prompt, str(prompt_regex)))

        if self._lockfile("exists", commport):
            raise DebugError("Unable to open port on %s as a lockfile exists in /var/lock" % commport)
        try:
            self._conn = serial.Serial(commport, baud)
        except:
            raise DebugError("Error occured trying to open serial port on %s" % commport)

        self._connected = True
        try:
            self._lockfile("create",commport)
        except:
            raise DebugError("Error occured trying to create lockfile for port %s" % commport)

        if compressed:
            self._outputpath = self._outputpath + ".gz"
            self._outputfile = gzip.open(self._outputpath, 'a')
        else:
            self._outputfile = open(self._outputpath, 'a')

        self._readthread = threading.Thread(target=self.read_thread)
        self._readthread.start()


    def _lockfile(self, action, commport):
        comm = commport.split("/")
        comm = comm[len(comm)-1]
        lockfile = "/var/lock/LCK..%s" % comm
        if action == "exists":
            if os.path.exists(lockfile):
                return True
            else:
                return False
        elif action == "create":
            try:
                with open(lockfile, 'a') as f:
                    f.write("     %s\n" % str(os.getpid()))
                self._lockfilename = lockfile
            except:
                raise DebugError("Unable to create serial port lock file %s" % lockfile)
        else:
            try:
                lockfile = str(self._lockfilename)
                os.remove(lockfile)
                self._lockfilename = None
            except Exception as e:
                logger.warn("Unable to remove lock file %s, with error %s" % (lockfile, str(e)))

    def debug_marker(self, text):
        try:
            self._outputfilequeued = True #Hold any further debug until this is written
            self._outputfile.write("\n\n**********************************\nMarker:  %s\n**********************************\n\n" % text)
            self._outputfilequeued = False
        except ValueError:
            logger.warn("Unable to write debug marker as debug output file appears to be closed!")

    def write(self, command):
        self._conn.write(command + "\n")

    def send_login(self):
        """     Sends the login user followed by the password
                If the tryalternativepasswords flag is set it will also try alternatives
        """

        try:
            self.write('\n')
            time.sleep(1)
            self.write(self._login)
            time.sleep(1)
            self._write_and_wait_for_prompt(self._password, '5 seconds')
        except DebugError:
            # Login failed
            if self._tryalternativepasswords:
                #try list of alternative passwords
                logger.info("Password for console did not work, trying list of alternatives")
                for password in self._alterative_passwords:
                    try:
                        self.write('\n')
                        time.sleep(1)
                        self.write(self._login)
                        time.sleep(1)
                        self._write_and_wait_for_prompt(password, '5 seconds')
                        logger.info("Alternative password worked")
                    except DebugError:
                        pass

            else:
                pass








    def send_command(self, command, suppresslogin=False, timeout="30 seconds"):
        try:
            if not suppresslogin:
                self.send_login()

            self._write_and_wait_for_prompt("", "5 seconds")
        except DebugError:
            if not suppresslogin:
                try_count = 0

                while try_count < 5:
                    logger.trace('login attempt: %s' % (try_count))
                    try:
                        self.send_login()
                        try_count = 10
                    except DebugError:
                        try_count += 1
                        time.sleep(1)

                if try_count == 4:
                    raise DebugError('Failed to login after 5 attempts!')

        self._write_and_wait_for_prompt(command, timeout)

    def _write_and_wait_for_prompt(self, command, timeout, attempt=0):
        self._buffer_debug = True
        self._rx_buffer = ""
        self.write(command)
        tout = 2 * utils.timestr_to_secs(timeout)
        halfseccount = 0

        while halfseccount <= tout:
            if not self._prompt_regex:

                if self._prompt in self._rx_buffer:
                    self._buffer_debug = False
                    self._rx_buffer = ""
                    return
                else:
                    time.sleep(0.5)
                    halfseccount = halfseccount + 1
            else:
                if re.search(self._prompt, self._rx_buffer) is not None:
                    self._buffer_debug = False
                    self._rx_buffer = ""
                    return
                else:
                    time.sleep(0.5)
                    halfseccount = halfseccount + 1

                # Pass newlines down the serial connection to have a better
                # chance of seeing the prompt
                self.write('')

        # Last ditch on the enable stack, try sending CTRL-C as if logread -f
        #  is running in the foreground NOTE: '\x03' is ASCII for CTRL-C
        if (self._prompt_regex) and (attempt < 2):
            logger.debug('CTRL-C attempt number: %s' % attempt)
            self.write('\x03')

            new_attempt = attempt + 1
            self._write_and_wait_for_prompt(command, '5 seconds', attempt=new_attempt)


        raise DebugError("Timeout waiting for prompt %s" % self._rx_buffer)


    def send_command_and_return_output(self, command, prompt, timeout, regex=False):
        command = str(command)

        self._redirect_debug = True

        if not regex:
            # Running on AmiNET, need to stop syslog from the Debug library
            self.write('/etc/init.d/rc.syslogd stop;echo ******* STOPPING LOGGING TO SEND COMMAND ***********')

        time.sleep(2)
        self._rx_buffer = ""
        self.write(command)
        tout = 2 * utils.timestr_to_secs(timeout)
        halfseccount = 0
        logger.trace("rx_buffer 1 = '%s'" % self._rx_buffer)

        while halfseccount <= tout:
            if regex:
                logger.trace("rx_buffer 2 = '%s'" % self._rx_buffer)
                if len(re.findall(prompt, self._rx_buffer)) > 0:
                    logger.trace("rx_buffer 3 = '%s'" % self._rx_buffer)
                    self._redirect_debug = False

                    try:
                        logger.debug(self._rx_buffer)
                        return re.sub(prompt, '', self._rx_buffer)
                    except:
                        # If removing the prompt fails, return the whole buffer
                        return self._rx_buffer

                else:
                    time.sleep(0.5)
                    halfseccount = halfseccount + 1
                    self.write('')
            else:
                # Support old AmiNET method of finding the prompt
                if prompt in self._rx_buffer:
                    self._redirect_debug = False
                    self.write('/etc/init.d/rc.syslogd start;echo *******RESTARTED LOGGING AFTER SEND COMMAND AND RECEIVE OUTPUT***********')
                    logger.trace("rx_buffer = '%s'" % self._rx_buffer)
                    try:
                        return self._rx_buffer.split('%s' % command)[1].split(prompt)[0]
                    except:
                        return self._rx_buffer.split(prompt)[0]


                  #return self._strip_rx(self._rx_buffer, command, prompt)
                else:
                    time.sleep(0.5)
                    halfseccount = halfseccount + 1

        raise DebugError("Timeout waiting for prompt")


    def _strip_rx(self, rx_buff, command, prompt):
        return rx_buff.split('%s\n' % command)[1].split(prompt)[0]


    def add_listener(self, listener):
        self._listeners.append(listener)

    def close(self):
        self._connected = False
        self._readthread.join()
        self._conn.close()
        if self._lockfilename != None:
            self._lockfile("close","")
        self._outputfile.close()

    def __debuglog(self, log):
        with open('/tmp/somedebug.txt', 'a') as f:
            f.write("%s\n" % log)

    def _check_listeners(self, output):
        # Check if a listener is heard
        heard = []
        for listener in self._listeners:
            if listener in output:
                heard.append(listener)

        if len(heard) > 0:
            # Found at least one of them, lets add the instances to the list of heards
            for line in output.split('\n'):
                for listener in heard:
                    if listener in line:
                        self._listeners_heard.append("Listener '%s' heard at %s : %s" % (listener, self._get_timestamp(), line))

    def check_listeners(self):
        if len(self._listeners_heard) > 0:
            return '\n'.join(self._listeners_heard)
        else:
            return ""

    def connected(self):
        return self._connected


    def _get_timestamp(self):
        time_obj = time.time()
        time_str = datetime.datetime.fromtimestamp(time_obj).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        return time_str


    def _handle_read(self, output):
        # Need a string buffer to keep in memory, plus a file to write to
        self._check_listeners(output)

        # IMPROVEMENT improve this by keeping the last 'output' in memory and appending them together to check if a listener fired between buffers?
        # may be problematic if more than one instance is picked up?  It will definately be picked up twice on consecutive checks?

        self._lastread = time.time()


        while self._outputfilequeued == True:
            pass
        if not self._redirect_debug:
            self._outputfile.write(output)
            if self._buffer_debug:
                self._rx_buffer = self._rx_buffer + output
        else:
            self._rx_buffer = self._rx_buffer + output

    def _log(self, msg, level=None):
        msg = msg.strip()
        if msg:
            logger.write(msg, level or self._default_log_level)

    def read_thread(self, loglevel=None):
        while self._connected:
            time.sleep(0.2)
            #self._verify_connection()
            try:
                if self._conn.inWaiting() > 0:
                    output = self._conn.read(self._conn.inWaiting())
                    if self._terminal_emulator:
                        self._terminal_emulator.feed(output)
                        # Removed newline rstrip to solve multi-line issue
                        self._handle_read(self._terminal_emulator.read())
                    else:
                        self._handle_read(output = self._decode(output))
            except:
                pass

    def _decode(self, rx_bytes):
        if self.__encoding[0] == 'NONE':
            return rx_bytes
        return rx_bytes.decode(*self.__encoding)

    def _check_terminal_emulation(self, terminal_emulation):
        if not terminal_emulation:
            return False
        if not pyte:
            raise RuntimeError("Terminal emulation requires pyte module!\n"
                               "https://pypi.python.org/pypi/pyte/")
        return TerminalEmulator(window_size=self._window_size,
                                newline=self._newline, encoding=self.__encoding)

    def open_connection_old(self, host, alias=None, port=23, timeout=None,
                        newline=None, prompt=None, prompt_is_regexp=False,
                        encoding=None, encoding_errors=None,
                        default_log_level=None, window_size=None,
                        environ_user=None, terminal_emulation=True,
                        terminal_type="vt100"):
        """Opens a new Telnet connection to the given host and port.

        The `timeout`, `newline`, `prompt`, `prompt_is_regexp`, `encoding`,
        `default_log_level`, `window_size`, `environ_user`,
        `terminal_emulation`, and `terminal_type` arguments get default values
        when the library is [#Importing|imported]. Setting them here overrides
        those values for the opened connection. See `Configuration` and
        `Terminal emulation` sections for more information.

        Possible already opened connections are cached and it is possible to
        switch back to them using `Switch Connection` keyword. It is possible
        to switch either using explicitly given `alias` or using index returned
        by this keyword. Indexing starts from 1 and is reset back to it by
        `Close All Connections` keyword.
        """
        timeout = timeout or self._timeout
        newline = newline or self._newline
        encoding = encoding or self._encoding
        encoding_errors = encoding_errors or self._encoding_errors
        default_log_level = default_log_level or self._default_log_level
        window_size = self._parse_window_size(window_size) or self._window_size
        environ_user = environ_user or self._environ_user
        terminal_emulation = self._get_terminal_emulation_with_default(terminal_emulation)
        terminal_type = terminal_type or self._terminal_type
        if not prompt:
            prompt, prompt_is_regexp = self._prompt
        logger.info('Opening connection to %s:%s with prompt: %s'
                    % (host, port, prompt))
        self._conn = self._get_connection(host, port, timeout, newline,
                                          prompt, prompt_is_regexp,
                                          encoding, encoding_errors,
                                          default_log_level, window_size,
                                          environ_user, terminal_emulation,
                                          terminal_type)
        return self._cache.register(self._conn, alias)

    def _get_connection(self, *args):
        """Can be overridden to use a custom connection."""
        return DebugConnection(*args)



class TerminalEmulator(object):

    def __init__(self, window_size=None, newline="\r\n",
                 encoding=('UTF-8', 'ignore')):
        self._rows, self._columns = window_size or (200, 200)
        self._newline = newline
        self._stream = pyte.ByteStream(encodings=[encoding])
        self._screen = pyte.HistoryScreen(self._rows,
                                          self._columns,
                                          history=100000)
        self._stream.attach(self._screen)
        self._screen.set_charset('B', '(')
        self._buffer = ''
        self._whitespace_after_last_feed = ''

    @property
    def current_output(self):
        return self._buffer + self._dump_screen()

    def _dump_screen(self):
        return self._get_history() + \
               self._get_screen(self._screen) + \
               self._whitespace_after_last_feed

    def _get_history(self):
        if self._screen.history.top:
            return self._get_screen(self._screen.history.top) + self._newline
        return ''

    def _get_screen(self, screen):
        return self._newline.join(''.join(c.data for c in row).rstrip()
                                  for row in screen).rstrip(self._newline)

    def feed(self, input_bytes):
        self._stream.feed(input_bytes)
        self._whitespace_after_last_feed = input_bytes[len(input_bytes.rstrip()):]

    def read(self):
        current_out = self.current_output
        self._update_buffer('')
        return current_out

    def read_until(self, expected):
        current_out = self.current_output
        exp_index = current_out.find(expected)
        if exp_index != -1:
            self._update_buffer(current_out[exp_index+len(expected):])
            return current_out[:exp_index+len(expected)]
        return None

    def read_until_regexp(self, regexp_list):
        current_out = self.current_output
        for rgx in regexp_list:
            match = rgx.search(current_out)
            if match:
                self._update_buffer(current_out[match.end():])
                return current_out[:match.end()]
        return None

    def _update_buffer(self, terminal_buffer):
        self._buffer = terminal_buffer
        self._whitespace_after_last_feed = ''
        self._screen.reset()
        self._screen.set_charset('B', '(')

class DebugError(RuntimeError):
    pass

