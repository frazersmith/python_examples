class EmailError(RuntimeError):
    pass

import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import os


from robot.libraries.BuiltIn import BuiltIn
from robot.version import get_version
from robot.api import logger


#GMAIL_USERNAME = 'aminosqa@gmail.com'
#GMAIL_PASSWORD = 'Aminocom202'

GMAIL_USERNAME = 'aminocom.aminorobot@gmail.com'
GMAIL_PASSWORD = 'Aminocom101'

class Email(object):

    ROBOT_LIBRARY_SCOPE = 'TEST SUITE'
    ROBOT_LIBRARY_VERSION = get_version()


    def __init__(self):
        """ Amino Email Library by Frazer Smith.

        This library is designed for use with Robot Framework.

        This is a very simple email helper to allow sending of status or message emails during or after test runs.

        """
       
        pass

    def send_email(self, email_subject, recipient, body_of_email, imagefile=None):
        """  Send a MIMEMultipart email to a single email address.
        
        Makes use of the aminocom.aminorobot account in Gmail

        RIDE Examples:-
        | Send Email	| This is the subject	| validation@aminocom.com	| ${email_body}			|					|
        | Send Email	| VideotestFailure		| validation@aminocom.com	| Please review image	| /tmp/image1.png	|
        
        Python Example:
        | email_body = "This is the body of the email"
        | email.send_email("This is the subject","validation@aminocom.com",email_body, imagefile="/tmp/capture1.png")

        """


        msg = MIMEMultipart()
        msg['Subject'] = email_subject
        msg['From'] = GMAIL_USERNAME
        msg['To'] = recipient
        body = MIMEText(body_of_email)
        msg.attach(body)
        if imagefile is not None:
            try:
                img_data = open(imagefile, 'rb').read()
            except IOError:
                raise EmailError("Unable to find imagefile '%s'" % imagefile)
            img = MIMEImage(img_data, name=os.path.basename(imagefile))
            msg.attach(img)

        session = smtplib.SMTP('smtp.gmail.com',587)
        session.ehlo()
        session.starttls() 
        session.login(GMAIL_USERNAME, GMAIL_PASSWORD)

        session.sendmail(GMAIL_USERNAME, recipient, msg.as_string())
        session.quit()




    def send_suite_teardown_status_email(self, recipient):
        """  Send a text email to a single recipient which explains the suite status. 

        Note: This depends upon variables which only exist during Suite Teardown, so only
        use this keyword there.

        Example:-
        | Send Suite Teardown Status Email	| fsmith@aminocom.com	|

        """

        try:
            status = BuiltIn().replace_variables('${SUITE STATUS}')
        except:
            logger.warn("A suite status email can only be sent as part of 'Suite Teardown'")
            return
       
 
        if recipient == None:
            return
        if recipient == "":
            return

        subject = "Aminorobot Test Status - %s" % status
  

        body = """
Test Suite: %s\r\n
Status: %s\r\n
Message: %s\r\n
""" % (BuiltIn().replace_variables('${SUITENAME}'), status, BuiltIn().replace_variables('${SUITE MESSAGE}'))

        self.send_email(subject, recipient, body)

