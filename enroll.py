from nbgrader.api import Gradebook, Student
from nbgrader.auth import JupyterHubAuthPlugin, Authenticator
from nbgrader.auth.jupyterhub import _query_jupyterhub_api, JupyterhubApiError
from traitlets.config import Config
import os

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class SubAuthenticator(Authenticator):
    def add_grader_to_course(self, student_id: str, course_id: str) -> None:
        logger.debug('Calling add_grader_to_course in SubAuthenticator')
        self.plugin.add_grader_to_course(student_id, course_id)

    def add_student_to_course(self, student_id: str, course_id: str) -> None:
        logger.debug('Calling add_student')
        self.plugin.add_student_to_course(student_id, course_id)


class SubAuthPlugin(JupyterHubAuthPlugin):

    def add_student_to_course(self, student_id: str, course_id: str) -> None:
        logger.debug('Calling add_student_to_course in plugin')
        logger.debug('JUPYTERHUB_API_URL: %s' % os.environ.get('JUPYTERHUB_API_URL'))
        if not course_id:
            logger.error(
                "Could not add student to course because the course_id has not "
                "been provided. Has it been set in the nbgrader_config.py?")
            return

        try:
            logger.debug('try block')
            group_name = "nbgrader-{}".format(course_id)
            jup_groups = _query_jupyterhub_api(
                method="GET",
                api_path="/groups",
            )
            logger.debug('jup_groups: %s' % jup_groups)
            if group_name not in [x['name'] for x in jup_groups]:
                # This could result in a bad request(JupyterhubApiError) if
                # there is already a group so first we check above if there is a
                # group
                _query_jupyterhub_api(
                    method="POST",
                    api_path="/groups/{name}".format(name=group_name),
                )
                logger.info("Jupyterhub group: {group_name} created.".format(
                    group_name=group_name))

            _query_jupyterhub_api(
                method="POST",
                api_path="/groups/{name}/users".format(name=group_name),
                post_data={"users": [student_id]}
            )
            logger.debug(f'Added {student_id} to {group_name}')
            # Saying student could be already here is because the post request
            # returns 200 even if the student_id was already in the group
            logger.info(
                "Student {student} added or was already in the Jupyterhub group: {group_name}".format(
                    student=student_id,
                    group_name=group_name))

        except JupyterhubApiError as e:
            # We assume user might be using Jupyterhub but something is not working
            err_msg = "Student {student} NOT added to the Jupyterhub group {group_name}: ".format(
                student=student_id,
                group_name=group_name
            )
            logger.error(err_msg + str(e))
            logger.error(
                "Make sure you set a valid admin_user 'api_token' in your config file before starting the service")

    def add_grader_to_course(self, student_id: str, course_id: str) -> None:
        logger.debug('Adding grader to course')
        if not course_id:
            logger.error(
                "Could not add grader to course because the course_id has not "
                "been provided. Has it been set in the nbgrader_config.py?")
            return

        try:
            group_name = "formgrader-{}".format(course_id)
            jup_groups = _query_jupyterhub_api(
                method="GET",
                api_path="/groups",
            )
            logger.debug('jup_groups %s' % jup_groups)
            if group_name not in [x['name'] for x in jup_groups]:
                # This could result in a bad request(JupyterhubApiError) if
                # there is already a group so first we check above if there is a
                # group
                _query_jupyterhub_api(
                    method="POST",
                    api_path="/groups/{name}".format(name=group_name),
                )
                logger.info("Jupyterhub group: {group_name} created.".format(
                    group_name=group_name))
            logger.debug('About to query Jupyterhub API')
            _query_jupyterhub_api(
                method="POST",
                api_path="/groups/{name}/users".format(name=group_name),
                post_data={"users": [student_id]}
            )
            # Saying instructor could be already here is because the post request
            # returns 200 even if the student_id was already in the group
            logger.info(
                "Instructor {instructor} added or was already in the Jupyterhub group: {group_name}".format(
                    instructor=student_id,
                    group_name=group_name))

        except JupyterhubApiError as e:
            # We assume user might be using Jupyterhub but something is not working
            err_msg = "Instructor {instructor} NOT added to the Jupyterhub group {group_name}: ".format(
                instructor=student_id,
                group_name=group_name
            )
            logger.error(err_msg + str(e))
            logger.error("Make sure you set a valid admin_user 'api_token' in your config file before starting the service")


if __name__ == '__main__':

    config = Config()
    config.Authenticator.plugin_class = SubAuthPlugin
    authenticator = SubAuthenticator(config=config)

    env = os.environ
    firstname = env['FIRST_NAME']
    surname = env['LAST_NAME']
    nbgrader_db = env['GRADEBOOK_DB']
    course_name = env['COURSE']
    unix_name = env['USERNAME']

    logger.debug('calling Gradebook %s %s %s' % (nbgrader_db, course_name, authenticator))
    with Gradebook(nbgrader_db, course_name, authenticator) as gb:
        logger.debug('\n\n\nInside Gradebook context\n\n\n %s' % vars(gb))
        student = {"first_name": firstname, "last_name": surname, "email": ''}
        gb.add_student(unix_name, **student)
        logger.debug('Created student')
        logger.debug('Created student\n\n')
        if unix_name == 'instructor':
            logger.debug('unix_name == instructor')
            authenticator.add_grader_to_course('instructor', course_name)
