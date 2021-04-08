import psycopg2
import logging
from psycopg2.extras import execute_values

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class PostgresRDS(object):
    def __init__(self, host=None, username=None, password=None, db_name=None, port=5432, connect_timeout=50, db_uri=None, cursor_factory=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.db_name = db_name
        self.connect_timeout = connect_timeout
        self.cursor_factory = cursor_factory
        self.db_uri = db_uri
        self.connect()

    def connect(self, connect_db_name=None, cursor_factory=None):
        if connect_db_name:
            self.db_name = connect_db_name
        
        if cursor_factory:
            self.cursor_factory = cursor_factory
        
        if self.db_uri:
            self.connection = psycopg2.connect(self.db_uri)
        elif self.db_name:
            self.connection = psycopg2.connect(
                host=self.host,
                user=self.username,
                password=self.password,
                dbname=self.db_name,
                connect_timeout=self.connect_timeout,
                port=self.port
            )
        else:
            self.connection = psycopg2.connect(
                host=self.host,
                user=self.username,
                password=self.password,
                connect_timeout=self.connect_timeout,
                port=self.port
            )

        if self.cursor_factory:
            self.cursor = self.connection.cursor(cursor_factory=self.cursor_factory)
        else:
            self.cursor = self.connection.cursor()
        self.connection.autocommit=True

    def get_connection(self):
        return self.connection

    def get_cursor(self):
        return self.cursor

    def exec_select(self, select, params=None):
        try:
            if params:
                result = self.cursor.execute(select, params)
            else:
                result = self.cursor.execute(select)
        except psycopg2.Error as e:
            logger.exception('Error while executing SQL statement %s.\n Exception: %s' % (select, str(e)))
            return None
        logger.info('Statement %s executed succesfully.' % self.cursor.query)
        return self.cursor.fetchall()

    def exec_sql(self, sql, params=None):
        try:
            if params:
                self.cursor.execute(sql, params)
            else:
                self.cursor.execute(sql)
        except psycopg2.Error as e:
            logger.exception('Error while executing SQL statement %s with params %s.\n Exception: %s' % (sql, params, str(e)))
            return False
        logger.info('Statement %s executed succesfully.' % self.cursor.query)
        return True

    def upsert_values(self, table, values, on_conflict_statement, set_statement, page_size=100):
        try:
            execute_values(self.cursor, (f'INSERT INTO {table} VALUES %s {on_conflict_statement}'
                                 f' DO UPDATE {set_statement};'), values(),
                           page_size=page_size)
        except psycopg2.Error as e:
            logger.exception('Error while executing SQL statement.\n Exception: %s' % (str(e)), exc_info=True)
            return False
        except Exception as ex:
            logger.exception('Error while executing SQL statement.\n Exception: %s' % (str(e)), exc_info=True)
            return False
        logger.info('Statement %s executed succesfully.' % self.cursor.query)
        return True

    def close(self):
        self.cursor.close()
        self.connection.close()
