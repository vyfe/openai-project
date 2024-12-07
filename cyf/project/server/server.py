import json
import sqlite3

from flask import Flask, request

app = Flask(__name__)
conn = sqlite3.connect("test.db")



@app.route('/test', )
def health_check():
    print(request.values)
    try:
        data = request.get_json()
        return json.dumps(data), 200
    except json.JSONDecodeError:
        return 'Not OK', 500

@app.route('/dialog', methods=['POST'])
def dialog():
    # 对话接口
    print(request.values)
    try:
        # 观察是独立文字还是上下文
        data = request.get_json()
        # sqlite3数据库写日志
        return json.dumps(data), 200
    except json.JSONDecodeError:
        return 'Not OK', 500

if __name__ == '__main__':
    # 若不存在sqlite3，初始化
    app.run(host='0.0.0.0', port=80)