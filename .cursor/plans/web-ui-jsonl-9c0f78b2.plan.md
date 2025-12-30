<!-- 9c0f78b2-e33d-4c98-98b1-6c1341f2346a befc9b98-a7d8-4eb3-aeb4-872476846ea0 -->
# Web UI 前后端通信改进计划

## 目标

将 `web_ui/server/server.py` 中的事件处理从文本解析改为直接解析 JSONL 事件流，移除对 `OutputCapture` 的依赖，提高系统稳定性和可维护性。

## 当前架构问题

- 使用 `OutputCapture` 类通过正则表达式解析终端输出文本
- 依赖固定的文本格式（如 "🔧 [agent] calls tool"），格式变化会导致解析失败
- 代码复杂，维护成本高（653 行文本解析逻辑）

## 改进方案

利用系统已有的 JSONL 事件流（`--jsonl` 模式），直接解析 JSON 事件，无需文本解析。

## 数据流对比

### 当前数据流

```
start.py (--jsonl)
  → stdout: JSONL 事件
  → stderr: print() 输出
  ↓
subprocess.stdout (合并)
  ↓
OutputCapture.write(line)
  → 正则解析文本
  → 提取信息
  → 转换为前端格式
  ↓
output_queue
  ↓
SSE 流
  ↓
前端
```

### 改进后数据流

```
start.py (--jsonl)
  → stdout: JSONL 事件
  → stderr: print() 输出
  ↓
subprocess.stdout (合并)
  ↓
直接解析 JSONL
  → json.loads(line)
  → 映射到前端格式
  ↓
output_queue
  ↓
SSE 流
  ↓
前端
```

## 实施步骤

### 步骤 1: 修改 `read_process_output()` 函数

**文件**: `web_ui/server/server.py`

**位置**: 第 528-597 行

**改动内容**:

- 移除 `OutputCapture` 的使用
- 实现直接 JSONL 解析逻辑
- 保持错误处理和任务停止逻辑
- 实现事件类型映射（JSONL 事件 → 前端消息格式）

**关键逻辑**:

1. 发送开始消息到 `output_queue`
2. 逐行读取 `process.stdout`
3. 尝试 `json.loads()` 解析每一行
4. 根据事件类型（`start`, `token`, `tool_call`, `error`, `end` 等）映射为前端格式
5. 非 JSON 行作为错误处理（仅显示明显的错误信息）
6. 任务结束时发送结束消息

### 步骤 2: 移除 OutputCapture 导入

**文件**: `web_ui/server/server.py`

**位置**: 第 29-34 行

**改动内容**:

- 注释或移除 `from output_capture import OutputCapture` 导入
- 移除相关的导入说明注释

### 步骤 3: 添加必要的导入

**文件**: `web_ui/server/server.py`

**位置**: 文件顶部

**改动内容**:

- 确保 `json` 已导入（通常已存在）
- 确保 `datetime` 已导入（用于时间戳）

### 步骤 4: 移除调试输出（可选）

**文件**: `web_ui/server/server.py`

**位置**: `read_process_output()` 函数内部

**改动内容**:

- 移除或注释掉 `sys.stdout.write(line)` 调试输出（第 554-556 行）

## 事件映射规则

| JSONL 事件类型 | 前端消息类型 | 内容处理 |

|---------------|------------|---------|

| `start` | `start` | `"🚀 任务开始: {task}"` |

| `token` (工具调用文本) | `tool_call` | 解析文本提取工具名和参数，格式化为前端格式 |

| `token` (普通文本) | `info` | 直接使用 `text` 字段 |

| `error` | `error` | `"❌ {text}"` |

| `warn` | `info` | `"⚠️ {text}"` |

| `notice` | `info` | `"ℹ️ {text}"` |

| `result` | `info` | `"✅/❌ 执行结果: {summary}"` |

| `end` | `end` | `"✅/❌ 任务完成 ({duration}秒)"` |

## 错误处理

1. **JSON 解析失败**: 

   - 捕获 `json.JSONDecodeError`
   - 检查是否是明显的错误信息（包含 "Error" 或 "Exception"）
   - 仅显示错误信息，忽略普通 print 输出

2. **进程异常终止**:

   - 检查 `process.returncode`
   - 根据退出码和 `stop_requested` 标志发送相应消息

3. **异常捕获**:

   - 外层 try-except 捕获所有异常
   - 发送错误消息到前端
   - 确保 `user_execution['running'] = False`

## 兼容性保证

- 前端接口不变：SSE 消息格式保持不变
- 事件格式向后兼容：支持现有的 `token` 事件文本格式
- 错误降级：JSON 解析失败时仍能处理错误信息

## 测试验证

1. **功能测试**:

   - 执行简单任务，验证消息正常显示
   - 执行包含工具调用的任务，验证工具调用信息显示
   - 执行包含子 Agent 调用的任务，验证调用关系显示
   - 验证任务完成状态正确显示

2. **错误测试**:

   - 验证错误信息能正确显示
   - 验证任务停止功能正常

3. **兼容性测试**:

   - 验证现有任务的聊天历史正常加载
   - 验证文件浏览器等其他功能不受影响

## 文件修改清单

1. `web_ui/server/server.py`

   - 修改 `read_process_output()` 函数（第 528-597 行）
   - 移除/注释 `OutputCapture` 导入（第 34 行）
   - 移除调试输出（第 554-556 行，可选）

## 风险与缓解

- **风险**: JSON 解析失败导致消息丢失
  - **缓解**: 捕获异常，错误信息单独处理
- **风险**: 事件格式不匹配
  - **缓解**: 向后兼容现有 token 事件格式，支持文本解析
- **风险**: 性能影响
  - **缓解**: JSON 解析比正则匹配更快，性能影响可忽略

## 后续优化（可选）

1. 扩展 `event_emitter.py` 添加结构化事件方法（`tool_call()`, `agent_call()` 等）
2. 在 `agent_executor.py` 中使用结构化事件替代文本格式的 token 事件
3. 完全移除 `output_capture.py` 文件（如果不再需要）

### To-dos

- [ ] 修改 read_process_output() 函数，实现直接 JSONL 解析逻辑，移除 OutputCapture 依赖
- [ ] 移除或注释 OutputCapture 的导入语句
- [ ] 完善错误处理逻辑，包括 JSON 解析失败、进程异常终止等情况
- [ ] 测试基本功能：简单任务执行、消息显示、任务完成状态
- [ ] 测试工具调用：验证工具调用信息、参数显示是否正确
- [ ] 测试错误情况：错误信息显示、任务停止功能