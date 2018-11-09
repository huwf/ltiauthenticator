"""
Custom Authenticator which integrates Canvas LTI with Jupyterhub
This does not implement OAuth 2.0, but rather uses the LTI standard.
"""


from tornado.auth import OAuthMixin
from jupyterhub.auth import Authenticator, LocalAuthenticator
from tornado import auth, gen, web
from jupyterhub.handlers import BaseHandler
from jupyterhub.auth import LocalAuthenticator

from traitlets import Unicode, Dict
from .lti_validator import LTIValidator
from .lti_db import LtiDB
from oauthlib.oauth1 import SignatureOnlyEndpoint

from oauthenticator.oauth2 import OAuthenticator, OAuthLoginHandler
import requests
from jupyterhub.utils import url_path_join
from lti import ToolProvider
import os
import pwd, grp
import json

connection_string = os.environ.get('LTI_DB', 'sqlite:///lti.db')


class LTIMixin(OAuthMixin):
    _OAUTH_VERSION = '1.0a'


class LTILoginHandler(BaseHandler):
    assessments_whitelist = ['stats', 'management', 'visualisation', 'introduction', 'data_science']

    @gen.coroutine
    def post(self, *args, **kwargs):
        # TODO: Check if state argument needs to be checked
        username = yield self.authenticator.get_authenticated_user(self, None)

        if username:
            db = LtiDB(connection_string)
            params = self._get_lti_params()
            self.log.debug('params', str(params))
            db.add_or_update_user_session(
                key=params['oauth_consumer_key'],
                user_id=params['user_id'],
                lis_result_sourcedid=params.get('lis_result_sourcedid', ''),
                lis_outcome_service_url=params['lis_outcome_service_url'],
                resource_link_id=params['resource_link_id']
            )

            # username = self._map_username(username, assessment)
            user = self.user_from_username(username)

            self.set_login_cookie(user)
            self.redirect(url_path_join(self.hub.server.base_url, 'home'))
        else:
            # todo: custom error page?
            raise web.HTTPError(403)

    def get(self, *args, **kwargs):
        """
        If anyone who is not logged in reaches the server with a GET request, they have almost certainly been logged out
        The login handler requires POST as per the LTI standard
        :param args:
        :param kwargs:
        :return:
        """
        self.write('<h1>Logged Out</h1>'
                   '<p>You have been logged out, although your server may remain running for a few minutes. If you '
                   'wish to log in again, you will have to do so through the Canvas "Assignments page"</p>')


    def _get_lti_params(self):
        """
        This method gets the parameters needed to create a proper ToolProvider
        :param handler: A Tornado request
        :return: A dictionary in the form {param_name: param_value, ....}
        """
        params = {}
        lti_params = [
            'lis_result_sourcedid',
            'lis_outcome_service_url',
            'resource_link_id',
            'user_id',
            'oauth_consumer_key'
        ]

        for lti in lti_params:
            arg = self.get_argument(lti, False, True)
            if arg:
                params[lti] = arg
                self.log.debug('Arg %s: %s' % (lti, arg))
            else:
                self.log.warning('Arg %s does not exist' % lti)
        return params



class LTIAuthenticator(OAuthenticator):
    login_handler = LTILoginHandler

    @gen.coroutine
    def authenticate(self, handler, data=None):
        self.log.debug("calling authenticate!\n")
        validator = LTIValidator()
        signature_authenticate = SignatureOnlyEndpoint(validator)

        request = handler.request

        self.log.debug('%s://%s%s\n' % (request.protocol, request.host, request.uri))
        self.log.debug('%s\n\n' % str(dict(request.headers)))
        # self.log.debug('%s\n\n' % request.body.decode('utf-8'))
        body = request.body.decode('utf-8')
        for p in body.split('&'):
            self.log.debug('%s' % p)
        self.log.debug('\nFinished self.log.debuging body.split\n')

        # Since we're behind a proxy we need to hardcode the URL here for the signature
        url = '%s://%s/hub/login' % (os.environ.get('PROTO', 'http'), os.environ.get('DOMAIN', 'localhost'))
        self.log.info('url: %s' % url)
        x = signature_authenticate.validate_request(url, request.method, request.body.decode('utf-8'), request.headers)
        self.log.debug("Authenticated? %s\n\n" % str(x[0]))

        if x[0]:
            db = LtiDB(connection_string)
            role = handler.get_argument('roles')
            # TAs and instructors can get the instructor account if they choose the Admin app
#            allow_admin = role.upper() in self.get_admin_roles()
            upper_r = role.upper()
            self.log.debug('upper_r: %s', upper_r)
            allow_admin = 'TeachingAssistant'.upper() in upper_r or 'Instructor'.upper() in upper_r or 'ContentDeveloper'.upper() in upper_r
            if allow_admin and handler.get_argument('custom_admin', ''):
                return 'instructor'
            firstname = handler.get_argument('lis_person_name_given', '')
            surname = handler.get_argument('lis_person_name_family', '')
            user = db.get_user(handler.get_argument("user_id"))
            if allow_admin and handler.get_argument('custom_admin', ''):
                user = 'instructor'            
            if not user:
                user = db.add_user(handler.get_argument('user_id'))
            print('About to add %r to nbgrader' % user)            
            db.add_to_nbgrader(user, firstname, surname)
            return user

        return None

    def get_handlers(self, app):
        return [
            (r'/hub/login', self.login_handler),
            (r"/login", self.login_handler),
        ]

class LocalLTIAuthenticator(LocalAuthenticator, LTIAuthenticator):

    """A version that mixes in local system user creation"""
    pass



if __name__ == '__main__':
    pass


