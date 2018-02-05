"""     Docstring
"""

from __future__ import division

# python library imports
from threading import Thread
from urlparse import urlparse
from ftplib import FTP

import time
import sys
import os

def download_from_ftp(build_url):
    """     Downloads a file from an FTP server, specified by build_url
    """

    print 'downloading file from FTP url: %s' % (build_url)

    # create a downloader Thread and set it off
    downloader = FtpDownloadThread(build_url)
    downloader.start()

    while downloader.get_file_size() == 0:
        # Wait until the file size is determined before tracking the progress
        time.sleep(0.25)

    file_size = 0

    local_file_name = build_url.split('/')[-1]

    while file_size < downloader.get_file_size():

        file_size = os.stat(local_file_name).st_size

        time.sleep(0.5)

    return local_file_name

class FtpDownloadThread(Thread):
    """     Thread to go away and download a file from an FTP server
    """

    def __init__(self, file_url):

        Thread.__init__(self, target=self.worker, args=())

        self.daemon = True

        self.file_url = file_url

        self._file_size = 0

    def worker(self):
        """     Worker method to connect to the server and download the file
        """

        parsed_url = urlparse(self.file_url)

        # Get the IP address or domain name from the URL e.g. 10.0.4.11
        ftp_server = parsed_url.netloc

        # Get the directory where the image is located
        #   e.g. software_release/broadcom/mv/
        file_path = '/'.join(parsed_url.path.split('/')[1:-1])

        # Get the image name e.g.:
        #  pkg_entone_hd_brcm_bin.<version_str>.verimatrix3.bin
        file_name = parsed_url.path.split('/')[-1]

        ftp_conn = FTP(ftp_server)

        ftp_conn.login()

        # Change to the directory where the image is located on the server
        ftp_conn.cwd(file_path)

        ftp_conn.sendcmd('TYPE i')

        self._file_size = ftp_conn.size(file_name)

        ftp_conn.retrbinary('RETR %s' % (file_name), open(file_name, 'wb').write)

        ftp_conn.quit()

    def get_file_size(self):
        """     Return the expected file size
        """

        return self._file_size


def main():
    if len(sys.argv) == 3:
        if 'ftp://' not in sys.argv[1]:
            print 'invalid ftp url: %s' % (sys.argv[1])
            sys.exit(1)
        elif 'ftp://' not in sys.argv[2]:
            print 'invalid ftp url: %s' % (sys.argv[2])
            sys.exit(1)

        else:

            print 'downloaded file: %s'  % (download_from_ftp(sys.argv[1]))
            print 'downloaded file: %s'  % (download_from_ftp(sys.argv[2]))

    else:
        print 'pass 2 args as python downloader.py $FTP_1 $FTP_2'

if __name__ == '__main__':
    main()
