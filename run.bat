@echo off
:: 设置 CMD 编码为 UTF-8
chcp 65001 >nul

:: 切换到当前脚本所在目录
cd /d %~dp0

:: 检查 main.py 是否存在
if not exist "main.py" (
    echo [错误] 当前目录下找不到 main.py 文件。
    pause
    exit /b
)

:: 执行 Python 脚本
echo [信息] 开始运行 main.py 脚本...
python main.py

:: 检查执行结果
if %errorlevel% neq 0 (
    echo [错误] 脚本执行失败！
) else (
    echo [信息] 脚本执行完成！
)

pause