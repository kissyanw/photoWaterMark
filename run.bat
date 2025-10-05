@echo off
chcp 65001 >nul
title 图片水印工具 (GUI)

echo.
echo ========================================
echo           图片水印工具 (GUI)
echo ========================================
echo.

REM 选择Python解释器: 优先 py，其次 python
set PYEXE=
py -V >nul 2>&1 && set PYEXE=py
if "%PYEXE%"=="" (
    python --version >nul 2>&1 && set PYEXE=python
)
if "%PYEXE%"=="" (
    echo ❌ 错误: 未找到Python，请先安装Python 3.6+
    echo    - 若已安装 Python Launcher，请确保可运行: py -V
    echo    - 或将 python.exe 添加到 PATH 后重开终端
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查依赖是否安装
%PYEXE% -c "import PIL, piexif" >nul 2>&1
if errorlevel 1 (
    echo 📦 正在安装依赖包...
    %PYEXE% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ 依赖安装失败，请检查网络连接
        pause
        exit /b 1
    )
)

echo ✅ 环境检查完成
echo.

echo 启动图形界面...
%PYEXE% -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Tkinter，请安装带Tk的Python版本
    pause
    exit /b 1
)

REM 拖拽依赖(可选)
%PYEXE% -c "import tkinterdnd2" >nul 2>&1
if errorlevel 1 (
    echo ⚠️ 未安装 tkinterdnd2，将无法使用拖拽，但不影响功能
)

%PYEXE% gui.py

echo.
echo 按任意键退出...
pause >nul
