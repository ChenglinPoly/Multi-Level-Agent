@echo off
REM Tool Server API 测试脚本 (Windows)

set SERVER=http://localhost:8001
set TASK_ID=%TEMP%\mla_test_%RANDOM%

echo === Tool Server API 测试 ===
echo 任务目录: %TASK_ID%
mkdir "%TASK_ID%" 2>nul

REM 测试文件写入
echo 测试 file_write...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"file_write\",\"params\":{\"path\":\"test.txt\",\"content\":\"Hello World\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试文件读取
echo 测试 file_read...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"file_read\",\"params\":{\"path\":\"test.txt\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试目录列表
echo 测试 dir_list...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"dir_list\",\"params\":{\"path\":\".\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试创建目录
echo 测试 dir_create...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"dir_create\",\"params\":{\"path\":\"testdir\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试文件移动
echo 测试 file_move...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"file_move\",\"params\":{\"source\":\"test.txt\",\"destination\":\"testdir/test.txt\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试 Python 代码执行
echo 测试 execute_code (Python)...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"execute_code\",\"params\":{\"language\":\"python\",\"code\":\"print('Hello from Python')\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试执行命令
echo 测试 execute_command...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"execute_command\",\"params\":{\"command\":\"dir\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试 Web 搜索
echo 测试 web_search...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"web_search\",\"params\":{\"query\":\"Python\",\"max_results\":3,\"save_path\":\"search.md\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试 arXiv 搜索
echo 测试 arxiv_search...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"arxiv_search\",\"params\":{\"query\":\"neural network\",\"max_results\":2,\"save_path\":\"arxiv.md\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试 Google Scholar 搜索
echo 测试 google_scholar_search...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"google_scholar_search\",\"params\":{\"query\":\"machine learning\",\"pages\":1,\"save_path\":\"scholar.md\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试网页爬取
echo 测试 crawl_page...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"crawl_page\",\"params\":{\"url\":\"https://example.com\",\"save_path\":\"page.md\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试文件下载
echo 测试 file_download...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"file_download\",\"params\":{\"url\":\"https://www.python.org/static/favicon.ico\",\"save_path\":\"favicon.ico\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试 pip 安装
echo 测试 pip_install...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"pip_install\",\"params\":{\"packages\":[\"requests\"]}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 复制测试 PDF 文件
if exist test.pdf copy test.pdf "%TASK_ID%\test.pdf" >nul 2>&1

REM 测试解析 PDF 文档
echo 测试 parse_document...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"parse_document\",\"params\":{\"path\":\"test.pdf\",\"save_path\":\"parsed.txt\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

REM 测试文件删除
echo 测试 file_delete...
curl -s -X POST "%SERVER%/api/tool/execute" -H "Content-Type: application/json" -d "{\"task_id\":\"%TASK_ID:\=/%\",\"tool_name\":\"file_delete\",\"params\":{\"path\":\"testdir\"}}" | findstr /C:"success" >nul && echo 成功 || echo 失败

echo.
echo 测试完成，清理: rmdir /s /q "%TASK_ID%"
rmdir /s /q "%TASK_ID%" 2>nul

pause

