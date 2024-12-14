import configparser
import os
from PyInstaller.__main__ import run

conf = configparser.ConfigParser()
# 针对打包文件获取路径
conf.read('conf/conf.ini', encoding="UTF-8")
version = conf["common"]["version"]

# 打包客户端

def find_data_files():
    # 定义需要包含的文件扩展名后缀
    include_extensions = {'.ini', '.tcl', '.pub', '.ttf', '.otf', '.ico', '.json'}

    # 要打包的文件
    data_files = []

    # 遍历当前目录及其子目录
    for root, dirs, files in os.walk('.'):
        for file in files:
            if any(file.endswith(ext) for ext in include_extensions):
                # 添加文件路径和目标路径
                relative_path = os.path.relpath(os.path.join(root, file), '.')
                target_path = os.path.dirname(relative_path)
                data_files.append((relative_path, target_path))

    # customTkinter样式文件也需要打包，所以手动加一项
    data_files.append(
        ("C:/Users/vyfe/AppData/Local/Programs/Python/Python313-32/Lib/site-packages/customtkinter/assets", "customtkinter/assets"))
    return data_files


def build_exe(script_name):
    # 查找依赖文件
    data_files = find_data_files()

    # 构建 PyInstaller 参数列表
    opts = [
        '--onefile',
        '--windowed',
        '--name',
        f"Chat-V{version}"
    ]

    # 添加每个数据文件到参数列表
    for source, destination in data_files:
        opts.append('--add-data')
        opts.append(f'{source};.\\{destination}')
    opts.append(script_name)
    # 执行 PyInstaller
    run(opts)

if __name__ == '__main__':
    # 将 'app.py' 替换为你的主应用程序文件
    build_exe('client.py')