#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSONL 事件输出工具 - 用于 VS Code 插件集成
"""

import sys
import json
import time
from typing import Dict, Any, Optional, List


class EventEmitter:
    """JSONL 事件发射器"""
    
    def __init__(self, enabled: bool = False):
        """
        Args:
            enabled: 是否启用 JSONL 输出模式
        """
        self.enabled = enabled
        self.call_id = None
        self.start_time = None
    
    def emit(self, event: Dict[str, Any]):
        """发射一个事件（JSONL格式）"""
        if not self.enabled:
            return
        
        # 直接写到原始 stdout（不受重定向影响）
        if hasattr(sys, 'stdout_orig'):
            sys.stdout_orig.write(json.dumps(event, ensure_ascii=False) + "\n")
            sys.stdout_orig.flush()
        else:
            sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    
    def start(self, call_id: str, project: str, agent: str, task: str):
        """任务开始"""
        self.call_id = call_id
        self.start_time = time.time()
        self.emit({
            "type": "start",
            "call_id": call_id,
            "project": project,
            "agent": agent,
            "task": task
        })
    
    def token(self, text: str):
        """流式文本输出"""
        if not self.call_id:
            return
        self.emit({
            "type": "token",
            "call_id": self.call_id,
            "text": text
        })
    
    def progress(self, phase: str, pct: int):
        """进度更新"""
        if not self.call_id:
            return
        self.emit({
            "type": "progress",
            "call_id": self.call_id,
            "phase": phase,
            "pct": pct
        })
    
    def notice(self, text: str):
        """通知"""
        if not self.call_id:
            return
        self.emit({
            "type": "notice",
            "call_id": self.call_id,
            "text": text
        })
    
    def warn(self, text: str):
        """警告"""
        if not self.call_id:
            return
        self.emit({
            "type": "warn",
            "call_id": self.call_id,
            "text": text
        })
    
    def error(self, text: str):
        """错误"""
        if not self.call_id:
            return
        self.emit({
            "type": "error",
            "call_id": self.call_id,
            "text": text
        })
    
    def artifact(self, kind: str, path: Optional[str] = None, 
                summary: Optional[str] = None, preview: Optional[str] = None):
        """产物"""
        if not self.call_id:
            return
        self.emit({
            "type": "artifact",
            "call_id": self.call_id,
            "kind": kind,
            "path": path,
            "summary": summary,
            "preview": preview
        })
    
    def human_in_loop(self, hil_id: str, title: str, message: str,
                     ui: Dict[str, Any], timeout_sec: int = 1800,
                     resume_hint: Optional[str] = None):
        """人机交互"""
        if not self.call_id:
            return
        self.emit({
            "type": "human_in_loop",
            "call_id": self.call_id,
            "hil_id": hil_id,
            "title": title,
            "message": message,
            "ui": ui,
            "timeout_sec": timeout_sec,
            "resume_hint": resume_hint
        })
    
    def result(self, ok: bool, summary: str, artifacts: Optional[List[str]] = None):
        """最终结果"""
        if not self.call_id:
            return
        self.emit({
            "type": "result",
            "call_id": self.call_id,
            "ok": ok,
            "summary": summary,
            "artifacts": artifacts or []
        })
    
    def tool_call(self, tool_name: str, parameters: Dict[str, Any]):
        """工具调用事件"""
        if not self.call_id:
            return
        self.emit({
            "type": "tool_call",
            "call_id": self.call_id,
            "tool_name": tool_name,
            "parameters": parameters
        })
    
    def agent_call(self, agent_name: str, parameters: Dict[str, Any]):
        """子 Agent 调用事件"""
        if not self.call_id:
            return
        self.emit({
            "type": "agent_call",
            "call_id": self.call_id,
            "agent_name": agent_name,
            "parameters": parameters
        })
    
    def end(self, status: str, extra: Optional[Dict] = None):
        """任务结束"""
        if not self.call_id:
            return
        
        duration_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0
        
        event = {
            "type": "end",
            "call_id": self.call_id,
            "status": status,
            "duration_ms": duration_ms
        }
        
        if extra:
            event.update(extra)
        
        self.emit(event)


# 全局实例
_event_emitter = EventEmitter(enabled=False)


def init_event_emitter(enabled: bool = False):
    """初始化全局事件发射器"""
    global _event_emitter
    _event_emitter = EventEmitter(enabled=enabled)
    return _event_emitter


def get_event_emitter() -> EventEmitter:
    """获取全局事件发射器"""
    return _event_emitter

