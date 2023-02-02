
from os import environ


DB_HOST = environ.get('DB_HOST', 'localhost')
DB_USER = environ.get('DB_USER', 'root')
DB_PASSWORD = environ.get('DB_PASSWORD', 'mjm')
DB_NAME = environ.get('DB_NAME', 'lite')
DB_PORT = environ.get('DB_PORT', 3309)

BRANCH_ID = environ.get('BRANCH_ID')