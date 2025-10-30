#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式 CLI 模式
"""

import os
import sys
from pathlib import Path
import subprocess
import threading
import queue
import signal
import platform

try:
    from prompt_toolkit import PromptSession, print_formatted_text
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.patch_stdout import patch_stdout
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.live import Live
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class InteractiveCLI:
    """交互式命令行界面"""
    
    def __init__(self, task_id: str, agent_system: str = "Test_agent"):
        self.task_id = task_id
        self.agent_system = agent_system
        self.current_agent = "writing_agent"
        self.current_process = None
        self.output_queue = queue.Queue()
        self.output_lines = []  # 保存最近的输出
        self.max_output_lines = 20  # 最多保留20行输出
        
        # Rich console
        self.console = Console() if RICH_AVAILABLE else None
        
        # 加载可用 agent 列表
        self.available_agents = self._load_available_agents()
    
    def _load_available_agents(self):
        """加载 Level 2/3 Agent 列表"""
        try:
            from utils.config_loader import ConfigLoader
            config_loader = ConfigLoader(self.agent_system)
            
            agents = []
            for name, config in config_loader.all_tools.items():
                if config.get("type") == "llm_call_agent":
                    level = config.get("level", 0)
                    if level in [2, 3]:
                        agents.append(name)
            
            return agents
        except:
            return ["writing_agent"]
    
    def get_banner_text(self):
        """获取 banner 文本（用于顶部固定显示）"""
        return (
            "="*80 + "\n" +
            "🤖 MLA Agent - 交互式 CLI 模式\n" +
            "="*80 + "\n" +
            f"📂 工作目录: {self.task_id}\n" +
            f"🤖 默认Agent: {self.current_agent}\n" +
            f"📋 可用Agents: {', '.join(self.available_agents[:3])}{'...' if len(self.available_agents) > 3 else ''}\n" +
            "-"*80 + "\n" +
            "💡 使用说明:\n" +
            "  - 直接输入任务（使用默认 Agent）\n" +
            "  - @agent_name 任务（切换并使用指定 Agent）\n" +
            "  - Ctrl+C 中断任务 | /quit 退出 | /help 帮助\n" +
            "-"*80 + "\n"
        )
    
    def show_banner(self):
        """显示欢迎信息（初始时）"""
        if RICH_AVAILABLE:
            self.console.clear()
            
            # 创建顶部 Panel
            header_table = Table.grid(padding=(0, 2))
            header_table.add_column(style="cyan")
            header_table.add_column()
            
            header_table.add_row("📂 工作目录:", self.task_id)
            header_table.add_row("🤖 默认Agent:", f"[bold green]{self.current_agent}[/]")
            header_table.add_row("📋 可用Agents:", ", ".join(self.available_agents[:4]) + ("..." if len(self.available_agents) > 4 else ""))
            
            self.console.print(Panel(
                header_table,
                title="[bold blue]🤖 MLA Agent - 交互式 CLI[/]",
                border_style="blue"
            ))
            
            # 使用说明
            help_text = Text()
            help_text.append("💡 使用说明:\n", style="bold yellow")
            help_text.append("  • 直接输入任务（使用默认 Agent）\n")
            help_text.append("  • @agent_name 任务（切换并使用指定 Agent）\n")
            help_text.append("  • Ctrl+C 中断任务 | /quit 退出 | /help 帮助\n")
            
            self.console.print(Panel(help_text, border_style="dim"))
            print()
        else:
            # 回退到简单模式
            os.system('clear' if os.name != 'nt' else 'cls')
            print(self.get_banner_text())
    
    def parse_input(self, user_input: str):
        """
        解析用户输入
        
        Returns:
            (agent_name, task_description)
        """
        user_input = user_input.strip()
        
        # 检查是否指定 agent
        if user_input.startswith('@'):
            parts = user_input[1:].split(None, 1)
            if len(parts) == 2:
                agent_name, task = parts
                # 验证 agent 是否存在
                if agent_name in self.available_agents:
                    return agent_name, task
                else:
                    print(f"⚠️  Agent '{agent_name}' 不存在，使用默认 Agent")
                    return self.current_agent, user_input
            elif len(parts) == 1:
                # 只有 @agent_name，没有任务
                agent_name = parts[0]
                if agent_name in self.available_agents:
                    self.current_agent = agent_name
                    print(f"✅ 已切换到: {agent_name}")
                    return None, None
                else:
                    print(f"⚠️  Agent '{agent_name}' 不存在")
                    return None, None
        
        # 没有 @，使用默认 agent
        return self.current_agent, user_input
    
    def stop_current_task(self):
        """停止当前运行的任务"""
        if self.current_process and self.current_process.poll() is None:
            try:
                if platform.system() == 'Windows':
                    # Windows: 发送 Ctrl+Break 信号
                    self.current_process.send_signal(signal.CTRL_BREAK_EVENT)
                    try:
                        self.current_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        # 如果信号无效，强制终止
                        self.current_process.terminate()
                        self.current_process.wait(timeout=1)
                else:
                    # Unix/Mac: 使用 terminate (发送 SIGTERM)
                    self.current_process.terminate()
                    self.current_process.wait(timeout=3)
                print("\n⚠️  已终止前一个任务\n")
            except Exception as e:
                # 最后手段：强制 kill
                try:
                    self.current_process.kill()
                    self.current_process.wait(timeout=1)
                except:
                    pass
    
    def run_task(self, agent_name: str, user_input: str):
        """
        在后台运行任务（JSONL模式）
        前台保持输入可用
        """
        # 终止当前任务（如果有）
        self.stop_current_task()
        
        print(f"\n{'='*80}")
        print(f"🤖 启动任务: {agent_name}")
        print(f"📝 输入: {user_input}")
        print(f"💡 提示: 输入相同内容+相同Agent可续跑，输入新内容开始新任务")
        print(f"{'='*80}\n")
        
        # 获取 mla-agent 命令路径
        import shutil
        mla_cmd = shutil.which('mla-agent') or 'mla-agent'
        
        # Windows 需要特殊的进程创建标志以支持信号处理
        popen_kwargs = {
            'stdout': subprocess.PIPE,
            'stderr': subprocess.PIPE,
            'text': True,
            'encoding': 'utf-8',
            'errors': 'replace',
            'bufsize': 0  # 无缓冲，实时输出
        }
        
        if platform.system() == 'Windows':
            # Windows: 创建新的进程组，允许发送 Ctrl+Break
            popen_kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        
        # 启动子进程（JSONL模式 - 实时流式输出）
        self.current_process = subprocess.Popen(
            [
                mla_cmd,
                '--task_id', self.task_id,
                '--agent_name', agent_name,
                '--user_input', user_input,
                '--agent_system', self.agent_system,
                '--jsonl'  # JSONL 模式，实时流式输出
            ],
            **popen_kwargs
        )
        
        # 后台线程读取输出（JSONL 模式，解析并显示）
        def read_output():
            try:
                import json
                for line in self.current_process.stdout:
                    if not line:
                        continue
                    line = line.rstrip('\n')
                    if not line.strip():
                        continue
                    
                    try:
                        # 解析 JSONL 事件
                        event = json.loads(line)
                        
                        # 显示所有事件（不截断）
                        if event['type'] == 'token':
                            text = event['text']
                            # 完整显示所有文本
                            display_line = f"  {text}"
                            
                            self.output_lines.append(display_line)
                            if len(self.output_lines) > self.max_output_lines:
                                self.output_lines.pop(0)
                            print(display_line)
                        
                        elif event['type'] == 'result':
                            # 显示完整结果
                            summary = event.get('summary', '')
                            
                            print(f"\n{'='*80}")
                            print("📊 执行结果:")
                            print(f"{'='*80}")
                            print(summary)  # 完整显示
                            print(f"{'='*80}\n")
                            
                            # 简短摘要到输出历史
                            self.output_lines.append(f"📊 结果: {summary[:100]}...")
                        
                        elif event['type'] == 'end':
                            status_icon = "✅" if event.get('status') == 'ok' else "❌"
                            duration_sec = event.get('duration_ms', 0) / 1000
                            display_line = f"{status_icon} 任务完成 ({duration_sec:.1f}s)"
                            self.output_lines.append(display_line)
                            print(display_line)
                            print()
                    
                    except json.JSONDecodeError:
                        # 不是有效的 JSON，跳过
                        pass
            except Exception:
                pass
        
        thread = threading.Thread(target=read_output, daemon=True)
        thread.start()

        # 读取 stderr，防止管道阻塞（但不显示，因为 JSONL 模式下 print 被重定向到 stderr）
        def read_stderr():
            try:
                for err in self.current_process.stderr:
                    if not err:
                        continue
                    # 静默消费 stderr，防止管道写满阻塞
                    # 只在遇到真正的错误关键词时才显示
                    err = err.rstrip('\n')
                    if any(keyword in err for keyword in ['Error:', 'Exception:', 'Traceback', 'CRITICAL', 'FATAL']):
                        error_line = f"⚠️ {err[:200]}"
                        self.output_lines.append(error_line)
                        if len(self.output_lines) > self.max_output_lines:
                            self.output_lines.pop(0)
                        print(error_line)
            except Exception:
                pass

        thread_err = threading.Thread(target=read_stderr, daemon=True)
        thread_err.start()
    
    def get_bottom_toolbar(self):
        """获取底部工具栏文本"""
        return HTML(
            f'<style bg="ansiblue" fg="ansiwhite"> 💡 @agent 切换 | 相同输入=续跑 | 新输入=新任务 | /quit 退出 </style>'
        )
    
    def run(self):
        """运行交互式 CLI"""
        self.show_banner()
        
        # 使用 prompt_toolkit（如果可用）
        if PROMPT_TOOLKIT_AVAILABLE:
            # 创建自动补全
            agent_completions = ['@' + agent for agent in self.available_agents]
            completer = WordCompleter(
                agent_completions + ['/quit', '/exit', '/help', '/agents'],
                ignore_case=True,
                sentence=True
            )
            
            session = PromptSession(
                completer=completer,
                bottom_toolbar=self.get_bottom_toolbar
            )
        
        while True:
            try:
                # 显示提示符（紧贴工具栏，无多余空白）
                if PROMPT_TOOLKIT_AVAILABLE:
                    # 使用 patch_stdout 确保任务输出不影响输入
                    with patch_stdout():
                        user_input = session.prompt(f"[{self.current_agent}] > ").strip()
                else:
                    user_input = input(f"[{self.current_agent}] > ").strip()
                
                if not user_input:
                    continue
                
                # 处理命令
                if user_input in ['/quit', '/exit', '/q']:
                    # 终止运行中的任务
                    if self.current_process and self.current_process.poll() is None:
                        print("\n⏹️  正在停止运行中的任务...")
                        try:
                            if platform.system() == 'Windows':
                                self.current_process.send_signal(signal.CTRL_BREAK_EVENT)
                                try:
                                    self.current_process.wait(timeout=2)
                                except subprocess.TimeoutExpired:
                                    self.current_process.terminate()
                                    self.current_process.wait(timeout=1)
                            else:
                                self.current_process.terminate()
                                self.current_process.wait(timeout=3)
                            print("✅ 任务已停止")
                        except:
                            try:
                                self.current_process.kill()
                                print("✅ 任务已强制终止")
                            except:
                                pass
                    print("\n👋 再见！\n")
                    break
                
                if user_input == '/help':
                    # 清屏并重新显示 banner
                    os.system('clear' if os.name != 'nt' else 'cls')
                    print(self.get_banner_text())
                    continue
                
                if user_input == '/agents':
                    print("\n📋 可用 Agents:")
                    for i, agent in enumerate(self.available_agents, 1):
                        mark = " (当前)" if agent == self.current_agent else ""
                        print(f"  {i}. {agent}{mark}")
                    print()
                    continue
                
                # 解析输入
                agent_name, task = self.parse_input(user_input)
                
                if agent_name and task:
                    # 执行任务
                    self.run_task(agent_name, task)
                
            except KeyboardInterrupt:
                # Ctrl+C: 终止当前任务但不退出 CLI
                if self.current_process and self.current_process.poll() is None:
                    print("\n\n⚠️  正在中断任务...")
                    try:
                        if platform.system() == 'Windows':
                            # Windows: 发送 Ctrl+Break 信号
                            self.current_process.send_signal(signal.CTRL_BREAK_EVENT)
                            try:
                                self.current_process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                self.current_process.terminate()
                                try:
                                    self.current_process.wait(timeout=1)
                                except:
                                    self.current_process.kill()
                        else:
                            # Unix/Mac: 使用 terminate
                            self.current_process.terminate()
                            try:
                                self.current_process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                self.current_process.kill()
                    except Exception:
                        try:
                            self.current_process.kill()
                        except:
                            pass
                    print("✅ 任务已中断\n")
                    print("💡 输入相同内容可续跑，输入新内容开始新任务\n")
                else:
                    print("\n\n💡 没有运行中的任务。输入 /quit 退出 CLI\n")
                continue
            except EOFError:
                # Ctrl+D: 退出
                if self.current_process and self.current_process.poll() is None:
                    print("\n\n⏹️  正在停止运行中的任务...")
                    try:
                        if platform.system() == 'Windows':
                            self.current_process.send_signal(signal.CTRL_BREAK_EVENT)
                            try:
                                self.current_process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                self.current_process.terminate()
                                self.current_process.wait(timeout=1)
                        else:
                            self.current_process.terminate()
                            self.current_process.wait(timeout=3)
                    except:
                        try:
                            self.current_process.kill()
                        except:
                            pass
                print("\n\n👋 再见！\n")
                break


def start_cli_mode(agent_system: str = "Test_agent"):
    """启动交互式 CLI 模式"""
    # task_id = 当前目录
    task_id = os.path.abspath(os.getcwd())
    
    cli = InteractiveCLI(task_id, agent_system)
    cli.run()


if __name__ == "__main__":
    start_cli_mode()

