"""     Container file to define a dict of the serial number prefixes

AmiNET and Enable both use the convention of defining the product by the
first 2 characters of the serial number and do not appear to clash, so for
now at least, we will leave in support for both stacks.

This contains the AmiNET serial number prefixes back to the Ax4x platform
and the enable serial number prefixes that we are aware of.
"""

STB_IDENTS = {
    'GB': 'A140',
    'GC': 'H140',
    'GD': 'A129',
    'GF': 'A540',
    'GG': 'M540',
    'GH': 'M140',
    'GI': 'A129',
    'GJ': 'A140',
    'GK': 'H140',
    'GL': 'A540',
    'GM': 'M540',
    'GN': 'M140',
    'GW': 'A140',
    'GX': 'A139',
    'G3': 'A139x',
    'G4': 'A139',
    'G5': 'A139-E',
    'G6': 'A540x',
    'G7': 'A540',
    'G8': 'M540',
    'J2': 'L1050 v1',
    'J3': 'L5050 v1',
    'J4': 'L1050 v1',
    'J5': 'L5050 v1',
    'J6': 'L5050 v1',
    'J7': 'L5055 v3',
    'J8': 'L1050 v3',
    'J9': 'L5050 v3',
    'KE': 'A150',
    'KF': 'A550',
    'KJ': 'A50 512MB',
    'KL': 'A50 1GB',
    'KN': 'H150',
    'LA': 'A139',
    'LB': 'A139x',
    'LC': 'A140',
    'LD': 'H140',
    'MA': 'Z315',
    'NA': 'A160 512MB RF4CE',
    'NB': 'A160 1GB   RF4CE',
    'NC': 'A160 512MB WiFi RF4CE',
    'ND': 'A160 1GB   WiFi RF4CE',
    'NE': 'A160 512MB',
    'NF': 'A160 1GB',
    'NG': 'A160 512MB WiFi',
    'NH': 'A160 1GB   WiFi',
    # Enable STBs:
    '03': 'Amulet 300',
    '11': 'Amulet 300',
    '05': 'Janus 300',
    '13': 'Janus 300',
    '20': 'Amulet 400',
    '21': 'Amulet 400',
    '22': 'Amulet 400',
    '23': 'Amulet 400',
    '18': 'Kamai 400',
    '19': 'Kamai 400',
    '25': 'Kamai 400',
    '26': 'Kamai 500',
    '27': 'Amulet 500',
    '24': 'Magi 400 Series',
    '28': 'Magi 400 Series',
    '29': 'Magi 400 Series',
    '30': 'Magi 400 Series',
    '31': 'Kamai 450',
    '32': 'Amulet 459m',
    '34': 'Aria 500c (Conax, DVB-C)',
    '35': 'Aria 500i (isdbt)',
    '36': 'Aria 500t DVB-T2',
    '39': 'Agora 550',
    '41': 'Agora 600',
    '42': 'Kamai 650',
    '45': 'Aria 550c',
    '48': 'Aria 500c (regular DVB-C)',
    '49': 'Kamai 500x',
    '47': 'A160 - Enable Stack',
    '54': 'Kamai 650',
    '55': 'Kamai 650m ZB',
    '56': 'Kamai 650m UP',
    '57': 'Amulet 650 ZB',
    '58': 'Amulet 650 UP',
    '59': 'Amulet 650m ZB',
    '60': 'Amulet 650m UP',
    '61': 'A160 - Enable Stack',
    '62': 'Kamai 6 or Aria 6 UP',
    '63': 'Kamai 6 or Aria 6 TP',
    '65': 'Kamai 6 or Aria 6 UB',
    '67': 'Amulet500 7221UB',
}


def get_stb_ident(serial_no):
    """     Get the STB identification string from the serial number

    The first 2 characters of the serial number string identify the
    platform, as can be seen in the STB label guide ( AM-000035-PR )

    This function is just a wrapper with protection if the platform
    has not been added to the STB_IDENTS dictionary

    Args:
        serial_no  ( str ) - The serial number of the STB to get the
                             identify string of.

    Returns:
        On Success ( str ) - The STB identification string
        On Failure ( str ) - 'Unknown'
    """

    prefix = serial_no[:2]

    try:
        ret = STB_IDENTS[prefix]
    except KeyError:
        ret = 'Unknown'

    return ret
