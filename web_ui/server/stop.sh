#!/bin/bash
# 停止 Web UI 服务器和工具服务器

# 设置 UTF-8 编码（兼容 macOS）
export LANG=${LANG:-en_US.UTF-8}
export LC_ALL=${LC_ALL:-en_US.UTF-8}

# 默认端口
WEB_PORT=${PORT:-22228}

printf "🛑 正在停止服务器...\n"

# 停止 Web UI 服务器
WEB_PIDS=$(lsof -ti:$WEB_PORT 2>/dev/null)
if [ -z "$WEB_PIDS" ]; then
    printf "   ℹ️  Web UI 服务器未运行（端口 %s）\n" "$WEB_PORT"
else
    printf "   🛑 停止 Web UI 服务器（端口 %s）...\n" "$WEB_PORT"
    for PID in $WEB_PIDS; do
        kill -9 $PID 2>/dev/null
        if [ $? -eq 0 ]; then
            printf "      ✅ 已终止进程 %s\n" "$PID"
        else
            printf "      ⚠️  无法终止进程 %s\n" "$PID"
        fi
    done
fi

# 停止工具服务器（使用新的 mla-tool-server 命令）
printf "   🛑 停止工具服务器...\n"
if command -v mla-tool-server &> /dev/null; then
    if mla-tool-server stop; then
        printf "      ✅ 工具服务器已停止\n"
    else
        printf "      ℹ️  工具服务器未运行或已停止\n"
    fi
else
    printf "      ⚠️  未找到 mla-tool-server 命令，跳过工具服务器停止\n"
fi

# 等待一下，然后检查
sleep 1

REMAINING_WEB=$(lsof -ti:$WEB_PORT 2>/dev/null)

if [ -z "$REMAINING_WEB" ]; then
    printf "✅ 所有服务器已成功停止\n"
else
    printf "⚠️  Web UI 服务器仍在运行: %s\n" "$REMAINING_WEB"
fi

