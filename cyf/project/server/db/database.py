import configparser

from peewee import SqliteDatabase

conf = configparser.ConfigParser()
conf.read('conf/conf.ini')

db = SqliteDatabase(conf['log']['sqlite3_file'])
