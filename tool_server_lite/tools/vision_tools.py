#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vision分析工具 - 图片内容分析
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


class VisionTool(BaseTool):
    """图片Vision分析工具 - 调用LLM分析图片内容"""
    
    def execute(self, task_id: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行Vision分析
        
        Parameters:
            image_path (str): 图片文件相对路径（相对于任务目录）
            question (str, optional): 要问的问题，默认"请描述这张图片的内容"
            model (str, optional): 模型名称，默认使用配置中的模型
        
        Returns:
            status: "success" 或 "error"
            output: 分析结果文本
            error: 错误信息（如有）
        """
        try:
            # 获取参数
            image_path = parameters.get("image_path")
            question = parameters.get("question", "请描述这张图片的内容")
            model = parameters.get("model")
            
            if not image_path:
                return {
                    "status": "error",
                    "output": "",
                    "error": "缺少必需参数: image_path"
                }
            
            # 转换为绝对路径
            abs_image_path = get_abs_path(task_id, image_path)
            
            # 调用LLM客户端
            llm_client = get_llm_client()
            
            try:
                result = llm_client.vision_query(
                    image_path=str(abs_image_path),
                    question=question,
                    model=model
                )
                
                return {
                    "status": "success",
                    "output": result,
                    "error": ""
                }
                
            except FileNotFoundError as e:
                return {
                    "status": "error",
                    "output": "",
                    "error": f"图片文件不存在: {str(e)}"
                }
            except Exception as e:
                return {
                    "status": "error",
                    "output": "",
                    "error": f"Vision分析失败: {str(e)}"
                }
        
        except Exception as e:
            return {
                "status": "error",
                "output": "",
                "error": f"执行失败: {str(e)}"
            }

