#!/usr/bin/env python
"""     Allow you to quickly switch all relays on for a given serial port


"""

import sys
import serial

try:
    from resources.variables.PowerDevices import *
except ImportError:

    sys.path.append("../")
    sys.path.append("./")

    try:
        from resources.variables.PowerDevices import *
    except ImportError:
        print "Unable to import Power Device variable file ..  abandoning"
        exit(1)






def main():
    # Ensure a serial port is supplied as an argument
    if len(sys.argv) < 2:
        print "Too few parameters, run as:"
        print "_utils/relays_on.py <SERIALPORT>        - For all"
        print "_utils/relays_on.py <SERIALPORT>:<PORT> - For one"

        exit(1)

    powerip = sys.argv[1].split(':')[0]
    try:
        powerport = int(sys.argv[1].split(':')[1])
    except IndexError:
        powerport = 0


    con = serial.Serial(port=powerip, baudrate=19200, bytesize=8, parity='N', stopbits=2)

    con.write(USB_RLY16['on'][powerport])

    con.close()


if __name__ == '__main__':
    main()


