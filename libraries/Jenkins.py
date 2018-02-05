"""
Jenkins.py
"""

from robot.api import logger

import os
import requests

# Sets functions which we can use as robot key words
__all__ = ['get_is_new_build']

def get_is_new_build(old_git_tag, new_git_tag):
    """     Determine if s/w should have changed and if it has changed

    Examples:
    | ${old_git_tag}=          | FTI.Send Fti Command            | info get gittag     |
    | FTI.Upgrade Fti          | http://host/mc2.mcfs            |                     |
    | ${new_git_tag}=          | FTI.Send Fti Command            | info get gittag     |
    | Get Is New Build         | ${old_git_tag}                  | ${new_git_tag}      |
    |                          |                                 |                     |
    | ${old_git_tag}=          | Send Command And Return Output  | cat /etc/gittagdesc |
    | STBRC.Send Stbrc Upgrade | http://host/mc2.mcfs            |                     |
    | ${new_git_tag}=          | Send Command And Return Output  | cat /etc/gittagdesc |
    | Get Is New Build         | ${old_git_tag}                  | ${new_git_tag}      |
    """
    strp_old_tag = _strip_prompt_from_git_tag(old_git_tag)
    strp_new_tag = _strip_prompt_from_git_tag(new_git_tag)

    logger.debug('FTI: old git tag: %s' % (strp_old_tag))
    logger.debug('FTI: new git tag: %s' % (strp_new_tag))

    if _get_is_downstream():
        logger.debug('FTI: is downstream build, tags should be different')

        if strp_old_tag == strp_new_tag:
            dbg_msg = 'Triggered by upstream but software not upgraded'
            logger.warn(dbg_msg)
            # Turn off failing until migration to new server/ git plugin
            #BuiltIn().fail(dbg_msg)
        else:
            logger.debug('FTI: git tags are different, continuing')
    else:
        logger.debug('FTI: started by user, ignoring git tags')

def _get_is_downstream():
    """     Gets if the Jenkins build under test is a new version

    This method uses the 'project' and 'build_num' variables from
    the robot framework script to determine a REST API URL from the
    Jenkins server and uses the JSON response to check the reason
    why the test run was triggered against a list of known reasons

    Args:
        None
    Returns:
        True  ( bool ) - Is a new build (triggered by downstream)
        False ( bool ) - Is not a new build (triggered by user)
    """

    job_url = os.environ['JOB_URL']
    build_num = os.environ['BUILD_NUMBER']

    get_url = '%s/%s/api/json' % (job_url, build_num)

    logger.debug('GET URL: %s' % get_url)

    response = requests.get(get_url)

    if response.status_code != 200:
        logger.warn('FTI: Unable to access Jenkins API')
        return False

    json_data = response.json()

    try:
        reason = json_data['actions'][1]['causes'][0]['shortDescription']
        logger.debug('FTI: Build reason: "%s"' % reason)
    except KeyError:
        # Assume triggered by user if we can't work it out
        logger.warn('FTI: Unable to determine build cause from JSON API')
        return False

    if 'Started by upstream' in reason:
        return True
    else:
        return False

def _strip_prompt_from_git_tag(git_tag):
    """     strips chars from 'info get gittag' for comparison

    Args:
        git_tag ( str ) - return from 'info get gittag' to strip

    Returns:
        ret     ( str ) - the git tag stripped of the prompt
    """
    logger.trace('FTI: stripping git tag "%s"' % git_tag)
    ret = git_tag.replace(' ', '')
    ret = ret.replace('FT>', '')
    ret = ret.replace('\n', '')

    logger.trace('FTI: Stripped git tag: "%s"' % ret)
    return ret
