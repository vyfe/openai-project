# 服务端文件打包
# 解压后执行python3 cyf/project/server/server.py 运行
import os
import tarfile


def create_tarball(output_filename, extensions):
    # 获取当前目录
    current_dir = os.getcwd()

    # 创建一个 tar.gz 文件
    with tarfile.open(output_filename, "w:gz") as tar:
        # 遍历当前目录的文件
        for root, dirs, files in os.walk(current_dir):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, current_dir)

                # Production configuration and private keys belong to the
                # running server, not to a deployable source archive.
                if relative_path == os.path.join("conf", "conf.ini") or file.endswith(".priv"):
                    continue

                # 检查文件后缀
                if any(file.endswith(ext) for ext in extensions):
                    # 将文件添加到 tar.gz 文件中
                    tar.add(file_path, arcname=relative_path)


if __name__ == "__main__":
    # 需要打包的文件后缀
    extensions = ['.py', '.ini', '.sh', '.sql']
    # 输出 tar.gz 文件的名称
    output_filename = 'dist/server.tar.gz'
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    create_tarball(output_filename, extensions)
