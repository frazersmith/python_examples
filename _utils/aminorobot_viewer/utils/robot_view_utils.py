"""
docstring
"""
from robot.parsing.model import TestData, TestCaseFile, TestDataDirectory
import socket
import datetime
import subprocess
import robot
import re
from socket import herror

DEBUG = False

def get_hostname_from_ip(ip_addr):
    """
    docstring
    """
    try:
        ret = socket.gethostbyaddr(ip_addr)[0]
    except herror:
        ret = 'Unavailable'

    if '.aminocom.com' in ret:
        ret = ret.replace('.aminocom.com', '')

    return ret

def get_test_times(job):
    """     Get test duration and remaining times
    """

    ret = {}

    duration_present = False

    if 'duration' in job['test_args']:
        # This is likely a soak test, try to calculate the elapsed and remaining time
        duration_str = job['test_args'].split('duration:')[1]
        duration_str = duration_str.split(' ')[0]
        duration_present = True

    elif 'timeout' in job['test_args']:
        duration_str = job['test_args'].split('timeout:')[1]
        duration_str = duration_str.split(' ')[0]
        duration_present = True

    out_dir = job['output_dir'].split('/')

    time_ind = 0

    for ind, spl in enumerate(out_dir):
        try:
            start_date = datetime.datetime.strptime(spl, "%Y-%m-%d")
            time_ind = ind + 1
        except ValueError:
            # This should catch any arg which is not a date
            pass

    try_start_time = out_dir[time_ind].split('-')

    if len(try_start_time) == 6:
        start_date = start_date.replace(hour=int(try_start_time[0]))
        start_date = start_date.replace(minute=int(try_start_time[1]))
        start_date = start_date.replace(second=int(try_start_time[2]))

    if duration_present:
        try:
            duration_seconds = robot.utils.robottime.timestr_to_secs(duration_str)
            test_end_time = start_date + datetime.timedelta(seconds=int(duration_seconds))
            time_remaining =  test_end_time - datetime.datetime.now()
            seconds_remaining = int(time_remaining.seconds) + (time_remaining.days * 60 * 60 * 24)

            ret['test_time_remaining'] = seconds_remaining
            ret['test_duration'] = duration_str
            ret['test_end_time'] = test_end_time.strftime('%a, %d %b %Y - %H:%M:%S')
        except ValueError:
            # Failed to parse time string, assume unavailable
            ret['test_duration'] = False

    else:
        ret['test_duration'] = False

    ret['test_start_time'] = start_date.strftime('%a, %d %b %Y - %H:%M:%S')

    return ret

def get_tag_text(tagslist):
    """
    docstring
    """
    tags = []
    try:
        for tag in tagslist:
            tags.append("%s" % tag)
        if len(tags) > 0:
            tagtext = ','.join(tags)
        else:
            tagtext = ""
    except TypeError:
        tagtext = ""
    return tagtext

CONT = {}

def parsetree(node, parents):
    """
    docstring
    """

    if isinstance(node, TestDataDirectory):
        if parents == "":
            parents = node.name
        else:
            parents = parents + "." + node.name

        ftagtext = get_tag_text(node.setting_table.force_tags)
        dtagtext = get_tag_text(node.setting_table.default_tags)

        for child in node.children:
            parsetree(child, parents)

    elif isinstance(node, TestCaseFile):
        ftagtext = get_tag_text(node.setting_table.force_tags)
        dtagtext = get_tag_text(node.setting_table.default_tags)

        parent_key = '%s/%s' % (parents, node.name)
        parent_key = parent_key.replace(' ', '_')
        parent_key = parent_key.replace('.', '/')

        if parent_key not in CONT:
            CONT[parent_key] = {}
        else:
            print 'duplicate key!' + parent_key

        CONT[parent_key]['f_tags'] = ftagtext
        CONT[parent_key]['d_tags'] = dtagtext

        CONT[parent_key]['tests'] = []

        tests = node.testcase_table
        for thistest in tests:
            if DEBUG:
                print 'Added test "%s"' % (thistest.name)

            tagtext = get_tag_text(thistest.tags)

            repair_name = thistest.name
            repair_name = repair_name.replace('"', '')

            CONT[parent_key]['tests'].append([repair_name, tagtext])
    return CONT

def get_tests_tree(source_path='.'):
    """
    docs
    """
    root_node = TestData(source=source_path)
    ret = parsetree(root_node, '')
    return ret

FIND_MAC_REGEX = re.compile(ur'(?:[0-9a-fA-F]:?){12}')

def get_mac_from_ip(ip_addr):
    """     Get's the mac address from a remote IP address

    try arp first as this is quicker but does not always contain
    the MAC address we want, so if it fails, try using nmap,
    which is more reliable, but takes longer to find by around a
    factor of 10. But once nmap is run, the MAC is cached by arp
    and will be fetched more quickly on multiple runs

    Example Times:
        found using arp  : 0.020577907562
        found using nmap : 0.343184089661

    :param ip_addr The IP address to fetch the MAC address of

    :returns mac_addr The MAC address of the IP passed to the function
    """

    proc = subprocess.Popen(['sudo', 'arp', '-n', ip_addr],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

    arp_out, arp_err = proc.communicate()

    if 'no entry' in arp_out:
        # The MAC is not in the arp_out of arp, try nmap
        nmap_proc = subprocess.Popen(['sudo', 'nmap', ip_addr],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)

        nmap_out, nmap_err = nmap_proc.communicate()

        ret_list = re.findall(FIND_MAC_REGEX, nmap_out)
    else:
        ret_list = re.findall(FIND_MAC_REGEX, arp_out)

    if len(ret_list) > 0:
        # Return the found MAC address
        return ret_list[0].lower()
    else:
        return 'FAIL %s' % (nmap_err if nmap_err else arp_err)
