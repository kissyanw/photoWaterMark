@echo off
chcp 65001 >nul
title 图片水印工具

echo.
echo ========================================
echo           图片水印工具 (GUI)
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

echo 启动图形界面...
python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Tkinter，请安装带Tk的Python版本
    pause
    exit /b 1
)

REM 拖拽依赖(可选)
python -c "import tkinterdnd2" >nul 2>&1
if errorlevel 1 (
    echo ⚠️ 未安装 tkinterdnd2，将无法使用拖拽，但不影响功能
)

python gui.py

echo.
echo 按任意键退出...
pause >nul
