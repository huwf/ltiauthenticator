# LTI Authenticator

The ltiauthenticator package provides authentication for Jupyterhub using the LTI (specification)[https://www.imsglobal.org/specs/ltiv1p1/implementation-guide]. 
It is designed that it should work out of the box, but there are some hardcoded parts which were specific to my implementation. I will do my best to get those out, but if I miss some, 
feel free to make a PR and I'll put them in.

It works as an authenticator for Jupyterhub, and is an LTI provider, so does not do anything on the receiver side. LMSes like Canvas or blackboard should be able to cope with the receiver side.
On Canvas, you need to create an app under settings, and make sure that the Launch URL goes to https://your-domain.com/hub/login. A key and secret are required to generate the LTI certificate and
they need to go here. Keep a note of them, you will be able to see the key again, but not the secret.  

Also set up an assignment as well with a submission type
as "external tool" and then select the app you just created from the list. Note, if you change the domain or anything, you need to change both the app and the assignment separately.

To install you can install locally with pip

    git clone https://github.com/huwf/ltiauthenticator
    pip install -e ltiauthenticator/

To use you need to include the following in your `jupyterhub_config.py` file:

c.JupyterHub.authenticator_class = 'ltiauthenticator.LTIAuthenticator'

It is also possible to use the "local" version, which maps the canvas names to system names. Because the canvas names in my implementation were too big for Linux, I mapped each from user-1 to user-n
incrementing each time a new user was added..

## Setting up a key and a secret

You will need to set up a key or a secret somewhere which are used to sign requests which form the OAuth part of the LTI protocol. In your LMS there will be an option to create these for an external app, 
either through an API, or through a menu somewhere. 

These need to also be saved on the server you are running JupyterHub. How you wish to store these is down to your implementation. By default, they are
stored as environment variables `LTI_KEY` and `LTI_SECRET`. This is detailed in the `authentication_information` function of validate_lti.py, which you can override if you wish for something more secure.

## Customisation

I made heavy use of environment variables for storing connection strings and such, which will need to be present on your server. Most of the time they should default to something sensible, but not necessarily.
The values are:

    LTI_KEY=""
    LTI_SECRET=""
    LTI_DB="sqlite:///lti.db"
    NONCES_DB="sqlite:///nonces.db"
    PROTO="http"
    DOMAIN="localhost"

Depending on your implementation, you may very well be behind a reverse proxy running SSL, so you will need to specify this (aside from development where it goes to http://localhost by default). This is because
the request signs including the URL, and the URL internally may be different than your public URL.

## Superuser
For my implementation, I had a special login for the lecturer with the "instructor" user. This is activated when the user is either a teacher, teaching assistant, or similar, and they have an `allow_admin=true` flag
in the request. This requires two separate applications in your LMS (make sure the students can't see this one! Although it should also not matter if they do, because they will be in the wrong group.

