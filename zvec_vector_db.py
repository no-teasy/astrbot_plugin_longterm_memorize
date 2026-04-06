import os
import hashlib
from astrbot.api import logger


class ZVecVectorDB:
    """zvec 向量数据库操作类"""
    
    def __init__(self, plugin_data_path: str, embedding_dim: int, collection_name: str = "default_collection"):
        """
        初始化 zvec 向量数据库
        
        Args:
            plugin_data_path: 插件数据路径
            embedding_dim: 嵌入向量维度
            collection_name: 集合名称
        """
        self.plugin_data_path = plugin_data_path
        self.embedding_dim = embedding_dim
        self.collection_name = collection_name
        self.zvec_path = os.path.join(self.plugin_data_path, "zvec_data")
        self._zvec = None
    
    def _import_zvec(self):
        """导入 zvec 模块"""
        if self._zvec is None:
            try:
                import zvec
                self._zvec = zvec
            except ImportError:
                logger.error("zvec 库未安装，请运行: pip install zvec")
                return None
        return self._zvec
    
    def _generate_doc_id(self, text: str):
        """根据文本生成唯一的文档 ID"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _get_collection(self, create_if_not_exists: bool = False):
        """获取或创建集合
        
        Args:
            create_if_not_exists: 如果集合不存在是否创建
            
        Returns:
            zvec.Collection 实例
        """
        zvec = self._import_zvec()
        if zvec is None:
            return None
        
        try:
            schema = zvec.CollectionSchema(
                name=self.collection_name,
                vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, self.embedding_dim),
            )
            
            if create_if_not_exists:
                collection = zvec.create_and_open(
                    path=self.zvec_path,
                    schema=schema
                )
            else:
                collection = zvec.open(
                    path=self.zvec_path,
                    schema=schema
                )
            return collection
        except Exception as e:
            logger.error(f"获取集合失败: {e}")
            return None
    
    async def store(self, text: str, metadata: dict, embedding_func=None):
        """存储文本到向量数据库
        
        Args:
            text: 要存储的文本内容
            metadata: 元数据，可以包含额外的信息
            embedding_func: 生成嵌入向量的异步函数
        Returns:
            str or None: 存储的文档 ID，失败返回 None
        """
        zvec = self._import_zvec()
        if zvec is None:
            return False
        
        if not embedding_func:
            logger.error("未提供嵌入函数")
            return False
        
        try:
            embedding = await embedding_func(text)
            if not embedding:
                logger.error("无法生成嵌入向量")
                return False
            
            collection = self._get_collection(create_if_not_exists=True)
            if collection is None:
                return False
            
            doc_id = self._generate_doc_id(text)
            doc_data = {
                "id": doc_id,
                "vectors": {"embedding": embedding},
            }
            
            if metadata:
                doc_data["metadata"] = metadata
            
            collection.insert([zvec.Doc(**doc_data)])
            logger.info(f"已存储: {text[:50]}...")
            return doc_id
            
        except Exception as e:
            logger.error(f"存储失败: {e}")
            return False
    
    async def search(self, query_vector: list, topk: int = 5):
        """搜索相关文本
        
        Args:
            query_vector: 预先生成的查询向量
            topk: 返回前 K 个最相关的结果
        Returns:
            list: 搜索结果列表，包含 ID、相似度分数和元数据
        """
        zvec = self._import_zvec()
        if zvec is None:
            return None
        
        try:
            if not query_vector:
                logger.error("必须提供 query_vector")
                return None
            embedding = query_vector
            
            collection = self._get_collection(create_if_not_exists=False)
            if collection is None:
                return None
            
            results = collection.query(
                zvec.VectorQuery("embedding", vector=embedding),
                topk=topk
            )
            
            return results
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return None
    
    async def delete(self, text: str):
        """删除特定文本（通过文本哈希删除）
        
        Args:
            text: 要删除的文本内容
        Returns:
            bool: 删除是否成功
        """
        zvec = self._import_zvec()
        if zvec is None:
            return False
        
        try:
            doc_id = self._generate_doc_id(text)
            
            collection = self._get_collection(create_if_not_exists=False)
            if collection is None:
                return False
            
            collection.delete([doc_id])
            logger.info(f"已删除: {text[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"删除失败: {e}")
            return False
    
    async def list_all(self):
        """列出所有存储的文档
        
        Returns:
            list: 所有文档的列表
        """
        zvec = self._import_zvec()
        if zvec is None:
            return None
        
        try:
            collection = self._get_collection(create_if_not_exists=False)
            if collection is None:
                return None
            
            all_docs = collection.get_all()
            return all_docs
            
        except Exception as e:
            logger.error(f"列出失败: {e}")
            return None
    
    async def clear(self):
        """清空所有文档
        
        Returns:
            bool: 是否成功
        """
        zvec = self._import_zvec()
        if zvec is None:
            return False
        
        try:
            collection = self._get_collection(create_if_not_exists=False)
            if collection is None:
                return False
            
            all_docs = collection.get_all()
            if all_docs:
                doc_ids = [doc['id'] for doc in all_docs]
                collection.delete(doc_ids)
                logger.info(f"已清空，共删除 {len(doc_ids)} 条")
            return True
            
        except Exception as e:
            logger.error(f"清空失败: {e}")
            return False
