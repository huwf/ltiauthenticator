import os

from oauthlib.oauth1 import SignatureOnlyEndpoint
from tornado import gen
from ltiauthenticator.lti_db import LtiDB, LtiUserCourse
from ltiauthenticator import LocalLTIAuthenticator, LTIAuthenticator
from ltiauthenticator.lti_validator import LTIValidator

connection_string = os.environ.get('LTI_DB', 'sqlite:///lti.db')
db = LtiDB(connection_string)


class NBGraderAuthenticator(LTIAuthenticator):

    # @gen.coroutine
    async def authenticate(self, handler, data=None):
        self.log.debug("calling authenticate in LTIAuthenticator\n")
        validator = LTIValidator()
        signature_authenticate = SignatureOnlyEndpoint(validator)

        request = handler.request

        self.log.debug('self.enable_auth_state: %s' % self.enable_auth_state)
        self.log.debug('self: %s' % self)
        self.log.debug('%s://%s%s\n' % (request.protocol, request.host, request.uri))
        self.log.debug('%s\n\n' % str(dict(request.headers)))
        # self.log.debug('%s\n\n' % request.body.decode('utf-8'))
        body = request.body.decode('utf-8')
        for p in body.split('&'):
            self.log.debug('%s' % p)
        self.log.debug('\nFinished self.log.debugging body.split\n')

        # Since we're behind a proxy we need to hardcode the URL here for the signature
        url = '%s://%s/hub/login' % (os.environ.get('PROTO', 'http'), os.environ.get('DOMAIN', 'localhost'))
        self.log.info('url: %s' % url)
        x = signature_authenticate.validate_request(url, request.method, request.body.decode('utf-8'), request.headers)
        self.log.debug("Authenticated? %s\n\n" % str(x[0]))

        if x[0]:

            user = db.get_user(handler.get_argument("user_id"))

            if not user:
                user = db.add_user(handler.get_argument('user_id'))

        else:
            return None

        username = user.unix_name
        role = handler.get_argument('roles')

        upper_r = role.upper()
        self.log.debug('upper_r: %s', upper_r)
        allow_admin = 'TeachingAssistant'.upper() in upper_r or 'Instructor'.upper() in upper_r or 'ContentDeveloper'.upper() in upper_r

        is_admin = bool(allow_admin and handler.get_argument('custom_admin', ''))
        if is_admin:
            username = 'instructor'

        course_name = handler.get_argument('custom_course', '')
        if course_name not in user.courses:
            user.courses.append(LtiUserCourse(user_id=user.user_id, course=course_name))
            db.db.commit()

        firstname = handler.get_argument('lis_person_name_given', '')
        surname = handler.get_argument('lis_person_name_family', '')
        env = os.environ.copy()

        auth_state = {'course': course_name}
        for var in ['JUPYTERHUB_API_URL', 'JUPYTERHUB_API_TOKEN', 'GRADEBOOK_DB', 'MONGO_PW']:
            auth_state[var] = env[var]

        auth_state['first_name'] = firstname
        auth_state['surname'] = surname

        self.log.debug('auth_state: %s' % auth_state)
        ret = {
            'name': username, 'auth_state': auth_state, 'admin': is_admin
        }

        # self.log.debug(ret)

        return ret

    @gen.coroutine
    def pre_spawn_start(self, user, spawner):
        auth_state = yield user.get_auth_state()
        if not auth_state:
            self.log.error('NO AUTH STATE!')
            return
        else:
            self.log.debug('AUTH STATE HERE!')

        # We need these variables to enroll students
        for var in ['JUPYTERHUB_API_URL', 'JUPYTERHUB_API_TOKEN', 'GRADEBOOK_DB', 'MONGO_PW']:
            spawner.environment[var] = auth_state[var]

        if spawner.name:
            self.log.debug('Spawner has name: %s' % spawner.name)
            spawner.environment['COURSE'] = spawner.name
            self.log.debug('Added %s to environment %s' % (spawner.name, spawner.environment))
        else:
            spawner.environment['COURSE'] = auth_state['course']
        spawner.environment['FIRST_NAME'] = auth_state['first_name']
        spawner.environment['LAST_NAME'] = auth_state['surname']
        spawner.environment['USERNAME'] = user.name
        spawner.environment['ADMIN_API_TOKEN'] = spawner.environment['JUPYTERHUB_API_TOKEN']
       
        self.log.debug('spawner.environment: %s\n\n\n' % spawner.environment)


class LocalNBGraderAuthenticator(LocalLTIAuthenticator, NBGraderAuthenticator):

    """A version that mixes in local system user creation"""
    pass
