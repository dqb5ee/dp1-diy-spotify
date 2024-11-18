import os
import json
import mysql.connector
import boto3
from chalice import Chalice

app = Chalice(app_name='backend')
app.debug = True

# s3 things
S3_BUCKET = 'dqb5ee-dp1-spotify'
s3 = boto3.client('s3')

# base URL for accessing the files
baseurl = 'http://dqb5ee-dp1-spotify.s3-website-us-east-1.amazonaws.com/'

# database things
DBHOST = os.getenv('DBHOST')
DBUSER = os.getenv('DBUSER')
DBPASS = os.getenv('DBPASS')
DB = os.getenv('DB')
db = mysql.connector.connect(user=DBUSER, host=DBHOST, password=DBPASS, database=DB)
cur = db.cursor()

# file extensions to trigger on
_SUPPORTED_EXTENSIONS = (
    '.json'
)

@app.on_s3_event(bucket=S3_BUCKET, events=['s3:ObjectCreated:*'])
def s3_handler(event):
    if _is_json(event.key):
        # get the file, read it, load it into JSON as an object
        response = s3.get_object(Bucket=S3_BUCKET, Key=event.key)
        text = response["Body"].read().decode()

        # Check if the file content is empty
        if not text.strip():
            app.log.error("File is empty or contains only whitespace: %s", event.key)
            return

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            app.log.error("Failed to parse JSON from file %s: %s", event.key, str(e))
            return

        # parse the data fields 1-by-1 from 'data'
        TITLE = data.get('title', '')
        ALBUM = data.get('album', '')
        ARTIST = data.get('artist', '')
        YEAR = data.get('year', '')
        GENRE = data.get('genre', '')

        # get the unique ID for the bundle to build the mp3 and jpg URLs
        keyhead = event.key
        identifier = keyhead.split('.')
        ID = identifier[0]
        MP3 = baseurl + ID + '.mp3'
        IMG = baseurl + ID + '.jpg'

        app.log.debug("Received new song: %s, key: %s", event.bucket, event.key)

        # try to insert the song into the database
        try:
            add_song = ("INSERT INTO songs "
                        "(title, album, artist, year, file, image, genre) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)")
            song_vals = (TITLE, ALBUM, ARTIST, YEAR, MP3, IMG, GENRE)
            cur.execute(add_song, song_vals)
            db.commit()

        except mysql.connector.Error as err:
            app.log.error("Failed to insert song: %s", err)
            db.rollback()

def _is_json(key):
    return key.endswith(_SUPPORTED_EXTENSIONS)
