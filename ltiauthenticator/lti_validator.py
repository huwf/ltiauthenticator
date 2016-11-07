from oauthlib.oauth1 import RequestValidator
from .authenticator_db import NoncesDB
from .lti_db import LtiDB
import os

connection_string = os.environ.get('LTI_DB', 'sqlite:////srv/jupyterhub/lti.db')

class LTIValidator(RequestValidator):


    @property
    def client_key_length(self):
        return 0, 64

    @property
    def nonce_length(self):
        return 20, 64

    @property
    def authentication_information(self):
        # db = LtiDB(connection_string)
        # print('In the authentication_information property method')
        # return db.get_key_secret()
        with open('/srv/jupyterhub/LTI_KEY') as f:
            with open('/srv/jupyterhub/LTI_SECRET') as f2:
                key = f.read().strip()
                secret = f2.read().strip()
                lti_db = LtiDB(connection_string)
                lti_db.add_key_secret(key, secret)
                return {'get_key': key, key: secret}

    def get_client_secret(self, client_key, request):
        return self.authentication_information[client_key]

    def validate_client_key(self, client_key, request):
        return client_key == self.authentication_information.get('get_key', '')

    def validate_timestamp_and_nonce(self, client_key, timestamp, nonce,
                                     request, request_token=None, access_token=None):
        # unpw = ''
        # with open('/srv/jupyterhub/mysql') as f:
        #     unpw = f.read().strip()
        #
        # connection_string = 'mysql+mysqlconnector://%s@%s/lti' % (unpw, os.environ['MYSQL_HOST'])
        # db = NoncesDB(connection_string)
        db = NoncesDB('sqlite:///timestamp.db')

        valid_nonce = db.check_valid_timestamp_and_nonce(timestamp, nonce)
        if not valid_nonce:
            print('Invalid nonce!')
        return valid_nonce
        # return True

    def validate_redirect_uri(self, client_key, redirect_uri, request):
        return True

    @property
    def dummy_client(self):
        """Dummy client used when an invalid client key is supplied.

        :returns: The dummy client key string.

        The dummy client should be associated with either a client secret,
        a rsa key or both depending on which signature methods are supported.
        Providers should make sure that

        get_client_secret(dummy_client)
        get_rsa_key(dummy_client)

        return a valid secret or key for the dummy client.

        This method is used by

        * AccessTokenEndpoint
        * RequestTokenEndpoint
        * ResourceEndpoint
        * SignatureOnlyEndpoint
        """
        raise NotImplementedError("TODO: Implement this")




