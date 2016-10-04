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

# Things for the timestamp and nonce validation
Base = declarative_base()

class TimestampNonce(Base):
    __tablename__ = 'nonces'

    id = Column(Integer, autoincrement=True, primary_key=True)
    username = Column(String)
    timestamp = Column(Integer)
    nonce = Column(String)

    def __repr__(self):
        return 'TimestampNonce(<id: %d username: %s timestamp: %d nonce: %s>)' \
               % (self.id, self.username, self.timestamp, self.nonce)

class NoncesDB(object):


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


    def add_nonce(self, user, timestamp, nonce):

        nonce = TimestampNonce(username=user, timestamp=timestamp, nonce=nonce)
        self.db.add(nonce)
        try:
            self.db.commit()
        except (IntegrityError, FlushError) as e:
            self.db.rollback()
            raise ValueError(*e.args)
        return nonce

    def check_valid_timestamp_and_nonce(self, timestamp, nonce):
        """
        Tries to find the nonce in the database table.  If it exists, then it's not valid
        :param nonce: The nonce to search for
        :param timestamp: the timestamp to search for
        :return:
        """
        import time

        try:
            timestamp = int(timestamp)
        except:
            timestamp = 0
        now = time.time()
        valid_timestamp = timestamp

        if not timestamp:
            valid_timestamp = 0
        elif now - timestamp > 900:
            valid_timestamp = 0
        elif now - timestamp < 0:
            valid_timestamp = 0
        result = self.db.query(TimestampNonce)\
                .filter(TimestampNonce.nonce == nonce)\
                .filter(TimestampNonce.timestamp >= valid_timestamp).all()

        return len(result) == 0 and valid_timestamp > 0
