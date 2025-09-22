@echo off
echo 图片水印工具示例
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python
    pause
    exit /b 1
)

REM 安装依赖
echo 正在安装依赖...
pip install -r requirements.txt

echo.
echo 使用方法示例:
echo 1. 处理当前目录: python photo_watermark.py .
echo 2. 处理指定目录: python photo_watermark.py "C:\Users\用户名\Pictures"
echo 3. 自定义设置: python photo_watermark.py . --font-size 30 --color red --position center
echo.

pause
