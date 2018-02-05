#!/usr/bin/env python
__author__ = 'fsmith'
import socket
import hashlib
import random
import time
import glob
import struct
import select
import os
import inspect
import robot.libraries.OperatingSystem as ROS
import json
import datetime
import string
import unicodedata
import subprocess
import psutil


VERSION = 0.02

""" Aminorobot Beacon

    The ArbBeacon will open a UDP_MCAST beacon to respond to requests for 'whos there'

    Will also open TCP port for direct communication of detailed information

    The ArbListen class gives access to client end functionality

    The ArbCommands class gives access to the detail that can be sent over the TCP connection
    and is also used by sqarun fro some returns


"""

DEBUG = False
MY_OS = ROS.OperatingSystem()

class ArbCommands(object):

    # Log statics variables
    LOG_ROBOTRUN = 0
    LOG_ROBOTDEBUG = 1
    LOG_STB_DEBUG = 2
    LOG_STB_CPU = 3
    LOG_STB_MEM = 4

    def __init__(self):
        pass

    def _return_long_message(self, size=2000):
        """     Returns a random message string, of length size kwarg
        """
        ret = ''.join(random.choice(string.lowercase) for x in range(size))
        ret += '__THE_END!'

        return ret


    def get_response(self, msg):
        #test 23234
        return "IT WURKS! %s" % msg

    def get_version(self):
        """     This will hash the source of ArbCommands

        Used to determine if the running instance is different from the file
        """
        try:
            return str(hash("%s%s%s" %
                        (str(inspect.getsource(ArbCommands)),
                         str(inspect.getsource(ArbBeacon)),
                         str(inspect.getsource(ArbListener))
                      )))

        except Exception, e:
            return str(e)

    def tail_log(self, pid, log, length=50, offset=0):
        """     Interface to tail a log file available from the sqarun output
        """

        try:
            logtype = log
            pid = str(pid)

            path = self.get_path(pid)

            if str(path) == str(pid):
                raise RuntimeError("Keyerror: %s not found" % pid)

            file_path = None

            if logtype == ArbCommands.LOG_STB_DEBUG:
                # Deal with serial debug first, this is a special case
                # where we could have plain text or compressed logs
                find_file_txt = glob.glob('%s/*_debug.log' % (path))
                find_file_gz = glob.glob('%s/*_debug.log.gz' % (path))

                if len(find_file_txt) == 1:
                    debug('Using debug log txt format')
                    ret = _tail_file(find_file_txt[0], length, offset)
                elif len(find_file_gz) == 1:
                    # _tail_file doesn't cope well with gz files, do it here
                    debug('Using debug log gz format')
                    ret = _tail_gz_logfile(find_file_gz[0], length, offset)

                else:
                    ret = 'debug log not found!!'

            elif logtype == ArbCommands.LOG_ROBOTRUN:
                file_path = '%s/robotrun.log' % (path)
            elif logtype == ArbCommands.LOG_ROBOTDEBUG:
                file_path = '%s/robotdebug.log' % (path)
            elif logtype == ArbCommands.LOG_STB_CPU:
                file_path = glob.glob('%s/*cpu.log' % (path))[0]
            elif logtype == ArbCommands.LOG_STB_MEM:
                file_path = glob.glob('%s/*mem.log' % (path))[0]
            else:
                raise RuntimeError('invalid logtype: "%s"' % (logtype))

            if file_path:
                ret = _tail_file(file_path, length, offset)

        except IndexError as error:
            ret = 'Requested log type is unavailable for this test'
        except Exception as error:
            ret = str(error)

        return ret

    def get_log_data_sample(self, pid, log_type, data_rows=50):
        """     Gets a sample of CPU or Memory logs data

        log_type should be one of ArbCommands.LOG_STB_CPU and
        ArbCommands.LOG_STB_MEM, these are maintained here and
        in the robot viewer library.

        The data is returned in JSON format, with the following
        schema:

        {
         'status': 'PASS'/ 'FAIL',    # Status of the request
         'message': '',               # message if the request failed
         'data': [                    # the data sample in a JSON list
            {time_stamp, data_row},   # a sample data row, as read from
         ]                            #  the log file
        }
        """
        ret = {
            'status': '',
            'message': '',
            'data': []
        }

        base_path = self.get_path(str(pid))

        if base_path == pid:
            ret['status'] = 'FAIL'
            ret['message'] = 'No such pid %s' % (pid)

        else:
            log_type_str = ''
            if log_type == ArbCommands.LOG_STB_MEM:
                try_log_path = glob.glob('%s/*mem.log' % (base_path))
                log_type_str = 'Memory'

            elif log_type == ArbCommands.LOG_STB_CPU:
                try_log_path = glob.glob('%s/*cpu.log' % (base_path))
                log_type_str = 'CPU'

            else:
                ret['status'] = 'FAIL'
                ret['message'] = 'Invalid log_type %s' % (log_type)
                return json.dumps(ret)

            try:
                log_path = try_log_path[0]
            except IndexError:
                ret['status'] = 'FAIL'
                ret['message'] = '%s log not found for pid %s' % (
                                  log_type_str, pid)
            else:
                ret['data'] = _get_data_sample(log_path, data_rows)

                if ret['data'] != []:
                    ret['status'] = 'PASS'
                else:
                    ret['status'] = 'FAIL'
                    ret['message'] = 'No %s log data found' % (log_type_str)

        return json.dumps(ret)


    def get_path(self, pid):
        """     Returns the outputdir for the test pid, defined by sqarun
        if the pid is not found, or invalid, the error is returned
        """

        try:
            path = self.view_running_tasks('dict')[pid][1]
        except KeyError as error:
            return str(error)
        except Exception as error:
            return str(error)

        return path

    def view_running_tasks(self, returntype='json'):
        """     Method to return the running pybot tasks on the robot

        this method returns a dict containing the running pybot tasks data

        The format of the returned data is:
            [{PID: [TEST_ARGUMENTS, TEST_OUTPUTDIR]},n]
        """

        try:
            ret_code, output = MY_OS.run_and_return_rc_and_output("ps aux --columns 10000| grep pybot | grep -v grep | grep -v pipefail")

            ret = {}

            if ret_code != 0:
                debug("No pybot processes found\n")

            else:
                lines = output.split("\n")

                for line in lines:
                    if 'sh -c pybot' in line:
                        # This is a foreground sqarun test host process, we can ignore
                        #  it and take the information from the child process
                        pass
                    else:
                        task = []
                        parts = line.split()

                        rest = ''

                        for part in range(16, (len(parts)-1)):
                            rest += '%s ' % (parts[part])

                        pid = parts[1]
                        task.append("%s" % rest)
                        task.append("%s" % parts[13])
                        ret[str(pid)] = task

            if returntype == 'json':
                return json.dumps(ret)

            elif returntype == 'display':
                str_ret = 'PID \t Arguments \t\t\t\t\t\t outputdir\n'

                for process in ret.keys():
                    str_ret += '%s\t %s \t %s\n' % (process, ret[process][0], ret[process][1])

                return str_ret
            else:
                return ret

        except KeyError, err:
            return str(err)


    def get_active_count(self):
        """     Returns the number of pybot processes running on the node
        """
        try:
            running = json.loads(self.view_running_tasks())
            return str(len(running))
        except Exception, e:
            return str(e)

    def get_node_audit(self):
        """     Gets a small JSON audit on the robot nodes statistics
        """

        try:
            memory_stats = psutil.virtual_memory()
            storage_stats = psutil.disk_usage('/')

            net_stats = psutil.net_if_addrs()

            rcode, hostname = MY_OS.run_and_return_rc_and_output('hostname -A')

            rcode, os_release = MY_OS.run_and_return_rc_and_output(
                    'grep PRETTY_NAME /etc/os-release | cut -d\'"\' -f2')

            """
            os.system("git branch | grep \* > %s/git_info.txt" % outputdir)
            os.system("git log -n 1 >> %s/git_info.txt" % outputdir)
            """

            rcode, git_branch = MY_OS.run_and_return_rc_and_output('git branch | grep \*')
            rcode, git_commit = MY_OS.run_and_return_rc_and_output('git log -n 1')

            active_if = None

            # if 'eth0' in net_stats.keys():
            #     active_if = net_stats['eth0'][0]
            # elif 'eth1' in net_stats.keys():
            #     active_if = net_stats['eth1'][0]

            for key in net_stats.keys():
                for snic in net_stats[key]:
                    if snic.family==2 and snic.address!="127.0.0.1":
                        active_if = net_stats[key][0]

            ret = {
                'status': 'PASS',
                'message': '',

                'memory': {
                    'total_mem': get_mb_from_bytes(memory_stats.total),
                    'used_mem': get_mb_from_bytes(memory_stats.available),
                    'percent_usage': '%s%%' % (memory_stats.percent)
                },
                'storage': {
                    'total': get_mb_from_bytes(storage_stats.total),
                    'used': get_mb_from_bytes(storage_stats.used),
                    'free': get_mb_from_bytes(storage_stats.free),
                    'percent_usage': '%s%%' % (storage_stats.percent)
                },
                'network': {
                    'ip_addr': active_if.address,
                    'netmask': active_if.netmask,
                    'broadcast': active_if.broadcast,
                    'hostname': hostname.strip(" ")
                }, 'system': {
                    'os_version': os_release
                }, 'git': {
                    'branch': git_branch,
                    'commit': git_commit
                }
            }

        except Exception as error:

            ret = {
                'status': 'FAIL',
                'message': 'Failed to get JSON audit error: %s' % (error)
            }

        return json.dumps(ret)

def get_mb_from_bytes(bytes_val):
    """
    """
    return '%s MB' % (bytes_val / 1000 / 1000)

class ArbBeacon(object):

    def __init__(self):
        self.myIP = self.get_ip()
        self.MCAST_GRP = '225.100.0.140'
        self.MCAST_PORT = 1888
        self.MCAST_RCPORT = 1889
        if DEBUG:
            self.POLLTIME = 20
        else:
            self.POLLTIME = 120

        self.mserv_socket = None
        self.beacon_socket = None


    def _closesocket(self, sock):
        # Close sockets
        try:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        except socket.error:
            debug("Socket error encountered shutting down and closing socket %s" % str(sock))


    def activate_beacon(self):
        # Start forked processes and get their comms sockets

        debug("Starting MSERV and BEACON")
        self.mserv_socket = self._start_message_server()
        time.sleep(1)
        self.beacon_socket = self._start_beacon_server()

        while True:
            try:

                ready_socks,_,_ = select.select([self.beacon_socket, self.mserv_socket], [], [])

                for sock in ready_socks:
                    if sock is self.beacon_socket:
                        debug("Parent receievd message on beacon socket")
                    elif sock is self.mserv_socket:
                        #debug("Parent recieved message on mserv socket")
                        pass

                    else:
                        debug("Parent recieved message on unknown socket, dieing")
                        os._exit(0)


                    #debug("A CHILD IS CONTACTING")
                    data = sock.recv(9)
                    #debug("Data = %s" % data)

                    if data == "A":
                        sock.send("A")
                    elif data == "DIEDIEDIE":
                        debug("Parent received request to die from message server, instructing beacon to die")
                        self.beacon_socket.send("DIEDIEDIE")
                        debug("Closing mserv socket")
                        self._closesocket(self.mserv_socket) # may cause exception?
                        debug("Closing beacon socket")
                        self._closesocket(self.beacon_socket)
                        debug("Parent dying")
                        os._exit(0)
                        debug("PARENT: Should not be seen")

            except KeyboardInterrupt:
                os._exit(1)

        try:
            self._closesocket(self.mserv_socket)
            self._closesocket(self.beacon_socket)

        except:
            pass

        os._exit(0)

    def _start_message_server(self):
        child_sock, parent_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        pid = os.fork()
        if pid:
            return child_sock

        parent_sock.setblocking(0)
        active = True
        mserv_sock = self._get_mserv_sock()

        while active:
            try:

                sock = select.select([mserv_sock], [], [], self.POLLTIME)

                if sock[0]:
                    conn, addr = mserv_sock.accept()
                    command = conn.recv(1024)
                    debug("MessageCommand=%s" % command)
                    if command == "DIEDIEDIE":
                        debug("Instruction to die received at message server")
                        self._send_msg(conn, "DYING")
                        conn.shutdown(1)
                        conn.close()
                        # Tell parent to die
                        parent_sock.send("DIEDIEDIE")
                        self._closesocket(parent_sock)
                        self._closesocket(mserv_sock)
                        debug("Mserv dying")
                        os._exit(0)
                        debug("MSERV: Should not be seen")
                    self._work_with_command(conn, command)
                    mserv_sock.shutdown(1)
                else:
                    try:
                        parent_sock.send("A")
                        time.sleep(0.3)
                        parent_sock.recv(8)
                        debug("PARENT still up")
                    except socket.error:
                        debug("MSERV parent socket down.  Closing child")
                        self._closesocket(parent_sock)
                        self._closesocket(mserv_sock)
                        os._exit(0)
            except KeyboardInterrupt:
                os._exit(1)

    def _start_beacon_server(self):

        child_sock, parent_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        pid = os.fork()
        if pid:
            return child_sock

        parent_sock.setblocking(0)

        beacon_sock = self._get_beacon_sock()

        while True:
            try:
                sock,_,_  = select.select([beacon_sock, parent_sock], [], [], self.POLLTIME)

                try:
                    if sock[0]:

                        if sock[0] is parent_sock:
                            received = parent_sock.recv(10240)
                            debug(received)
                            if received == "DIEDIEDIE":
                                debug("Beacon server instructed to die")
                                self._closesocket(parent_sock)
                                debug("Beacon server closing sockets")
                                beacon_sock.close()

                                os._exit(0)
                        if sock[0] is beacon_sock:
                            received = beacon_sock.recv(10240)
                            if received == "ROBOT ROLL CALL":
                                # Wait for up to 2 seconds before responsing
                                waittime = random.random() * 2.0
                                time.sleep(waittime)
                                debug("Waited %s" % str(waittime))
                                self.send_beacon()
                except IndexError:
                    debug("Beacon server timeout")
                    try:
                        parent_sock.send("A")
                        time.sleep(0.3)
                        parent_sock.recv(9)
                        debug("PARENT still up")
                    except socket.error:
                        debug("BEACON parent socket down.  Closing child")
                        self._closesocket(parent_sock)
                        self._closesocket(beacon_sock)
                        os._exit(0)

            except KeyboardInterrupt:
                os._exit(1)

    def _work_with_command(self, conn, command):

        message_interpreter = ArbCommands()

        try:
            response = eval("message_interpreter.%s" % command)
            if inspect.ismethod(response):
                response = "Error! Commands need parentheses and parameters, e.g. '%s()' or '%s(foo)'" % (command, command)
        except AttributeError:
            msg = "Error! '%s' is not recognised as a command" % command
            debug(msg)
            self._send_msg(conn, msg)
            return
        except (TypeError, NameError) as error:
            msg = "Error! : %s" % str(error)
            debug(msg)
            self._send_msg(conn, msg)
            return
        except Exception as error:
            debug(str(error))
            self._send_msg(conn, "ERROR: %s" % str(error))
            return

        #conn.send(response)
        self._send_msg(conn, response) # Send message with known length


    def _send_msg(self, sock, msg):
        # Prefix each message with a 4-byte length (network byte order)
        debug("Sending back message %s" % msg)
        try:
            msg = unicode(msg)
            msg = unicodedata.normalize('NFKD', msg).encode('ascii','ignore')
            debug("msg normalised = %s" % msg)
            msg = struct.pack('>I', len(msg)) + msg
            debug("msg packed with length = %s" % msg)
        except Exception, err:
            msg = "Exception '%s', message '%s'" % (str(type(err)), str(err))
            debug(msg)

        sock.sendall(msg)

    def _get_mserv_sock(self):
        host = ''
        port = 8998

        mserv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        mserv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        connected = False

        while not connected:
            try:
                mserv_sock.bind((host, port))
                connected = True
                debug("MSERV connected")
            except socket.error, msg:
                print "MSERV Bind failed. Error code : %s Message %s.  Waiting..." % (str(msg[0]), msg[1])
                time.sleep(5)

        mserv_sock.setblocking(0)

        mserv_sock.listen(10)

        return mserv_sock


    def __del__(self):
        try:
            self.mserv_socket.send("EXIT")
            self.mserv_socket.close()
        except:
            pass

    @staticmethod
    def get_ip():
        try:
            ip = [(s.connect(('8.8.8.8', 80)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]
        except:
            print "ERROR: Unable to obtain local IP!"
            exit(1)

        return ip

    def _get_beacon_sock(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.MCAST_GRP, self.MCAST_RCPORT))  # use MCAST_GRP instead of '' to listen only
                             # to MCAST_GRP, not all groups on MCAST_PORT
        mreq = struct.pack("4sl", socket.inet_aton(self.MCAST_GRP), socket.INADDR_ANY)

        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        return sock

    def build_beacon(self):
        """
        These elements are required:-
        [IP],[ACTIVERUNS],[TS],[CHECKSUM]
        """

        beacon = "%s,%s,%s" % (self.myIP, self.get_active_runs(), str(time.time()))
        myhash = hashlib.md5(beacon).hexdigest()[-8:]
        beacon += ",%s" % myhash

        return beacon

    def get_active_runs(self):
        """     Interface to get_active_count()
        """
        return ArbCommands().get_active_count()

    def send_beacon(self):

        beacon = self.build_beacon()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.sendto(beacon, (self.MCAST_GRP, self.MCAST_PORT))

class ArbListener(object):

    def __init__(self):
        self.MCAST_GRP = '225.100.0.140'
        self.MCAST_PORT = 1888
        self.MCAST_RCPORT = 1889
        self.beacon_list = []
        self.beacon_time = None
        self.beacon_life = 60

    def help(self, includehidden=False):
        """
        help() - displays this help information

        Example:
        mylistener.help()

        :return: None

        """
        methods = inspect.getmembers(ArbListener)
        for method in methods:
            if method[0][0] != "_" or includehidden == True: # Don't list private members
                print method[0]
                print eval("self.%s.__doc__" % method[0])

    def help_commands(self, includehidden=False):
        """
        help_commands() - displays help information for supported commands

        Example:
        mylistener.help_commands()

        :return: None

        """
        methods = inspect.getmembers(ArbCommands)
        for method in methods:
            if (method[0][0] != "_" and method[0][:3] != "LOG") or includehidden==True: # Don't list private members
                print method[0]
                print eval("ArbCommands().%s.__doc__" % method[0])

    def _beacon_list_expired(self):
        """     Method to check if the beacon list has passed it's beacon_life
        """
        if time.time() > (self.beacon_time + self.beacon_life):
            return True
        else:
            return False

    def _test_listen(self):

        sock = self._get_beacon_sock()

        while True:
            print sock.recv(10240)

    def _get_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.MCAST_GRP, self.MCAST_PORT))  # use MCAST_GRP instead of '' to listen only

        # to MCAST_GRP, not all groups on MCAST_PORT
        mreq = struct.pack("4sl", socket.inet_aton(self.MCAST_GRP), socket.INADDR_ANY)

        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        return sock

    def _send_rollcall(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.sendto("ROBOT ROLL CALL", (self.MCAST_GRP, self.MCAST_RCPORT))

    def _detect_beacons(self, timeout=5):

        sock = self._get_socket()

        expirytime = time.time() + timeout

        received = ""

        sock.setblocking(0)

        self._send_rollcall()

        while time.time() < expirytime:
            ready = select.select([sock], [], [], 1)
            if ready[0]:
                received += "%s|" % sock.recv(10240)

        received_list = []

        if len(received) > 0:
            received = received[:-1] # Chomp trailing pipe

            #CHECK CHCKSUMS HERE, only allow valid into list OR mark invalid ?

            unchecked_received_list = received.split('|')

            for listitem in unchecked_received_list:
                if self._check_beacon_checksum(listitem):
                    received_list.append(Beacon(listitem))

        return received_list

    def refresh_beacon_list(self):
        """
        refresh_beacon_list() - Force a refresh of the beacon list

        Example:
        mylistener.refresh_beacon_list()

        :return: None

        """
        self.beacon_list = self._detect_beacons()
        self.beacon_time = time.time()

    def _check_beacon_checksum(self, beacon):
        # IMPROVEMENT add hash checking in reverse
        return True

    def beacon_count(self):
        """
        beacon_count() - Return number of beacons in the beacon_list

        Example:
        mylistener.beacon_count()

        :return: integer

        """
        return len(self._get_beacon_list())

    def _get_beacon_list(self):
        if len(self.beacon_list) == 0 or self._beacon_list_expired():
            self.refresh_beacon_list()

        return self.beacon_list

    def list_beacons(self):
        """
        list_beacons() - return a list of beacons which are responding

        The list will contain a number of other lists which contain IP address and Number of robot runs active

        Example:
        mylistener.list_beacons()

        :return: list of beacons, a beacon is itself a list of IP address and number of active robot runs

        """
        beacons = self._get_beacon_list()
        ret = []
        if len(beacons) > 0:

            for beacon in beacons:
                ip_addr = str(beacon.ip)
                active_runs = str(beacon.active_runs)
                debug("IP %s  -  %s running tasks" % (ip_addr, active_runs))
                single = []
                single.append(ip_addr)
                single.append(active_runs)
                ret.append(single)

        return ret


    def send_command(self, ip_addr, command):
        """
        Send a command to the Aminorobot Beacon.  Commands must exist in the ArbCommands object.

        Must supply the ip_addr of the beacon and the command, both as strings

        Example:
        mylistener.send_command("10.172.2.22","view_running_tasks()")

        :param ip_addr: for example '10.172.2.22'
        :param command:  for example 'view_running_tasks()'
        :return: output from the command sent, can vary in type

        NOTE: Please see mylistener.help_commands() for list of commands supported

        """
        port = 8998
        host = ip_addr
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error:
            print 'Failed to create socket'
            os._exit(1)

        try:
            s.connect((host, port))
        except socket.error:
            debug("Error! Unable to contact %s:%s" % (host, str(port)))
            return

        s.send(command)
        data = self._recv_msg(s)
        #debug("Received response '%s'" % data)
        if data == "DYING":
            s.shutdown(1)
            s.close()
            return

        s.close()
        return data

    def _recv_msg(self, sock):
        # Read message length and unpack it into an integer
        raw_msglen = self._recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        # Read the message data
        return self._recvall(sock, msglen)

    def _recvall(self, sock, number):
        # Helper function to recv number bytes or return None if EOF is hit
        data = ''
        while len(data) < number:
            packet = sock.recv(number - len(data))
            if not packet:
                return None
            data += packet
        return data

class Beacon(object):
    def __init__(self, beacon_message):
        beacon_message = beacon_message.split(',')
        self.ip = beacon_message[0]
        self.active_runs = beacon_message[1]
        self.timestamp = beacon_message[2]

def debug(text):
    """     Simple debug helper function
    """
    if DEBUG:
        print "DEBUG: %s" % text

def get_timestamp():
    """     Get a timestamp for the current time
    """
    time_stamp = time.time()
    time_str = datetime.datetime.fromtimestamp(time_stamp).strftime(
                                        '%Y-%m-%d %H:%M:%S.%f')[:-3]
    return time_str

def _tail_file(path, lines, offset=0):
    """     Simulates a unix tail command, with an optional offset

    :param: path   - str - fully qualified path to the plain text log file
    :param: lines  - int - The number of lines to extract from the log file
    :param: offset - int - offset from the bottom of the file to take the log
                           lines from.

    :returns: - str - newline seperated string of the lines requested by the
                      lines and offset params.
    """

    ret = ''
    try:
        logfile = open(path, 'r')

    except IOError:
        ret = 'Failed to find log file!'

    else:
        # File found, tail it
        log_lines = logfile.readlines()

        if offset == 0:
            tail = log_lines[-int(lines):]
        elif offset > 0:
            tail = log_lines[-int(lines)-int(offset):-int(offset)]

        ret = ''.join(tail)

        logfile.close()

    return ret

def _tail_gz_logfile(path, lines, offset=0):
    """     Similar behaviour to _tail_file, for gz compressed log files

    This is done using a subprocess, as the gzip python library struggles to
    correctly read a file the aminorobot library is currently writing to. Also,
    the performance of calling a subprocess is significantly worse than using
    python's built in file reading.

    :param: path   - str - fully qualified path to the gzip log file
    :param: lines  - int - The number of lines to extract from the log file
    :param: offset - int - offset from the bottom of the file to take the log
                           lines from.

    :returns: - str - newline seperated string of the lines requested by the
                      lines and offset params.
    """

    ret = ''

    tail_file = subprocess.Popen(['zcat', path],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)

    out, err = tail_file.communicate()

    if out != '':
        tail_lines = str(out).split('\r\n')

        if offset == 0:
            ret = '\r\n'.join(tail_lines[-lines:])
        else:
            ret = '\r\n'.join(tail_lines[-lines-offset:-offset])
    else:
        ret = 'tail gz debug log failed %s' % (err)

    return ret


def _get_data_sample(log_path, sample_size):
    """     Reads a data log file and returns a sample list of the data
    """

    data = []

    try:
        with open(log_path, 'r') as data_file:
            first = True
            for line in data_file.readlines():
                if first:
                    # First line is the csv header
                    first = False

                else:
                    row = line.split(',')

                    time_stamp = row[0]
                    row_data = row[1].replace('\n', '')

                    data.append({time_stamp: row_data})

    except IOError:
        # Failed to read the log file, return an empty list
        return []

    size_of_data = len(data)
    if size_of_data > int(sample_size):
        # We have more data than the sample size, we need to take a sample
        sample_rate = int(size_of_data / sample_size)

        # Take every nth element of the list
        data = data[0::sample_rate]

        # Trim the remainder of the list
        data = data[:sample_size]

        debug('size_of_data=%s sample_size=%s sample_rate=%s len(data)=%s' % (
               size_of_data, sample_size, sample_rate, len(data)))

    return data


if __name__ == "__main__":
    ARB_BEACON = ArbBeacon()
    ARB_BEACON.activate_beacon()

# Helper functions

def list_robots():
    """     print a listof  the beacons available on the network
    """

    myal = ArbListener()
    print myal.list_beacons()

def view_robot(ip_addr, displaytype='display'):
    """     Print the running robot a listener, defined by the ip_addr
    """

    myal = ArbListener()
    print myal.send_command(ip_addr, "view_running_tasks('%s')" % displaytype)

def view_log(ip_addr, pid, log_type=0, length=50, offset=0):
    """     Tail one of the log files on a listening arb beacon
    """

    myal = ArbListener()
    print myal.send_command(ip_addr, "tail_log(%s,%s,length=%s, offset=%s)" % (
                            str(pid), str(log_type), str(length), str(offset)))

def get_log_data_sample(ip_addr, pid, log_type, rows=50):
    """     Test function to get a sample of the statistics data
    """
    myal = ArbListener()

    print myal.send_command(ip_addr, "get_log_data_sample(%s, %s, data_rows=%s)" % (
                                      str(pid), str(log_type), str(rows)))

def get_node_stats(ip_addr):
    """     Test function to get the node statistics
    """
    myal = ArbListener()

    print myal.send_command(ip_addr, "get_node_audit()")

def view_local_robot():
    """ List locally running sqarun tasks
    """
    mya = ArbCommands()
    print mya.view_running_tasks()

