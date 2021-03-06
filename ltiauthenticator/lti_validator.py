from oauthlib.oauth1 import RequestValidator
from .authenticator_db import NoncesDB
from .lti_db import LtiDB
import os

connection_string = os.environ.get('LTI_DB', 'sqlite:///lti.db')

class LTIValidator(RequestValidator):


    @property
    def client_key_length(self):
        return 0, 64

    @property
    def nonce_length(self):
        return 20, 64

    @property
    def enforce_ssl(self):
        return False

    @property
    def authentication_information(self):
        key = os.environ.get('LTI_KEY', '')
        secret = os.environ.get('LTI_SECRET', '')
        lti_db = LtiDB(connection_string)
        lti_db.add_key_secret(key, secret)
        return {'get_key': key, key: secret}

    def get_client_secret(self, client_key, request):
        return self.authentication_information[client_key]

    def validate_client_key(self, client_key, request):
        return client_key == self.authentication_information.get('get_key', '')

    def validate_timestamp_and_nonce(self, client_key, timestamp, nonce,
                                     request, request_token=None, access_token=None):

        db = NoncesDB(os.environ.get('NONCES_DB', 'sqlite:///timestamp.db'))

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




