cp ~/server.tar.gz ./
tar xf server.tar.gz
pgrep 'gunicorn' | xargs kill
source myenv/bin/activate
gunicorn --reload --log-level=DEBUG -w 4 -b 0.0.0.0:39997 server:app &