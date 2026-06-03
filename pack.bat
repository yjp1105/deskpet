@echo off
chcp 65001
echo 正在安装打包工具 PyInstaller...
pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
echo ---------------------------------------
echo 开始打包义勇桌宠（隐藏控制台，单文件模式）...
pyinstaller --noconsole --onefile "C:\Users\YJP\Desktop\deskpet\fg.py"
echo ---------------------------------------
echo 打包成功！请在 C:\Users\YJP\Desktop\deskpet\ 目录下的 dist 文件夹里寻找编译好的 exe 文件。
pause
