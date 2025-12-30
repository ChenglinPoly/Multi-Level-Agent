#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对话历史存储 - 简化版
只保存action_history，不保存传统的user/assistant对话
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List
from datetime import datetime


class ConversationStorage:
    """对话历史存储器"""
    
    def __init__(self, task_id: str = None):
        """
        初始化存储器
        
        Args:
            task_id: 任务ID（绝对路径），如果提供则使用 task_id/conversations/，否则使用旧路径（向后兼容）
        """
        if task_id:
            # 使用 task_id 下的 conversations 目录
            self.conversations_dir = Path(task_id) / "conversations"
        else:
            # 向后兼容：如果没有提供 task_id，使用旧路径
            self.conversations_dir = Path.home() / "mla_v3" / "conversations"
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self.task_id = task_id
    
    def _generate_filename(self, task_id: str, agent_id: str) -> str:
        """生成对话文件名：直接使用 agent_id（不需要 hash，因为已经在 task_id 目录下了）"""
        # 如果 task_id 与初始化时不同，使用新的 task_id（向后兼容）
        if task_id and task_id != self.task_id:
            conversations_dir = Path(task_id) / "conversations"
            conversations_dir.mkdir(parents=True, exist_ok=True)
            return str(conversations_dir / f"{agent_id}_actions.json")
        
        return str(self.conversations_dir / f"{agent_id}_actions.json")
    
    def save_actions(self, task_id: str, agent_id: str, agent_name: str, 
                    task_input: str, action_history: List[Dict], current_turn: int,
                    latest_thinking: str = "", first_thinking_done: bool = False,
                    tool_call_counter: int = 0, system_prompt: str = "",
                    action_history_fact: List[Dict] = None,
                    pending_tools: List[Dict] = None):
        """
        保存动作历史和完整状态
        
        Args:
            task_id: 任务ID
            agent_id: Agent ID
            agent_name: Agent名称
            task_input: 任务输入
            action_history: 动作历史列表
            current_turn: 当前轮次
            latest_thinking: 最新的thinking内容
            first_thinking_done: 是否已完成首次thinking
            tool_call_counter: 工具调用计数
            system_prompt: 完整的system_prompt（包含XML上下文）
        """
        try:
            filepath = self._generate_filename(task_id, agent_id)
            
            data = {
                "task_id": task_id,
                "agent_id": agent_id,
                "agent_name": agent_name,
                "task_input": task_input,
                "current_turn": current_turn,
                "action_history": action_history,  # 用于渲染（会压缩）
                "action_history_fact": action_history_fact if action_history_fact else action_history,  # 完整轨迹
                "pending_tools": pending_tools if pending_tools else [],  # 待执行的工具
                "latest_thinking": latest_thinking,
                "first_thinking_done": first_thinking_done,
                "tool_call_counter": tool_call_counter,
                "system_prompt": system_prompt,
                "last_updated": datetime.now().isoformat()
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # print(f"💾 已保存状态: 第{current_turn}轮, {len(action_history)}个动作")
        
        except Exception as e:
            print(f"⚠️ 保存对话历史失败: {e}")
    
    def load_actions(self, task_id: str, agent_id: str) -> Dict:
        """
        加载动作历史
        
        Args:
            task_id: 任务ID
            agent_id: Agent ID
            
        Returns:
            动作历史数据，如果不存在则返回None
        """
        try:
            filepath = self._generate_filename(task_id, agent_id)
            
            if not Path(filepath).exists():
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"📂 已加载动作历史: 第{data.get('current_turn', 0)}轮, {len(data.get('action_history', []))}个动作")
            return data
        
        except Exception as e:
            print(f"⚠️ 加载对话历史失败: {e}")
            return None


if __name__ == "__main__":
    # 测试存储器
    storage = ConversationStorage()
    
    # 测试保存
    storage.save_actions(
        task_id="test",
        agent_id="agent_123",
        agent_name="test_agent",
        task_input="测试任务",
        action_history=[
            {"tool_name": "file_read", "arguments": {}, "result": {}}
        ],
        current_turn=1
    )
    
    # 测试加载
    data = storage.load_actions("test", "agent_123")
    print(f"✅ 加载的数据: {data}")

