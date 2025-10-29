#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio分析工具 - 音频内容分析
"""

from pathlib import Path
from typing import Dict, Any

from .file_tools import BaseTool, get_abs_path

# 导入llm_client_lite
import sys
import os
# 添加父目录到路径
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from llm_client_lite import get_llm_client


class AudioTool(BaseTool):
    """音频分析工具 - 调用LLM分析音频内容"""
    
    def execute(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行Audio分析
        
        Parameters:
            audio_path (str): 音频文件相对路径（相对于任务目录）
            question (str, optional): 要问的问题，默认"请描述这段音频的内容"
            model (str, optional): 模型名称，默认使用配置中的模型
        
        Returns:
            status: "success" 或 "error"
            output: 分析结果文本
            error: 错误信息（如有）
        """
        try:
            # 获取参数
            audio_path = parameters.get("audio_path")
            question = parameters.get("question", "请描述这段音频的内容")
            model = parameters.get("model")
            
            if not audio_path:
                return {
                    "status": "error",
                    "output": "",
                    "error": "缺少必需参数: audio_path"
                }
            
            # 转换为绝对路径
            abs_audio_path = get_abs_path(task_id, audio_path)
            
            # 调用LLM客户端
            llm_client = get_llm_client()
            
            try:
                result = llm_client.audio_query(
                    audio_path=str(abs_audio_path),
                    question=question,
                    model=model
                )
                
                return {
                    "status": "success",
                    "output": result,
                    "error": ""
                }
                
            except NotImplementedError as e:
                return {
                    "status": "error",
                    "output": "",
                    "error": "音频分析功能尚未实现，请等待开发完成。"
                }
            except FileNotFoundError as e:
                return {
                    "status": "error",
                    "output": "",
                    "error": f"音频文件不存在: {str(e)}"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "output": "",
                    "error": f"Audio分析失败: {str(e)}"
                }
        
        except Exception as e:
            return {
                "status": "error",
                "output": "",
                "error": f"执行失败: {str(e)}"
            }

