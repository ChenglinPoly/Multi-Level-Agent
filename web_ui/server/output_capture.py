#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Output Capture Tool

Captures output during agent execution process.

Author: Songmiao Wang
MLA System: Chenlin Yu, Songmiao Wang"""

import sys
import json
import re
from typing import Optional, Callable
from io import StringIO
from datetime import datetime


class OutputCapture:
    """Output capture class - captures stdout/stderr and EventEmitter events"""
    
    def __init__(self, callback: Callable[[dict], None], agent_name: str = "unknown"):
        """
        Args:
            callback: Callback function called when there is output, receives a dict with type, agent, content, timestamp
            agent_name: Currently executing agent name
        """
        self.callback = callback
        self.agent_name = agent_name
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.buffer = StringIO()
        self.current_agent = agent_name
        
        # Output buffer - for merging similar messages
        self.output_buffer = []
        self.last_output_time = 0
        self.buffer_timeout = 0.5  # Output buffer content after 0.5 seconds
        
        # Maintain most recent calling agent name (for parameter lines and JSON content)
        self.last_call_agent = None
        
        # Call buffer: stores tool/agent call message, waiting for parameters
        self.call_buffer = None
        
        # Parameter buffer (for merging "Parameters:" and parameter content)
        self.params_buffer = None
        
        # Final output buffer (for merging final_output call and result)
        self.final_output_buffer = None
        self.is_final_output_call = False  # Track if current call is final_output
        
        # Only keep these important message patterns (Agent calls, tool calls, parameters)
        # Format unified as:
        # - Tool call: 🔧 [agent_name] calls tool: tool_name
        # - Agent call: 📚 [caller_name] calls sub-agent: agent_name
        # - Parameters: 📋 Parameters: + JSON
        self.important_patterns = [
            re.compile(r'📚.*\[.*\].*calls sub-agent'),  # Agent call (only keep those with caller)
            re.compile(r'🔧.*\[.*\].*calls tool'),  # Tool call (unified format, no longer use "Execute tool")
            re.compile(r'📋.*Parameters'),  # Parameter info (parameter title)
        ]
        
        # Noise messages to filter (all other output)
        self.noise_patterns = [
            # Server related
            re.compile(r'检查/创建任务时出错'),
            re.compile(r'HTTPConnectionPool'),
            re.compile(r'Connection refused'),
            re.compile(r'Max retries exceeded'),
            re.compile(r'Restarting with stat'),
            re.compile(r'Debugger is active'),
            re.compile(r'Running on'),
            re.compile(r'Serving Flask app'),
            # Agent startup and task info
            re.compile(r'🤖\s+启动Agent'),
            re.compile(r'📝\s+任务:'),
            re.compile(r'📂\s+已加载对话历史'),
            re.compile(r'🔄\s+发现.*pending工具'),
            re.compile(r'---\s+第\s+\d+.*轮执行'),
            re.compile(r'⚠️\s+达到最大轮次限制'),
            re.compile(r'✅\s+任务已完成，直接返回'),
            # Initialization info
            re.compile(r'🚀\s+启动任务'),
            re.compile(r'📦\s+加载配置'),
            re.compile(r'✅\s+配置加载成功'),
            re.compile(r'📊\s+初始化层级管理器'),
            re.compile(r'✅\s+层级管理器初始化成功'),
            re.compile(r'🧹\s+检查并清理状态'),
            re.compile(r'✅\s+指令已注册'),
            re.compile(r'🔍\s+查找Agent配置'),
            re.compile(r'✅\s+Agent配置加载成功'),
            re.compile(r'▶️\s+开始执行任务'),
            # Agent push (not displayed, only show call relationship)
            re.compile(r'📚\s+Agent入栈:'),
            re.compile(r'📚\s+Agent出栈'),
            # Other completion info
            re.compile(r'✅\s+使用.*模型'),
            re.compile(r'✅\s+Agent配置'),
            re.compile(r'✅\s+工具执行器初始化'),
            re.compile(r'✅\s+任务.*已在toolServer中创建'),
            re.compile(r'✅\s+.*测试'),
            re.compile(r'✅\s+.*工具.*执行完成'),  # Tool execution completion also not displayed
            re.compile(r'工具\s+\w+\s+完成'),  # Tool xxx completed
            re.compile(r'工具.*完成:'),  # Tool xxx completed: success
            re.compile(r'"type":\s*"token".*工具.*完成'),  # Tool completion info in JSONL events
            # Warnings and errors
            re.compile(r'⚠️\s+.*'),
            re.compile(r'❌\s+执行出错'),
            re.compile(r'❌\s+恢复失败'),
            # Other info
            re.compile(r'📄\s+输出预览'),
            re.compile(r'🔗\s+.*调用toolServer'),
            re.compile(r'🎉\s+所有Agent已完成'),
            re.compile(r'✅\s+任务已归档'),
            re.compile(r'📝\s+新指令已添加'),
            re.compile(r'ℹ️\s+指令已存在'),
            re.compile(r'⚠️\s+加载.*失败'),
            re.compile(r'⚠️\s+保存.*失败'),
            re.compile(r'⚠️\s+.*配置失败'),
            re.compile(r'⚠️\s+创建任务失败'),
            re.compile(r'⚠️\s+Thinking触发失败'),
            re.compile(r'⚠️\s+压缩失败'),
            # Separator lines
            re.compile(r'^={80,}$'),
            re.compile(r'^-{3,}.*-{3,}$'),
        ]
        
        # Agent name pattern matching
        self.agent_patterns = [
            re.compile(r'\[([^\]]+)\]\s+calls'),  # [agent_name] calls...
            re.compile(r'\[([^\]]+)\]'),  # [agent_name]
            re.compile(r'🤖\s+Start Agent:\s+(\w+)'),  # 🤖 Start Agent: agent_name
            re.compile(r'Agent completed:\s+(\w+)'),  # Agent completed: agent_name
            re.compile(r'calls sub-agent:\s+(\w+)'),  # Call sub-agent: agent_name
            re.compile(r'calls tool:\s+(\w+)'),  # Call tool: tool_name
        ]
    
    def start(self):
        """开始捕获输出"""
        sys.stdout = self
        sys.stderr = self
    
    def stop(self):
        """停止捕获输出"""
        # Output remaining buffered content
        self._flush_buffer()
        # Output remaining call with parameters or final output (if any)
        if self.call_buffer:
            if self.final_output_buffer:
                self._output_final_output_with_result()
            elif self.params_buffer:
                self._output_call_with_params()
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
    
    def write(self, text: str):
        """写入输出（重定向 stdout/stderr）"""
        # 写入原始 stdout（用于调试）
        self.original_stdout.write(text)
        self.original_stdout.flush()
        
        # 如果是 final_output 调用，先处理结果收集（在所有过滤之前）
        # 现在只输出 output 字段的内容（纯文本），不再是 JSON
        if self.is_final_output_call and self.call_buffer:
            text_stripped = text.strip()
            
            # 跳过参数行（对于 final_output，不显示参数）
            if '📋' in text and 'Parameters' in text:
                return  # 忽略参数标题行
            
            # 跳过参数内容（参数是 JSON 格式）
            # 如果还没有开始收集结果，且看起来是 JSON 格式，可能是参数，忽略
            # 现在参数已经在 agent_executor.py 中被跳过了，但为了安全起见还是检查一下
            if not self.final_output_buffer:
                # 检查是否是 JSON 格式的参数内容
                looks_like_json = (text_stripped.startswith('{') or text_stripped.startswith('[') or 
                                  (text_stripped.startswith('"') and ':' in text))
                if looks_like_json:
                    # 检查是否是参数：如果包含参数字段
                    has_param_fields = any(field in text for field in ['"task_id"', '"task_input"', '"arguments"', '"status"', '"output"'])
                    # 如果看起来像完整的 JSON 对象（包含多个字段），可能是参数或工具完成信息，忽略
                    if has_param_fields or ('"' in text and text.count(':') > 1):
                        return
            
            # Check if tool completion info (need to output final output and filter this message)
            is_tool_complete = 'tool' in text.lower() and 'completed' in text.lower()
            
            if is_tool_complete:
                # Output call message with final output together
                if self.final_output_buffer:
                    self._output_final_output_with_result()
                # 过滤掉工具完成信息
                return
            
            # 检查是否是结果内容
            # 对于 final_output，现在只输出 output 字段的内容（纯文本），不再是 JSON
            # 排除 JSON 格式的内容（可能是参数或工具完成信息）
            # 只接受纯文本内容（不包含 JSON 特征）
            is_result_content = (
                text_stripped and 
                not any(x in text for x in ['🔧', '📋', '📚', 'calls tool', 'calls sub-agent', 'completed']) and
                # 排除参数行
                'Parameters' not in text and
                # 排除 JSON 格式（不应该是 JSON）
                not text_stripped.startswith('{') and
                not text_stripped.startswith('[') and
                not (text_stripped.startswith('"') and ':' in text) and
                # 排除包含多个 JSON 字段的行（如 "task_id": "xxx"）
                not ('"' in text and text.count(':') >= 1 and any(field in text for field in ['"task_id"', '"status"', '"output"', '"execution_experience"', '"sub_tools"']))
            )
            
            if is_result_content:
                # 初始化或更新 final_output_buffer
                if not self.final_output_buffer:
                    agent = self.call_buffer.get("agent") or self.current_agent
                    self.final_output_buffer = {
                        "type": "final_output",
                        "agent": agent,
                        "content": text_stripped,
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    # 追加内容（可能是多行文本）
                    self.final_output_buffer["content"] = self.final_output_buffer["content"] + "\n" + text_stripped
                # 继续等待更多结果内容（可能是多行文本）
                return
            elif text_stripped:
                # 遇到非结果内容，可能是新的工具调用等
                # 先输出已收集的结果
                if self.final_output_buffer:
                    self._output_final_output_with_result()
                # 继续处理当前行（不要 return，让它继续处理）
            # 空行也作为结果的一部分（可能是多行文本）
            elif not text_stripped:
                # 如果已经有内容，空行可能是文本的分隔，继续等待
                if self.final_output_buffer:
                    return
        
        if not text.strip():
            return
        
        # 先过滤噪音消息（所有不需要的输出）
        if self._is_noise(text):
            return
        
        # 如果参数缓冲存在，检查是否是参数内容（即使不是重要消息，也要处理）
        if self.params_buffer:
            # 如果是 final_output 工具，忽略参数，清空 params_buffer
            if self.is_final_output_call:
                self.params_buffer = None
            else:
                text_stripped = text.strip()
            
            # Check if tool completion info (need to output parameters and filter this message)
            is_tool_complete = 'tool' in text.lower() and 'completed' in text.lower()
            
            if is_tool_complete:
                # Output call message with parameters together
                self._output_call_with_params()
                # 过滤掉工具完成信息
                return
            
            # 空行也作为参数的一部分（可能是多行JSON）
            if not text_stripped:
                # 空行，继续等待参数内容
                return
            
            # 检查是否是参数内容（JSON格式）
            is_json_content = (
                text_stripped.startswith('{') or 
                text_stripped.startswith('[') or
                (text_stripped.startswith('"') and ':' in text) or  # JSON字段
                (text_stripped and not any(x in text for x in ['🔧', '📋', '📚', 'calls tool', 'calls sub-agent', 'completed']))
            )
            
            if is_json_content:
                # 合并参数标题和内容
                if self.params_buffer["content"].endswith('Parameters:'):
                    self.params_buffer["content"] = self.params_buffer["content"] + "\n" + text_stripped
                else:
                    self.params_buffer["content"] = self.params_buffer["content"] + "\n" + text_stripped
                # 继续等待更多参数内容（可能是多行JSON）
                return
            else:
                # Check if new important message (tool call, Agent call, etc.)
                is_new_important = (
                    '🔧' in text and 'calls tool' in text or
                    '📚' in text and 'calls sub-agent' in text
                )
                
                if is_new_important:
                        # Encounter new important message, output call with parameters together
                        self._output_call_with_params()
                    # 继续处理当前行
                else:
                        # Other cases, output call with parameters together
                        self._output_call_with_params()
                    # 继续处理当前行
        
        # 只处理重要消息（Agent调用、工具调用、参数）
        if not self._is_important(text):
            return
        
        # Determine message type
        msg_type = self._determine_message_type(text)
        
        # Handle tool call or agent call - save to call_buffer instead of immediate output
        if msg_type in ["tool_call", "agent_call"]:
            # If there's a previous call_buffer with parameters, output it first
            if self.call_buffer:
                if self.params_buffer:
                    self._output_call_with_params()
                elif self.final_output_buffer:
                    self._output_final_output_with_result()
            
            # Save current call to call_buffer
            agent = self._extract_agent_name(text)
            if not agent:
                # 如果提取失败，尝试从文本中提取
                if msg_type == "agent_call":
                    match = re.search(r'\[([^\]]+)\]\s+calls sub-agent', text)
                    if match:
                        agent = match.group(1)
                elif msg_type == "tool_call":
                    match = re.search(r'\[([^\]]+)\]\s+calls tool', text)
                    if match:
                        agent = match.group(1)
            
            if agent:
                self.last_call_agent = agent
            
            if not agent:
                agent = self.last_call_agent or self.current_agent
            
            # Check if this is final_output tool call
            self.is_final_output_call = False
            if msg_type == "tool_call":
                # Extract tool name from text
                match = re.search(r'calls tool:\s*(\w+)', text)
                if match and match.group(1) == "final_output":
                    self.is_final_output_call = True
            
            self.call_buffer = {
                "type": msg_type,
                "agent": agent,
                "content": text.strip(),
                "timestamp": datetime.now().isoformat()
            }
            # Clear params_buffer and final_output_buffer to prepare for new content
            self.params_buffer = None
            self.final_output_buffer = None
            return  # 不立即输出，等待参数或结果
        
        # Handle parameter title line ("📋 Parameters:")
        if msg_type == "params" and '📋' in text and 'Parameters' in text:
            # 如果是 final_output 工具，跳过参数处理，只等待最终输出
            if self.is_final_output_call:
                # 对于 final_output，忽略参数，不保存到 params_buffer
                return
            
            # 保存参数标题到缓冲，等待参数内容
            agent = self._extract_agent_name(text) or self.last_call_agent or self.current_agent
            self.params_buffer = {
                "type": "params",
                "agent": agent,
                "content": text.strip(),
                "timestamp": datetime.now().isoformat()
            }
            return  # 不立即输出，等待参数内容
        
        # 如果不是参数内容，且不是工具/Agent调用，清空缓冲并输出
        if self.call_buffer and self.params_buffer:
            self._output_call_with_params()
        
        # 其他类型的消息正常处理
        if msg_type not in ["tool_call", "agent_call", "params"]:
        # 尝试从输出中提取 agent 名称
            agent = self._extract_agent_name(text) or self.last_call_agent or self.current_agent
        
        # 如果还是没有 agent，使用当前 agent
        if not agent:
            agent = self.current_agent
        
        # 检查内容是否为空
        content = text.strip()
        if not content:
            return  # 不输出空消息
        
        # 去重：检查是否与最近输出的消息相同（避免重复）
        if hasattr(self, '_last_output'):
            if self._last_output == content and msg_type == self._last_output_type:
                return  # 跳过重复消息
        
        # 保存最近输出的消息
        self._last_output = content
        self._last_output_type = msg_type
        
            # 立即输出其他类型消息
        self.callback({
            "type": msg_type,
            "agent": agent,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        return
    
    def _is_important(self, text: str) -> bool:
        """判断是否是重要消息（只保留Agent调用、工具调用、参数）"""
        text_stripped = text.strip()
        
        # 空消息不算重要
        if not text_stripped:
            return False
        
        # Check if important message（Agent调用、工具调用、参数）
        # 只匹配带调用者信息的消息（避免重复）
        for pattern in self.important_patterns:
            if pattern.search(text):
                # Ensure message contains caller information (avoid duplicates)
                if 'calls sub-agent' in text and '[' not in text:
                    return False  # Agent call without caller info not displayed
                if 'calls tool' in text and '[' not in text:
                    return False  # Tool call without caller info not displayed
                return True
        
        # 检查是否是参数的 JSON 内容（多行）
        # 如果当前行是 JSON（以 { 或 [ 开头，且包含常见字段）
        if text_stripped.startswith('{') or text_stripped.startswith('['):
            # 检查是否包含常见字段（参数或结果）
            if any(field in text for field in ['"task_input"', '"path"', '"content"', '"arguments"', '"task_id"', '"status"', '"output"']):
                # 只有在有参数缓冲时才显示（避免单独显示 JSON）
                if self.params_buffer:
                    return True
                return False  # 没有参数缓冲的 JSON 不单独显示
        
        # 检查是否是参数内容的后续行（不以 { 开头，但包含 JSON 字段）
        if self.params_buffer and not text_stripped.startswith('{') and not text_stripped.startswith('['):
            # 可能是多行 JSON 的一部分
            if any(x in text for x in ['"', ':', ',', '}', ']']) and not any(x in text for x in ['🔧', '📋', '📚', 'calls tool', 'calls sub-agent']):
                return True  # 作为参数内容处理
        
        return False
    
    def _is_noise(self, text: str) -> bool:
        """判断是否是噪音消息（过滤所有其他输出）"""
        # 先检查是否是重要消息，如果是就不算噪音
        if self._is_important(text):
            return False
        # 其他都是噪音
        return True
    
    def _flush_buffer(self):
        """输出缓冲的内容"""
        if not self.output_buffer:
            return
        
        # 合并缓冲中的消息
        if len(self.output_buffer) == 1:
            msg = self.output_buffer[0]
        else:
            # 合并多条消息
            contents = [m["content"] for m in self.output_buffer]
            msg = {
                "type": self.output_buffer[0]["type"],
                "agent": self.output_buffer[0]["agent"],
                "content": "\n".join(contents)
            }
        
        self.callback({
            "type": msg["type"],
            "agent": msg["agent"],
            "content": msg["content"],
            "timestamp": datetime.now().isoformat()
        })
        
        self.output_buffer.clear()
    
    def _output_call_with_params(self):
        """输出工具调用/Agent调用和参数合并的消息"""
        if not self.call_buffer:
            # 如果没有调用信息，只输出参数
            if self.params_buffer and self.params_buffer["content"].strip() and self.params_buffer["content"] != "📋 Parameters:":
                self.callback(self.params_buffer)
                self.params_buffer = None
            return
        
        # 合并调用信息和参数
        call_content = self.call_buffer["content"]
        
        if self.params_buffer and self.params_buffer["content"].strip() and self.params_buffer["content"] != "📋 Parameters:":
            # 提取参数内容（去掉 "📋 Parameters:" 前缀）
            params_content = self.params_buffer["content"]
            if params_content.startswith("📋 Parameters:"):
                params_content = params_content.replace("📋 Parameters:", "").strip()
            
            # 合并到调用消息中
            combined_content = f"{call_content}\n\n📋 Parameters:\n{params_content}"
        else:
            combined_content = call_content
        
        # 输出合并后的消息
        self.callback({
            "type": self.call_buffer["type"],
            "agent": self.call_buffer["agent"],
            "content": combined_content,
            "timestamp": self.call_buffer["timestamp"]
        })
        
        # 清空缓冲
        self.call_buffer = None
        self.params_buffer = None
    
    def _output_final_output_with_result(self):
        """输出 final_output 工具调用和完整结果合并的消息"""
        if not self.call_buffer:
            # 如果没有调用信息，只输出结果
            if self.final_output_buffer and self.final_output_buffer["content"].strip():
                self.callback(self.final_output_buffer)
                self.final_output_buffer = None
            return
        
        # 合并调用信息和完整结果
        call_content = self.call_buffer["content"].strip()
        
        if self.final_output_buffer and self.final_output_buffer["content"].strip():
            # 获取结果内容
            result_content = self.final_output_buffer["content"].strip()
            
            # 合并到调用消息中（只显示调用信息和完整输出，不显示参数）
            # 确保调用信息和结果之间有明确的换行
            combined_content = f"{call_content}\n\n{result_content}"
        else:
            # 没有结果，只显示调用信息
            combined_content = call_content
        
        # 输出合并后的消息（使用 final_output 类型）
        self.callback({
            "type": "final_output",
            "agent": self.call_buffer["agent"],
            "content": combined_content,
            "timestamp": self.call_buffer["timestamp"]
        })
        
        # 清空缓冲
        self.call_buffer = None
        self.final_output_buffer = None
        self.is_final_output_call = False
    
    def flush(self):
        """刷新缓冲区"""
        self.original_stdout.flush()
    
    def _extract_agent_name(self, text: str) -> Optional[str]:
        """从文本中提取 agent 名称"""
        for pattern in self.agent_patterns:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None
    
    def _determine_message_type(self, text: str) -> str:
        """确定消息类型"""
        text_stripped = text.strip()
        
        # 空消息直接返回
        if not text_stripped:
            return "info"
        
        # Agent call (check if contains caller information)
        # Format: 📚 [caller_name] calls sub-agent: agent_name
        if '📚' in text and 'calls sub-agent' in text and '[' in text:
            return "agent_call"
        # Tool call (unified format)
        # Format: 🔧 [agent_name] calls tool: tool_name
        elif '🔧' in text and 'calls tool' in text and '[' in text:
            return "tool_call"
        # Parameter info
        # Format: 📋 Parameters:
        elif '📋' in text and 'Parameters' in text:
            return "params"
        else:
            return "info"
    
    def set_agent(self, agent_name: str):
        """设置当前 agent 名称"""
        self.current_agent = agent_name
        self.agent_name = agent_name
    
    def parse_jsonl_event(self, line: str):
        """解析 EventEmitter 的 JSONL 事件"""
        try:
            event = json.loads(line.strip())
            event_type = event.get('type', 'unknown')
            
            # 提取 agent 信息
            agent = self.current_agent
            if 'agent' in event:
                agent = event['agent']
            
            # 格式化内容
            content = ""
            if event_type == 'token':
                # token 类型：检查内容是否需要过滤
                text = event.get('text', '')
                
                # Filter tool completion info
                if 'tool' in text.lower() and 'completed' in text.lower():
                    return  # Do not process tool completion info
                
                content = text
                
                # 如果内容为空，不输出
                if not content.strip():
                    return
                    
            elif event_type == 'start':
                content = f"🚀 Task started: {event.get('task', '')}"
                agent = event.get('agent', agent)
            elif event_type == 'result':
                content = f"📊 Execution result: {event.get('summary', '')}"
            elif event_type == 'end':
                status = event.get('status', 'unknown')
                duration = event.get('duration_ms', 0) / 1000
                content = f"{'✅' if status == 'ok' else '❌'} Task completed ({duration:.1f}s)"
            elif event_type == 'error':
                content = f"❌ Error: {event.get('text', '')}"
            elif event_type == 'warn':
                content = f"⚠️ Warning: {event.get('text', '')}"
            elif event_type == 'notice':
                content = f"ℹ️ Notice: {event.get('text', '')}"
            elif event_type == 'progress':
                # progress 类型：不输出（避免显示进度条）
                return
            else:
                content = json.dumps(event, ensure_ascii=False)
            
            # 如果内容为空，不输出
            if not content or not content.strip():
                return
            
            # Send message（使用原始事件类型）
            self.callback({
                "type": event_type,
                "agent": agent,
                "content": content.strip(),
                "timestamp": datetime.now().isoformat()
            })
        except json.JSONDecodeError:
            # 不是 JSON，忽略
            pass

