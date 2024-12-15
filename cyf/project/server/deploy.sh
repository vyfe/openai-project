cp ~/server.tar.gz ./
tar xf server.tar.gz
pgrep -f 'python3 server.py' | xargs kill
source myenv/bin/activate && python3 server.py &