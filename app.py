from flask import Flask, request, jsonify

app = Flask(__name__)


# 路由一：处理 JSON 数据
@app.route('/algorithm1', methods=['POST'])
def algorithm1():
    data = request.json  # 获取 JSON 格式的数据
    # 处理数据并应用算法1
    # ...
    return jsonify({"message": "Algorithm 1 processed the data"})


# 路由二：处理表单数据
@app.route('/algorithm2', methods=['POST'])
def algorithm2():
    data = request.form  # 获取表单格式的数据
    # 处理数据并应用算法2
    # ...
    return jsonify({"message": "Algorithm 2 processed the data"})


# 其他路由和算法 ...

if __name__ == '__main__':
    app.run(debug=True)
