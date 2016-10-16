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


    def add_or_update_user_session(self, key, user_id, lis_result_sourcedid, lis_outcome_service_url, resource_link_id):
        """
        We assume that for each application we have a single secret.  We need to identify the users
        based on their ID and key, so we can return the correct assignment
        If the user session does not exist, add it.  If the user session does exist, update it
        :param params: A dict of the parameters passed by the LTI Consumere

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
        :param user_id: The User ID sent across from Canvas.
        :return: A unix username
        """
        try:
            user_obj = self.db.query(LtiUser).filter(LtiUser.user_id == user_id).one()
        # if user_obj:
            print('User already exists, getting user %s' % user_obj.unix_name)
            return user_obj.unix_name
        except NoResultFound:
            total_users = len(self.db.query(LtiUser).all())
            new_unix_name = 'user-%d-%s' % ((total_users + 1), os.environ['ASSESSMENT_NAME'])
            print('Adding new user %s' % new_unix_name)
            self.add_user(user_id, new_unix_name)
            return new_unix_name

    def add_user(self, user_id, username):
        self.db.add(LtiUser(user_id=user_id, unix_name=username))
        with open('/home/instructor/data_science', 'a') as f:
            f.write('\n%s' % username)
        try:
            self.db.commit()
            self.log.info('Added new user %s to the database' % username)
        except (IntegrityError, FlushError) as e:
            self.db.rollback()
            raise ValueError(*e.args)
