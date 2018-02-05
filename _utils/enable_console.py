#!/usr/bin/env python

"""     Enables the console on a verimatrix enabled build using HNR

Run as:
    ./enable_console.py <STB_IP_ADDRESS>

Example:
    ./enable_console.py 10.172.249.95
"""

import sys
import time
import subprocess



try:
    from libraries.HNRKey import HNRKey
except ImportError:

    sys.path.append("../")
    sys.path.append("./")

    try:
        from libraries.HNRKey import HNRKey
    except ImportError:
        print "Unable to import HNRKey..  abandoning"
        exit(1)



def main():
    """     Main function
    """

    # Ensure an IP address is supplied as an argument
    if len(sys.argv) < 4:
        print "Too few parameters, run as:"
        print "./enable_console.py <STB_IP_ADDRESS> <SSH USERNAME> <SSH PASSWORD>"

        exit(1)

    ip_address = sys.argv[1]
    ssh_user = sys.argv[2]
    ssh_pass = sys.argv[3]

    proc = subprocess.Popen(['ping', '-c', '1', ip_address],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

    # Wait for ping to complete
    proc.communicate()

    if proc.returncode != 0:
        print "unable to contact provided IP Address, exiting"
        exit(1)

    #conn = HNRKey(ipaddress=ip_address)
    conn = HNRKey(ipaddress=ip_address, ssh_tunnel_user=ssh_user, ssh_tunnel_password=ssh_pass )

    key_presses = ['INPUT', '7', '3', '6', '6', '8', '3']

    for key in key_presses:
        conn.send_hnrkey(key)
        time.sleep(0.1)

if __name__ == '__main__':
    main()
