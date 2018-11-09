from oauthlib.oauth1 import RequestValidator
from sqlalchemy import (create_engine, ForeignKey, Column, String, Text,
    DateTime, Interval, Float, Enum, UniqueConstraint, Boolean, Integer)
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, column_property
from sqlalchemy.orm.exc import NoResultFound, FlushError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import and_
from sqlalchemy import select, func, exists, case, literal_column
from traitlets.config import LoggingConfigurable
import os
from nbgrader import api

# Things for the timestamp and nonce validation
Base = declarative_base()

class LtiUser(Base):
    """
    This converts the Canvas ID into something more readable and is a valid Linux name
    """
    __tablename__ = 'usermap'
    user_id = Column(String, primary_key=True)
    unix_name = Column(String)

    def __repr__(self):
        return 'User(<user_id: %s unix_name: %s>)' % (self.user_id, self.unix_name)


class LtiUserSession(Base):
    __tablename__ = 'nonces'

    id = Column(Integer, autoincrement=True, primary_key=True)
    key = Column(String)
    user_id = Column(String)
    lis_result_sourcedid = Column(String)
    lis_outcome_service_url = Column(String)
    resource_link_id = Column(String)

    def __repr__(self):
        return 'LtiUserSession(<key: %s, user_id %s, lis_result_sourcedid: %s, lis_outcome: %s resource_link_id: %s>)' \
            % (self.key, self.user_id, self.lis_result_sourcedid, self.lis_outcome_service_url, self.resource_link_id)


class LtiKeySecret(Base):
    __tablename__ = 'keysecret'

    key_secret_id = Column(Integer, primary_key=True, autoincrement=True)
    key_value = Column(String)
    secret = Column(String)

    def __repr__(self):
        return '<KeySecret object %d>' % self.key_secret_id

class LtiDB(LoggingConfigurable):

    def __init__(self, db_url):
        """Initialize the connection to the database.

        Parameters
        ----------
        db_url : string
            The URL to the database, e.g. ``sqlite:///nonces.db``

        """
        # create the connection to the database
        engine = create_engine(db_url, echo=True)
        self.db = scoped_session(sessionmaker(autoflush=True, bind=engine))

        # this creates all the tables in the database if they don't already exist
        Base.metadata.create_all(bind=engine)

    def get_key_secret(self):
        """
        Gets the key and secret from the database.
        Assumes that there is only one, which exists.
        If it does not exist an exception is raised
        :return:
        """
        try:
            key_secret = self.db.query(LtiKeySecret).one()
            return_value = {'get_key': key_secret.key_value, key_secret.key_value: key_secret.secret}
            print(str(return_value))
            return return_value

        except:
            self.log.warn('There is no key/secret pair in the database.  Returning None')
            return None


    def add_key_secret(self, key, secret):
        if not(self.get_key_secret()):
            self.db.add(LtiKeySecret(key_value=key, secret=secret))
            self.db.commit()
            self.log.info('New key/secret added to the database')
        else:
            self.log.warn('IGNORED attempt to add a new key/secret when one already exists')

    def add_or_update_user_session(self, key, user_id, lis_result_sourcedid, lis_outcome_service_url, resource_link_id):
        """
        We assume that for each application we have a single secret.  We need to identify the users
        based on their ID and key, so we can return the correct assignment
        If the user session does not exist, add it.  If the user session does exist, update it
        :param params: A dict of the parameters passed by the LTI Consumer

        :return:
        """

        user_session = self.get_user_session(user_id)
        if not user_session:
            self.db.add(LtiUserSession(key=key,
                                       user_id=user_id,
                                       lis_result_sourcedid=lis_result_sourcedid,
                                       lis_outcome_service_url=lis_outcome_service_url,
                                       resource_link_id=resource_link_id))
        else:
            setattr(user_session, 'lis_result_sourcedid', lis_result_sourcedid)
            setattr(user_session, 'resource_link_id', resource_link_id)

        try:
            self.db.commit()
        except (IntegrityError, FlushError) as e:
            self.db.rollback()
            raise ValueError(*e.args)
        return user_session

    def get_user_session(self, user_id):
        user_session = \
            self.db.query(LtiUserSession).filter(LtiUserSession.user_id == user_id).all()
        if len(user_session) > 0:
            return user_session[0]
        else:
            return None

    def get_user_by_unix_name(self, unix_name):
        try:
            return self.db.query(LtiUser).filter(LtiUser.unix_name == unix_name).one()
        except:
            self.log.error('No user by the UNIX name %s' % unix_name)

    def get_user(self, user_id):

        """
        When a user logs in, we check to see if they exist.  If they do not, create them
        The firstname and surname are optional.  If they are there and we are creating a
        user, put them into the CSV file.
        :param user_id: The User ID sent across from Canvas.
        :return: A unix username, or None if they do not exist
        """
        try:
            user_obj = self.db.query(LtiUser).filter(LtiUser.user_id == user_id).one()
        # if user_obj:
            print('User already exists, getting user %s' % user_obj.unix_name)
            return user_obj.unix_name
        except NoResultFound:
            return None

    def add_user(self, user_id, firstname='', surname=''):
        """
        Creates a new user map between the Canvas ID and unix name, adding to
        :param user_id: The User ID sent from Canvas
        :param firstname: The first name sent from Canvas
        :param surname: The surname sent from Canvas
        :return: The unix name of the new user
        """
        total_users = len(self.db.query(LtiUser).all())
        username = 'user-%d' % (total_users + 1)
        self.log.info('Adding new user %s' % username)
        # self.add_user(user_id, username, firstname, surname)

        self.db.add(LtiUser(user_id=user_id, unix_name=username))
        # with open('/home/instructor/students.csv', 'a') as f:
        #     print("About to write: %s,%s,%s" % (username, firstname, surname))
        #     f.write('%s,%s,%s\n' % (username, firstname, surname))
        try:
            self.db.commit()
            self.log.info('Added new user %s to the database' % username)
            return username
        except (IntegrityError, FlushError) as e:
            self.db.rollback()
            raise ValueError(*e.args)

    def add_to_nbgrader(self, unix_name, firstname, surname, email):
        """
        This function adds the user authenticated by LTI and adds to the student database
        :param unix_name: The new student's unix name
        :param firstname: The new student's first name
        :param surname: The new student's surname
        :param email: The new student's email address (if applicable)
        :return:
        """       
        db_url = os.environ.get('GRADEBOOK_DB', 'sqlite:///gradebook.db')
        self.log.info('Calling add_to_nbgrader with GRADEBOOK_DB as: %s' % db_url)
        gb = api.Gradebook(db_url)
        try:
            student = gb.add_student(unix_name, first_name=firstname, last_name=surname, email=email)
            return student
        except InvalidEntry as e:
            # We don't care
            self.log.info('Not adding student %r to database' % (unix_name))

