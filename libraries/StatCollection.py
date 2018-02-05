"""
Classes:
    StatCollection - Collect stats from an enable STB

Functions:
    _create_output_file        - Creates output file and writes the CSV headers
    _get_free_cpu_from_top     - strip cpu and memory values from output of top
    _get_free_mem_from_meminfo - strip free memory from output of /proc/meminfo
"""
# robot framework imports
from robot import utils
from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn

# Standard python imports
from threading import Thread
from datetime import datetime
import SSHLibrary
import socket
import time
import re
import os

__version__ = '0.0 alpha'

ANSI_ESCAPE = re.compile(r'\x1b[^m]*m')

CPU_CMD = 'top -n 1 | head -n 2 | tail -n 1'
MEMORY_CMD = 'grep \'MemFree\\|Cached\\|SwapCached\\|Buffers\' /proc/meminfo'
WIFI_CMD = 'cat /proc/net/wireless'
HDD_CMD = 'df | grep sda'
IOSTAT_CMD = "iostat sda -cx | awk '/sda/ { print $4, $5, $6, $7, $10, $11, $12, $16, $15+$16 }'"

class StatCollection(Thread):
    """     Library to be used to collect system statistics from enable STBs
    """

    def __init__(self, stb_object):

        Thread.__init__(self, target=self.stats_worker, args=())

        # Set daemon flag on the Thread object
        self.daemon = True

        self.stats_running = False
        self.end_stats_collection = False

        self.ssh_conn = SSHLibrary.SSHLibrary(loglevel='TRACE')
        self._ssh_open = False

        self._uut_shortname = stb_object.get_property('shortname')
        self._base_output_path = self._get_logfile_path()

        self._stats_ip = stb_object.get_interface_attribute()
        self._ssh_keyfile = stb_object.get_property('ssh_keyfile')

        self._stats_interval = 0

        self._ssh_prompt_regex = '(\/.* #|~ #)'

        self._ssh_open_opts = {
            'prompt': ' #',
            'newline': '\r\n',
            'timeout': 10,
            'port': 10022
        }

        self.stats_to_capture = {
            'cpu': True,
            'mem': True,
            'wifi': False,
            'iostat': False,
            'hdd': False,
        }

    def _connect_ssh(self):
        """     Open an ssh connection for the stats commands to be run
        """
        logger.debug('Opening stats connection')

        self.ssh_conn.open_connection(self._stats_ip, **self._ssh_open_opts)

        try_count = 0

        while try_count < 5:
            # Try 5 times to get an SSH connection as if coming up from reboot,
            # There is a chance that the ssh client is not yet ready
            try:
                self.ssh_conn.login_with_public_key('root', self._ssh_keyfile)
                self._ssh_open = True
                try_count = 5
            except RuntimeError:
                logger.debug('Failed to login for stats, retrying')
                try_count += 1
                time.sleep(2)

        if not self._ssh_open:
            raise RuntimeError('Failed to login via SSH for stats capture')

    def _send_stats_command(self, stats_cmd):
        """     Send a single stats command over SSH and return the output

        Parameters:
        -----------
        stats_cmd - (str) - command to run over an SSH connection to the STB

        Returns:
        -----------
        ret         (str) - stdout and stderr from running the command
                            specified by the stats_cmd parameter.
        """
        logger.trace('_send_stats_command: command = "%s"' % (stats_cmd))

        if not self._ssh_open:
            self._connect_ssh()

        # Send command and wait for prompt
        ret = self.ssh_conn.write(stats_cmd)
        ret += self.ssh_conn.read_until_regexp(self._ssh_prompt_regex)
        ret += self.ssh_conn.read(delay="0.5 seconds")

        # Strip colour chars, pybot does not handle them well
        ret = ANSI_ESCAPE.sub('', ret)

        # Strip the prompt from the string
        ret = re.sub(self._ssh_prompt_regex, '', ret)

        # Remove the original command, as it is left in by the SSHLibrary
        ret = ret.replace(stats_cmd, '')

        # Strip additional prompts left in by multiple 'reads'
        ret = ret.replace('\r\n~', '')

        return ret

    def start_stats_collection(self, cpu=True, mem=True, wifi=False,
                                iostat=False, hdd=False):
        """     Start the stats collection thread, set which stats to collect

        Parameters:
        -----------
        cpu  - (bool) - Start statistics capture for the CPU usage
        mem  - (bool) - Start statistics capture for the memory usage
        wifi - (bool) - Start capturing wifi statistics

        Returns:
        -----------
        None - (void)
        """
        self.stats_running = True

        self.stats_to_capture = {
            'cpu': bool(cpu),
            'mem': bool(mem),
            'wifi': bool(wifi),
            'iostat': bool(iostat),
            'hdd': bool(hdd)
        }

        self.start()

    def stop_stats_collection(self):
        """     Stops the stats collection at the end fo the test suite
        """
        logger.debug('Stopping STB statistics collection')

        self.end_stats_collection = True

    def pause_stats_for_reboot(self):
        """     Temporarily pause the stats collection for reboot
        """
        logger.debug('pause_stats_for_reboot: Called')

        self._ssh_open = False
        self.stats_running = False

    def restart_stats_after_reboot(self):
        """     Restart stats collection after a reboot has completed
        """
        time.sleep(2.5)
        logger.debug('restart_stats_after_reboot: Called')
        self.stats_running = True

    def stats_worker(self):
        """     Main worker method for the stats collection thread
        """

        while not self.end_stats_collection:

            try:
                start_time = int(time.time())

                if self.stats_running:

                    if self.stats_to_capture['cpu']:
                        cpu_ret = self._send_stats_command(CPU_CMD)
                        cpu_free = _get_free_cpu_from_top(cpu_ret)

                        self._write_to_logfile('cpu', cpu_free)


                    if self.stats_to_capture['mem']:
                        mem_ret = self._send_stats_command(MEMORY_CMD)
                        free_mem = _get_free_mem_from_meminfo(mem_ret)

                        self._write_to_logfile('mem', free_mem)

                    if self.stats_to_capture['wifi']:
                        wifi_ret = self._send_stats_command(WIFI_CMD)
                        wifi_stats = _get_wifi_stats_string(wifi_ret)

                        self._write_to_logfile('wifi', wifi_stats)

                    if self.stats_to_capture['iostat']:
                        iostat_ret = self._send_stats_command(IOSTAT_CMD)

                        iostat_stats = _get_iostat_from_str(iostat_ret)

                        self._write_to_logfile('iostat', iostat_stats)

                    if self.stats_to_capture['hdd']:
                        hdd_ret = self._send_stats_command(HDD_CMD)

                        hdd_stats = _get_hdd_stat_from_str(hdd_ret)

                        self._write_to_logfile('hdd', hdd_stats)

                end_time = int(time.time())

                # Remove time it took to capture stats from interval
                time_to_sleep = self._stats_interval - (end_time - start_time)

                if time_to_sleep < 0:
                    # If the interval becomes negative set it to 0, time.sleep
                    #  will reject a negative parameter and throw an exception
                    time_to_sleep = 0

                time.sleep(time_to_sleep)

            except (socket.error, RuntimeError) as error:
                logger.debug('StatsCollection: error %s' % error)
                logger.debug('StatsCollection: Restarting SSH connection')
                time.sleep(60)
                self.ssh_conn.close_all_connections()
                self._connect_ssh()

    def _get_logfile_path(self):
        """     Returns the base path for log files to be generated
        """

        try:
            outdir = BuiltIn().replace_variables('${OUTPUTDIR}')
            suitename = BuiltIn().replace_variables('${SUITENAME}')
        except:
            print "Running library outside of aminorobot --- Using temp log location /tmp/STATS_xxxx.txt"
            outdir = "/tmp"
            suitename = "STATS"


        ret = os.path.join(outdir, suitename + '_' +
                           self._uut_shortname).replace(' ','_')

        return ret

    def _write_to_logfile(self, stats_file, stat_value):
        """     Writes a single line to the log file

        Parameters:
        -----------
        stats_file - (str) - The type of statistics that are to be written
                             to the log file ('cpu', 'mem', 'wifi')
        stat_value - (str) - The value, or comma separated values read from
                             the STB to be written to the log file

        Returns
        -----------
        None - (void)
        """

        file_path = '%s_%s.log' % (self._base_output_path, stats_file)

        # Use the same format we used in AmiNET log files
        time_stamp = datetime.strftime(datetime.now(), '%Y%m%d%H%M%S')

        if not os.path.isfile(file_path):
            _create_output_file(file_path, stats_file)

        with open(file_path, 'a') as output_file:
            output_file.write('%s,%s\n' % (time_stamp, stat_value))

    def set_stats_interval(self, interval):
        """ Sets the interval for collecting STB statistics

        Parameters:
        -----------
        interval - (str) - Interval to collect statistics from the STB
                           in a human readable format for example:
                           '10 seconds', '30 seconds', '1 minute'

        Returns:
        -----------
        None - (void)
        """

        self._stats_interval = utils.timestr_to_secs(interval)


def _create_output_file(file_path, log_type):
    """     Creates the log file and writes the header

    Parameters:
    -----------
    file_path - (str) - The base file path for the log files, fetched
                        from the _get_logfile_path method of the
                        StatCollection class.
    log_type  - (str) - The type of log file to be created, ('cpu','mem'
                        'wifi', 'iostat'), this also determines the
                        headers to be written to the first line of the
                        file

    Returns:
    -----------
    None - (void)
    """

    header = ''

    if log_type == 'cpu':
        header = 'Timestamp,CPU_IDLE(%)'
    elif log_type == 'mem':
        header = 'Timestamp,FreeMemory(KB)'
    elif log_type == 'wifi':
        header = 'Timestamp,Quality(%),SignalStrength(dBm),Noisefloor(dBm)'
    elif log_type == 'iostat':
        header = 'Timestamp,r/s,w/s,kr/s,kw/s,wait,svc_t,%b,id,wt+id'
    elif log_type == 'hdd':
        header = 'Timestamp,Used,Available,use%'
    else:
        header = 'UNKNOWN_STATS_HEADER'
        logger.warn('Unknown log_type in _create_output_file %s' % (log_type))

    with open(file_path, 'w') as output_file:
        output_file.write('%s\n' % (header))

def _get_free_cpu_from_top(top_output):
    """     Get the idle CPU percentage from the output of top

    Parameters:
    -----------
    top_output - (str) - the output of running 'top -n 1|head -n 2|tail -n 1'
                         on the STB console, this returns the CPU statistics,
                         of which we are interested in the 'free' field.

    Returns:
    -----------
    ret - (str) - The free CPU percentage stripped from the output of top on
                  success, 'FAIL' is returned if the free CPU percentage cannot
                  be determined.
    """
    ret = 'FAIL'

    for part in top_output.split('  '):
        if 'idle' in part:
            ret = part.split('%')[0]

    return str(int(ret))

def _get_free_mem_from_meminfo(meminfo):
    """     Calculates free memory from the output of /proc/meminfo

    Gets the sum of MemFree, Cached and SwapCached from /proc/meminfo
    to calculate the total free memory on the STB.

    Parameters:
    -----------
    meminfo - (str) - the output of running MemFree, Cached and SwapCached from
                      /proc/meminfo using the command:
                        grep 'MemFree\|Cached\|SwapCached' /proc/meminfo

    Returns:
    -----------
    ret - (str) - the sum total of the 3 memory statistics captured from the
                  /proc/meminfo entry in string format on success, else '0'
                  is returned
    """
    ret = 0

    for line in meminfo.split('\n'):
        if (line != '') and ('kB' in line):
            parts = line.split(' ')
            mem_val = parts[len(parts)-2]
            ret += int(mem_val)

    return str(int(ret))

def _get_wifi_stats_string(net_output):
    """     Strips the required stats from the output of /proc/net/wireless

    Parameters:
    -----------
    net_output (str) - The output of running cat /proc/net/wireless on the
                       STB console.
    Returns:
    -----------
    ret_str (str) - A comma separated string of the 3 statistics we want to
                    capture from the output in the format:
                       <Quality(%)>,<SignalStrength(dBm)>,<Noisefloor(dBm)>
                    or, if the wifi interface is not found on the unit under
                    test then '"FAIL","FAIL","FAIL"' is returned to maintain
                    the CSV log file format.
    """
    wifi_found = False
    ret_list = []

    for line in net_output.split('\n'):
        if 'wlan0' in line:
            wifi_found = True

            parts = line.split('  ')

            ret_list.append(parts[2].replace('.', ''))
            ret_list.append(parts[3].replace('.', ''))
            ret_list.append(parts[4].replace('.', ''))

    if wifi_found:
        ret_str = ','.join(ret_list)
        ret_str = ret_str.replace(' ', '')
    else:
        ret_str = '"FAIL","FAIL","FAIL"'

    return ret_str

def _get_iostat_from_str(iostat_out):
    """     Gets a csv line from the output of the iostat command

    Parameters:
    -----------
    iostat_out (str) - the output of running the IOSTAT_CMD on the STB

    Returns:
    -----------
    ret (str) -
    """

    lines = iostat_out.split('\r\n')

    ret = None
    for line in lines:
        parts = line.split(' ')

        if len(parts) > 7:
            # Use how many parts there are as an indicator of which line to use
            ret = line.replace(' ', ',')

    return ret

def _get_hdd_stat_from_str(df_out):
    """     Gets a csv line from the output of the hdd command
    logs the hdd usage, using the output of df, not ideal for
    hdd usage, but it's the best utility we have.


    Returns:
    -----------
    ret (str) - csv line in format <Used>,<Available>,<Use%>
    """

    lines = df_out.split('\n')

    ret = ''

    for line in lines:
        if 'sda' in line:
            single_spaced_line = line.split()

            ret += '%s,' % (single_spaced_line[2])
            ret += '%s,' % (single_spaced_line[3])
            ret += '%s' % (single_spaced_line[4])

    return ret
