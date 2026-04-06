import time
import os
from typing import Optional, Dict, List, Any
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.provider.provider import EmbeddingProvider
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .zvec_vector_db import ZVecVectorDB


class LongMemory(Star):
    """长期记忆插件，用于存储和管理AI的长期记忆"""
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.vector_db: Optional[ZVecVectorDB] = None
        self.context = context
        self.plugin_data_path: Optional[str] = None
        self._embedding_dim: Optional[int] = None

    async def initialize(self) -> None:
        """初始化插件，设置数据路径并初始化向量数据库"""
        try:
            self._setup_plugin_data_path()
            self._initialize_vector_db()
        except Exception as e:
            logger.error(f"长期记忆插件初始化失败: {e}")

    def _setup_plugin_data_path(self) -> None:
        """设置插件数据路径"""
        self.plugin_data_path = os.path.realpath(
            os.path.join(get_astrbot_data_path(), "plugin_data", self.name)
        )
        os.makedirs(self.plugin_data_path, exist_ok=True)
        logger.debug(f"插件数据路径设置为: {self.plugin_data_path}")

    def _initialize_vector_db(self) -> None:
        """初始化向量数据库"""
        embedding_dim = self._get_embedding_dim()
        if embedding_dim and self.plugin_data_path:
            self.vector_db = ZVecVectorDB(
                plugin_data_path=self.plugin_data_path,
                embedding_dim=embedding_dim,
                collection_name="longterm_memory"
            )
            logger.info(f"长期记忆插件初始化成功，嵌入维度: {embedding_dim}")
        else:
            logger.warning("无法获取嵌入维度或数据路径，向量数据库未初始化")

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest) -> None:
        """LLM请求钩子，在请求前添加记忆到系统提示词"""
        await event.send(MessageChain().message("🤔 thinking..."))
        req.system_prompt += await self._create_prompt(event.get_message_str())

    @filter.command("test")
    async def test_command(self, event: AstrMessageEvent) -> None:
        """测试命令"""
        pass

    async def terminate(self) -> None:
        """插件销毁方法，当插件被卸载/停用时会调用"""
        pass

    @filter.llm_tool(name="set_memory")
    async def set_memory(self, event: AstrMessageEvent, content: str, method: str) -> str:
        """设置长期记忆，会附加到system提示词中

        Args:
            content(string): 内容，用markdown和英文，尽量简洁
            method(string): 设置方法，可选值为：replace, append
        Returns:
            设置结果
        """
        try:
            if not isinstance(content, str):
                logger.warning("set_memory: 内容必须是字符串类型")
                return "error: 内容必须是字符串类型"
            if not content:
                logger.warning("set_memory: 内容为空")
                return "error: 内容不能为空"
            if not isinstance(method, str):
                logger.warning("set_memory: 方法必须是字符串类型")
                return "error: 方法必须是字符串类型"
            if method not in ["replace", "append"]:
                logger.warning(f"set_memory: 无效的方法: {method}")
                return "error: 无效的方法，可选值为 replace 或 append"
            
            self._file_operation("memory.md", content, method == "replace")
            logger.info(f"记忆已{method}")
            return "success"
        except Exception as e:
            logger.error(f"set_memory 失败: {e}")
            return f"error: {str(e)}"

    @filter.llm_tool(name="set_soul")
    async def set_soul(self, event: AstrMessageEvent, content: str, method: str) -> str:
        """设置灵魂，用于对话风格相关功能

        Args:
            content(string): 内容，用markdown和英文，尽量简洁
            method(string): 设置方法，可选值为：replace, append
        Returns:
            设置结果
        """
        try:
            if not isinstance(content, str):
                logger.warning("set_soul: 内容必须是字符串类型")
                return "error: 内容必须是字符串类型"
            if not content:
                logger.warning("set_soul: 内容为空")
                return "error: 内容不能为空"
            if not isinstance(method, str):
                logger.warning("set_soul: 方法必须是字符串类型")
                return "error: 方法必须是字符串类型"
            if method not in ["replace", "append"]:
                logger.warning(f"set_soul: 无效的方法: {method}")
                return "error: 无效的方法，可选值为 replace 或 append"
            
            self._file_operation("soul.md", content, method == "replace")
            logger.info(f"灵魂已{method}")
            return "success"
        except Exception as e:
            logger.error(f"set_soul 失败: {e}")
            return f"error: {str(e)}"

    @filter.llm_tool(name="set_recent_memory")
    async def set_recent_memory(self, event: AstrMessageEvent, content: str) -> str:
        """设置最近记忆，使近1天的对话都可以记住这个内容

        Args:
            content(string): 内容，用markdown和英文，尽量简洁
        Returns:
            设置结果
        """
        try:
            if not isinstance(content, str):
                logger.warning("set_recent_memory: 内容必须是字符串类型")
                return "error: 内容必须是字符串类型"
            if not content:
                logger.warning("set_recent_memory: 内容为空")
                return "error: 内容不能为空"
                
            file_name = f"recent_memory/{time.strftime('%Y-%m-%d')}.md"
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            
            if self.vector_db:
                metadata = {
                    "timestamp": timestamp,
                    "filename": file_name
                }
                doc_id = await self._store_to_vector_db(content, metadata)
                if doc_id:
                    content_with_id = f"{content}\n\n[ID: {doc_id}]\n[Timestamp: {timestamp}]\n"
                    self._file_operation(file_name, content_with_id, False)
                    logger.info(f"最近记忆已存储到向量数据库，文档ID: {doc_id}")
                    return "success"
                else:
                    logger.warning("向量数据库存储失败，回退到文件存储")
            
            self._file_operation(file_name, content, False)
            logger.info("最近记忆已存储到文件")
            return "success"
        except Exception as e:
            logger.error(f"set_recent_memory 失败: {e}")
            return f"error: {str(e)}"

    def _file_operation(self, file_path: str, content: str, replace: bool = True) -> None:
        """文件操作，支持替换或追加内容

        Args:
            file_path: 文件路径
            content: 内容
            replace: 是否替换
        """
        if not self.plugin_data_path:
            raise ValueError("插件数据路径未设置")
        
        # 检查内容大小，限制为10MB
        max_size = 10 * 1024 * 1024  # 10MB
        if len(content) > max_size:
            raise ValueError(f"内容大小超过限制 ({max_size / (1024 * 1024):.1f}MB)")
            
        full_path = os.path.join(self.plugin_data_path, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        mode = "w" if replace else "a"
        with open(full_path, mode, encoding="utf-8") as f:
            f.write(content)
        
        operation = "替换" if replace else "追加"
        logger.debug(f"文件已{operation}: {full_path}")

    def _read_file(self, file_path: str) -> str:
        """读取文件内容

        Args:
            file_path: 文件路径
        Returns:
            文件内容
        """
        try:
            if not self.plugin_data_path:
                raise ValueError("插件数据路径未设置")
                
            full_path = os.path.join(self.plugin_data_path, file_path)
            
            # 检查文件大小，限制为10MB
            max_size = 10 * 1024 * 1024  # 10MB
            if os.path.exists(full_path) and os.path.getsize(full_path) > max_size:
                logger.warning(f"文件过大，超过限制 ({max_size / (1024 * 1024):.1f}MB): {full_path}")
                return ""
            
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
                logger.debug(f"已读取文件: {full_path}，大小: {len(content)} 字符")
                return content
        except FileNotFoundError:
            logger.debug(f"文件未找到: {file_path}")
            return ""
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
            return ""

    async def _create_prompt(self, message: str) -> str:
        """创建包含记忆的提示词

        Args:
            message(string): 用户消息
        Returns:
            提示词
        """
        recent_file_name = f"recent_memory/{time.strftime('%Y-%m-%d')}.md"
        prompt = "---Memory.md---"
        prompt += self._read_file("memory.md")
        prompt += "\n"
        prompt += "---Soul.md---"
        prompt += self._read_file("soul.md")
        prompt += "\n"
        prompt += f"---{recent_file_name}---"
        prompt += self._read_file(recent_file_name)
        prompt += "---you can use tools to change them---"
        
        if self.vector_db:
            results = await self._search_memory(message)
            if results:
                prompt += "\n"
                prompt += "---RAG---"
                prompt += str(results)
        return prompt

    def _get_embedding_provider(self) -> Optional[EmbeddingProvider]:
        """获取配置的嵌入模型提供商

        Returns:
            嵌入模型提供商
        """
        embedding_provider_id = self.config.get("embedding_provider_id")
        if not embedding_provider_id:
            logger.warning("未配置嵌入模型提供商")
            return None
        provider = self.context.get_provider_by_id(embedding_provider_id)
        if not provider or not isinstance(provider, EmbeddingProvider):
            logger.warning(f"无法获取嵌入模型提供商: {embedding_provider_id}")
            return None
        return provider

    def _get_embedding_dim(self) -> Optional[int]:
        """获取嵌入模型的维度

        Returns:
            嵌入维度
        """
        if self._embedding_dim is not None:
            return self._embedding_dim
        
        provider = self._get_embedding_provider()
        if not provider:
            logger.warning("无法获取嵌入模型提供商")
            return None
        try:
            self._embedding_dim = provider.get_dim()
            return self._embedding_dim
        except Exception as e:
            logger.error(f"获取嵌入维度失败: {e}")
            return None

    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """生成文本的嵌入向量

        Args:
            text: 文本
        Returns:
            嵌入向量
        """
        provider = self._get_embedding_provider()
        if not provider:
            logger.warning("无法获取嵌入模型提供商")
            return None
        try:
            embedding = await provider.get_embedding(text)
            return embedding
        except Exception as e:
            logger.error(f"生成嵌入向量失败: {e}")
            return None

    async def _generate_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """批量生成文本的嵌入向量

        Args:
            texts: 文本列表
        Returns:
            嵌入向量列表
        """
        provider = self._get_embedding_provider()
        if not provider:
            logger.warning("无法获取嵌入模型提供商")
            return None
        try:
            embeddings = await provider.get_embeddings(texts)
            return embeddings
        except Exception as e:
            logger.error(f"批量生成嵌入向量失败: {e}")
            return None

    async def _store_to_vector_db(self, text: str, metadata: Dict[str, Any]) -> Optional[str]:
        """存储文本到向量数据库

        Args:
            text: 文本内容
            metadata: 元数据
        Returns:
            文档ID
        """
        try:
            if self.vector_db is None:
                logger.warning("向量数据库未初始化")
                return None
            if not isinstance(text, str):
                logger.warning("store: 文本必须是字符串类型")
                return None
            if not text:
                logger.warning("store: 文本内容为空")
                return None
            if not isinstance(metadata, dict):
                logger.warning("store: 元数据必须是字典类型")
                return None
            
            result = await self.vector_db.store(text, metadata, self._generate_embedding)
            logger.info(f"文本存储到向量数据库: {result}")
            # 确保返回值是字符串或None
            if isinstance(result, str):
                return result
            return None
        except Exception as e:
            logger.error(f"store 失败: {e}")
            return None

    async def _search_memory(self, query_text: str, topk: int = 5) -> Optional[List[Dict[str, Any]]]:
        """搜索相关记忆

        Args:
            query_text: 查询文本
            topk: 返回前 K 个最相关的结果
        Returns:
            搜索结果
        """
        if self.vector_db is None:
            return None
        if not isinstance(query_text, str):
            logger.warning("search: 查询文本必须是字符串类型")
            return None
        if not isinstance(topk, int) or topk <= 0:
            logger.warning("search: topk必须是正整数")
            topk = 5
        embedding = await self._generate_embedding(query_text)
        if not embedding:
            logger.error("无法生成查询嵌入向量")
            return None
        return await self.vector_db.search(embedding, topk)

    async def _delete_from_vector_db(self, text: str) -> bool:
        """从向量数据库删除文本

        Args:
            text: 要删除的文本
        Returns:
            是否删除成功
        """
        try:
            if self.vector_db is None:
                logger.warning("向量数据库未初始化")
                return False
            if not isinstance(text, str):
                logger.warning("delete: 文本必须是字符串类型")
                return False
            if not text:
                logger.warning("delete: 文本内容为空")
                return False
            
            result = await self.vector_db.delete(text)
            logger.info(f"从向量数据库删除文本: {result}")
            return result
        except Exception as e:
            logger.error(f"delete 失败: {e}")
            return False

