@echo off
chcp 65001 >nul
title 图片水印工具

echo.
echo ========================================
echo           图片水印工具
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到Python，请先安装Python 3.6+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查依赖是否安装
python -c "import PIL, piexif" >nul 2>&1
if errorlevel 1 (
    echo 📦 正在安装依赖包...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ 依赖安装失败，请检查网络连接
        pause
        exit /b 1
    )
)

echo ✅ 环境检查完成
echo.

REM 确保默认目录存在
REM 获取用户输入
set /p input_dir="请输入图片目录路径 (直接回车使用当前目录 .): "
if "%input_dir%"=="" set input_dir=.

echo.
echo 可选设置 (直接回车使用默认值):
set /p font_size="字体大小 (默认24): "
if "%font_size%"=="" set font_size=24

set /p color="水印颜色 (默认white): "
if "%color%"=="" set color=white

echo 位置选项: top-left, top-right, bottom-left, bottom-right, center
set /p position="水印位置 (默认bottom-right): "
if "%position%"=="" set position=bottom-right

echo.
echo 🚀 开始处理...
echo.

REM 运行程序
python photo_watermark.py "%input_dir%" --font-size %font_size% --color %color% --position %position%

echo.
echo 按任意键退出...
pause >nul
