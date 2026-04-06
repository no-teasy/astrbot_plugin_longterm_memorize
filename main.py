import time
import os
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.provider.provider import EmbeddingProvider
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

from .zvec_vector_db import ZVecVectorDB


class LongMemory(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.zvec_db = None
        self.context = context

    async def initialize(self):
        try:
            self.plugin_data_path = os.path.realpath(os.path.join(get_astrbot_data_path(), "plugin_data", self.name))
            os.makedirs(self.plugin_data_path, exist_ok=True)
            
            embedding_dim = self.get_embedding_dim()
            if embedding_dim:
                self.zvec_db = ZVecVectorDB(
                    plugin_data_path=self.plugin_data_path,
                    embedding_dim=embedding_dim,
                    collection_name="longterm_memory"
                )
                logger.info(f"长期记忆插件初始化成功，嵌入维度: {embedding_dim}")
            else:
                logger.warning("无法获取嵌入维度，向量数据库未初始化")
        except Exception as e:
            logger.error(f"长期记忆插件初始化失败: {e}")
        
        
    @filter.on_llm_request()
    async def my_custom_hook_1(self, event: AstrMessageEvent, req: ProviderRequest):
        
        await event.send(MessageChain().message("🤔 thinking..."))
        req.system_prompt += self.create_prompt(event.get_message_str())
        print(req)
    
    @filter.command("test")
    async def helloworld(self, event: AstrMessageEvent):
        pass
        

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        pass
    
    @filter.llm_tool(name="set_memory")
    async def set_memory(self, event: AstrMessageEvent, content: str, method: str):
        '''设置你的记忆，使每次对话都可以记住这个内容，会附加到system提示词中，使用markdown和英文，尽量简洁
    
        Args:
            content(string): 内容，用markdown和英文，尽量简洁
            method(string): 设置方法 ，可选值为：replace, append
        Returns:
            string: 设置成功
        ''' 
        try:
            if not content:
                logger.warning("set_memory: 内容为空")
                return "error: 内容不能为空"
            if method not in ["replace", "append"]:
                logger.warning(f"set_memory: 无效的方法: {method}")
                return "error: 无效的方法，可选值为 replace 或 append"
            
            self.replace_or_append("memory.md", content, method == "replace")
            logger.info(f"记忆已{method}")
            return "success"
        except Exception as e:
            logger.error(f"set_memory 失败: {e}")
            return f"error: {str(e)}"
    
    @filter.llm_tool(name="set_soul")
    async def set_soul(self, event: AstrMessageEvent, content: str, method: str):
        '''设置你的灵魂，用于对话风格相关功能,当你需要调整自己的人格设定的时候调用,必须使用它来持久化人格设定,使用markdown和英文
    
        Args:
            content(string): 内容，用markdown和英文，尽量简洁
            method(string): 设置方法 ，可选值为：replace, append
        Returns:
            string: 设置成功
        ''' 
        try:
            if not content:
                logger.warning("set_soul: 内容为空")
                return "error: 内容不能为空"
            if method not in ["replace", "append"]:
                logger.warning(f"set_soul: 无效的方法: {method}")
                return "error: 无效的方法，可选值为 replace 或 append"
            
            self.replace_or_append("soul.md", content, method == "replace")
            logger.info(f"灵魂已{method}")
            return "success"
        except Exception as e:
            logger.error(f"set_soul 失败: {e}")
            return f"error: {str(e)}"
    
    @filter.llm_tool(name="set_recent_memory")
    async def set_recent_memory(self, event: AstrMessageEvent, content: str):
        '''设置你的最近记忆，使近1天的对话都可以记住这个内容，文件名为yyyy-mm-dd.md会附加到system提示词中，使用它保证最近发生的事件记忆的持久化，追加更改，当每次任务完成的时候、与用户进行某一个话题、发生什么事的时候调用、后续会通过RAG注入到上下文
    
        Args:
            content(string): 内容，用markdown和英文，尽量简洁
        Returns:
            string: 设置成功
        ''' 
        try:
            if not content:
                logger.warning("set_recent_memory: 内容为空")
                return "error: 内容不能为空"
                
            file_name = f"recent_memory/{time.strftime('%Y-%m-%d')}.md"
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            
            if self.zvec_db:
                metadata = {
                    "timestamp": timestamp,
                    "filename": file_name
                }
                doc_id = await self.zvec_db.store(content, metadata)
                if doc_id:
                    content_with_id = f"{content}\n\n[ID: {doc_id}]\n[Timestamp: {timestamp}]\n"
                    self.replace_or_append(file_name, content_with_id, False)
                    logger.info(f"最近记忆已存储到向量数据库，文档ID: {doc_id}")
                    return "success"
                else:
                    logger.warning("向量数据库存储失败，回退到文件存储")
            
            self.replace_or_append(file_name, content, False)
            logger.info("最近记忆已存储到文件")
            return "success"
        except Exception as e:
            logger.error(f"set_recent_memory 失败: {e}")
            return f"error: {str(e)}"
    
    def replace_or_append(self, file_path: str, content: str, replace: bool = True):
        try:
            file_path = os.path.join(self.plugin_data_path, file_path)
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            if replace:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.debug(f"文件已替换: {file_path}")
            else:
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(content)
                logger.debug(f"内容已追加到文件: {file_path}")
        except Exception as e:
            logger.error(f"文件操作失败 {file_path}: {e}")
            raise
    
    def read_file(self, file_path: str):
        try:
            file_path = os.path.join(self.plugin_data_path, file_path)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                logger.debug(f"已读取文件: {file_path}，大小: {len(content)} 字符")
                return content
        except FileNotFoundError:
            logger.debug(f"文件未找到: {file_path}")
            return ""
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
            return ""

    def create_prompt(self,message:str):
        recent_file_name = f"recent_memory/{time.strftime('%Y-%m-%d')}.md"
        prompt = None
        prompt = "---Memory.md---"
        prompt += self.read_file("memory.md")
        prompt += "\n"
        prompt += "---Soul.md---"
        prompt += self.read_file("soul.md")
        prompt += "\n"
        prompt += "---{recent_file_name}---"
        prompt += self.read_file(recent_file_name)
        prompt += "---you can use tools to change them---"
        if self.zvec_db and self.get_embedding_dim():
            
            results = self.search(message)
            if results:
                prompt += "\n"
                prompt += "---RAG---"
                prompt += str(results)
        return prompt

    def get_embedding_provider(self)->EmbeddingProvider|None:
        """获取配置的嵌入模型提供商"""
        embedding_provider_id = self.config.get("embedding_provider_id")
        if not embedding_provider_id:
            logger.warning("未配置嵌入模型提供商")
            return None
        provider = self.context.get_provider_by_id(embedding_provider_id)
        if not provider or not isinstance(provider, EmbeddingProvider):
            logger.warning(f"无法获取嵌入模型提供商: {embedding_provider_id}")
            return None
        return provider

    def get_embedding_dim(self):
        """获取嵌入模型的维度"""
        provider = self.get_embedding_provider()
        if not provider:
            logger.warning("无法获取嵌入模型提供商")
            return None
        try:
            return provider.get_dim()
        except Exception as e:
            logger.error(f"获取嵌入维度失败: {e}")
            return None

    async def generate_embedding(self, text: str):
        """生成文本的嵌入向量"""
        provider = self.get_embedding_provider()
        if not provider:
            logger.warning("无法获取嵌入模型提供商")
            return None
        try:
            embedding = await provider.get_embedding(text)
            return embedding
        except Exception as e:
            logger.error(f"生成嵌入向量失败: {e}")
            return None

    async def generate_embeddings(self, texts: list[str]):
        """批量生成文本的嵌入向量"""
        provider = self.get_embedding_provider()
        if not provider:
            logger.warning("无法获取嵌入模型提供商")
            return None
        try:
            embeddings = await provider.get_embeddings(texts)
            return embeddings
        except Exception as e:
            logger.error(f"批量生成嵌入向量失败: {e}")
            return None

    async def store(self, text: str, metadata: dict):
        """存储文本到向量数据库
        
        Args:
            text: 要存储的文本内容
            metadata: 元数据，可以包含额外的信息
        Returns:
            bool: 存储是否成功
        """
        try:
            if self.zvec_db is None:
                logger.warning("向量数据库未初始化")
                return None
            if not text:
                logger.warning("store: 文本内容为空")
                return False
            if not isinstance(metadata, dict):
                logger.warning("store: 元数据必须是字典类型")
                return False
            
            result = await self.zvec_db.store(text, metadata, self.generate_embedding)
            logger.info(f"文本存储到向量数据库: {result}")
            return result
        except Exception as e:
            logger.error(f"store 失败: {e}")
            return False

    async def search(self, query_text: str, topk: int = 5):
        """搜索相关文本
        
        Args:
            query_text: 查询文本
            topk: 返回前 K 个最相关的结果
        Returns:
            list: 搜索结果列表，包含 ID、相似度分数和元数据
        """
        if self.zvec_db ==None: return None
        embedding = await self.generate_embedding(query_text)
        if not embedding:
            logger.error("无法生成查询嵌入向量")
            return None
        return await self.zvec_db.search(embedding, topk)

    
    async def delete(self, text: str):
        """删除特定文本
        
        Args:
            text: 要删除的文本内容
        Returns:
            bool: 删除是否成功
        """
        try:
            if self.zvec_db is None:
                logger.warning("向量数据库未初始化")
                return False
            if not text:
                logger.warning("delete: 文本内容为空")
                return False
            
            result = await self.zvec_db.delete(text)
            logger.info(f"从向量数据库删除文本: {result}")
            return result
        except Exception as e:
            logger.error(f"delete 失败: {e}")
            return False

