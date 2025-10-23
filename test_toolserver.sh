#!/bin/bash
# Tool Server API 测试脚本

SERVER="http://localhost:8001"
TASK_ID="/tmp/mla_test_$(date +%s)"

echo "=== Tool Server API 测试 ==="
echo "任务目录: $TASK_ID"
mkdir -p "$TASK_ID"

# 测试函数
test_api() {
    local name=$1
    local data=$2
    echo -n "测试 $name... "
    response=$(curl -s -X POST "$SERVER/api/tool/execute" \
        -H "Content-Type: application/json" \
        -d "$data")
    if echo "$response" | grep -q '"success":true'; then
        echo "✅"
    else
        echo "❌"
        echo "$response" | head -c 200
    fi
}

# 1. 文件写入
test_api "file_write" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"file_write\",\"params\":{\"path\":\"test.txt\",\"content\":\"Hello World\"}}"

# 2. 文件读取
test_api "file_read" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"file_read\",\"params\":{\"path\":\"test.txt\"}}"

# 3. 目录列表
test_api "dir_list" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"dir_list\",\"params\":{\"path\":\".\"}}"

# 4. 创建目录
test_api "dir_create" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"dir_create\",\"params\":{\"path\":\"testdir\"}}"

# 5. 文件移动
test_api "file_move" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"file_move\",\"params\":{\"source\":\"test.txt\",\"destination\":\"testdir/test.txt\"}}"

# 6. 执行 Python 代码
test_api "execute_code" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"execute_code\",\"params\":{\"language\":\"python\",\"code\":\"print('Hello from Python')\"}}"

# 7. 执行 Bash
if [[ "$OSTYPE" != "msys" && "$OSTYPE" != "win32" ]]; then
    test_api "execute_bash" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"execute_code\",\"params\":{\"language\":\"bash\",\"code\":\"echo 'Hello from Bash'\"}}"
fi

# 8. 执行命令
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    test_api "execute_command" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"execute_command\",\"params\":{\"command\":\"dir\"}}"
else
    test_api "execute_command" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"execute_command\",\"params\":{\"command\":\"ls -la\"}}"
fi

# 9. Web 搜索
test_api "web_search" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"web_search\",\"params\":{\"query\":\"Python\",\"max_results\":3,\"save_path\":\"search.md\"}}"

# 10. arXiv 搜索
test_api "arxiv_search" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"arxiv_search\",\"params\":{\"query\":\"neural network\",\"max_results\":2,\"save_path\":\"arxiv.md\"}}"

# 11. Google Scholar 搜索
test_api "google_scholar_search" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"google_scholar_search\",\"params\":{\"query\":\"machine learning\",\"pages\":1,\"save_path\":\"scholar.md\"}}"

# 12. 网页爬取
test_api "crawl_page" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"crawl_page\",\"params\":{\"url\":\"https://example.com\",\"save_path\":\"page.md\"}}"

# 13. 文件下载
test_api "file_download" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"file_download\",\"params\":{\"url\":\"https://www.python.org/static/favicon.ico\",\"save_path\":\"favicon.ico\"}}"

# 14. pip 安装
test_api "pip_install" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"pip_install\",\"params\":{\"packages\":[\"requests\"]}}"

# 15. Markdown 写入（用于文档转换测试）
test_api "write_md" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"file_write\",\"params\":{\"path\":\"test.md\",\"content\":\"# Test\\n\\nHello **World**\"}}"

# 16. 复制测试 PDF 文件
cp "$(pwd)/test.pdf" "$TASK_ID/test.pdf" 2>/dev/null || echo "  (跳过 - test.pdf 不存在)"

# 17. 解析 PDF 文档
test_api "parse_document" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"parse_document\",\"params\":{\"path\":\"test.pdf\",\"save_path\":\"parsed.txt\"}}"

# 17. Markdown 转 PDF（需要文档转换 API）
# test_api "md_to_pdf" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"md_to_pdf\",\"params\":{\"source_path\":\"test.md\"}}"

# 18. Markdown 转 DOCX（需要文档转换 API）
# test_api "md_to_docx" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"md_to_docx\",\"params\":{\"source_path\":\"test.md\"}}"

# 19. 文件删除
test_api "file_delete" "{\"task_id\":\"$TASK_ID\",\"tool_name\":\"file_delete\",\"params\":{\"path\":\"testdir\"}}"

echo ""
echo "测试完成，清理: rm -rf $TASK_ID"
rm -rf "$TASK_ID"

