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

class LTIMixin(OAuthMixin):
    _OAUTH_VERSION = '1.0a'


class LTILoginHandler(BaseHandler):
    assessments_whitelist = ['stats', 'management', 'visualisation', 'introduction', 'data_science']

    @gen.coroutine
    def post(self):
        # TODO: Check if state argument needs to be checked
        username = yield self.authenticator.get_authenticated_user(self, None)

        if username:

            db = LtiDB('sqlite:///user_session.db')
            params = self._get_lti_params()
            db.add_or_update_user_session(
                key=params['oauth_consumer_key'],
                user_id=params['user_id'],
                lis_result_sourcedid=params.get('lis_result_sourcedid', ''),
                lis_outcome_service_url=params['lis_outcome_service_url'],
                resource_link_id=params['resource_link_id']
            )

            # username = self._map_username(username, assessment)
            user = self.user_from_username(username)
            # Hardcode these courses for now.
            os.makedirs('/home/%s/intro')
            os.makedirs('/home/%s/management')
            os.makedirs('/home/%s/stats')
            os.makedirs('/home/%s/visualisation')

            user.spawner.host_homedir = '/home/{username}/%s' % os.environ.get('ASSESSMENT_NAME', 'intro')
            self.set_login_cookie(user)
            self.redirect(url_path_join(self.hub.server.base_url, 'home'))
        else:
            # todo: custom error page?
            raise web.HTTPError(403)


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
                print('Arg %s: %s' % (lti, arg))
            else:
                self.log.warning('Arg %s does not exist' % lti)
        return params




class LTIAuthenticator(OAuthenticator):
    login_handler = LTILoginHandler

    @gen.coroutine
    def authenticate(self, handler, data=None):
        print("calling authenticate!\n")
        validator = LTIValidator()
        signature_authenticate = SignatureOnlyEndpoint(validator)

        request = handler.request

        print('%s://%s%s\n' % (request.protocol, request.host, request.uri))
        print('%s\n\n' % str(dict(request.headers)))
        # print('%s\n\n' % request.body.decode('utf-8'))
        body = request.body.decode('utf-8')
        for p in body.split('&'):
            print('%s' % p)
        print('\nFinished printing body.split\n')

        # Since we're behind a proxy we need to hardcode the URL here for the signature
        # Assume that it's in the format https://assessment_name.domain/hub/login
        url = 'https://%s.%s/hub/login' % (os.environ.get('ASSESSMENT_NAME', 'intro'), os.environ.get('DOMAIN', ''))
        x = signature_authenticate.validate_request(url, request.method, request.body.decode('utf-8'), request.headers)
        print("Authenticated? %s\n\n" % str(x[0]))

        # if x[0]:
            # return handler.get_argument("user_id")
        db = LtiDB('sqlite:///user_session.db')
        username = db.get_user(handler.get_argument("user_id"))

        return 'instructor'

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


