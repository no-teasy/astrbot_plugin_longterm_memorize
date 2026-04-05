import time
import os
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


class LongMemory(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        self.plugin_data_path = os.path.realpath(os.path.join(get_astrbot_data_path(), "plugin_data", self.name))
        os.makedirs(self.plugin_data_path, exist_ok=True)
        
    @filter.on_llm_request()
    async def my_custom_hook_1(self, event: AstrMessageEvent, req: ProviderRequest): # 请注意有三个参数
        
        await event.send(MessageChain().message("🤔 thinking..."))
        req.system_prompt += self.create_prompt()
        print(req) # 打印请求的文本
    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
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
        self.replace_or_append("memory.md", content, method == "replace")
        return "success"
    @filter.llm_tool(name="set_soul")
    async def set_soul(self, event: AstrMessageEvent, content: str, method: str):
        '''设置你的灵魂，用于对话风格相关功能,当你需要调整自己的人格设定的时候调用,必须使用它来持久化人格设定,使用markdown和英文
    
        Args:
            content(string): 内容，用markdown和英文，尽量简洁
            method(string): 设置方法 ，可选值为：replace, append
        Returns:
            string: 设置成功
        ''' 
        
        
        self.replace_or_append("soul.md", content, method == "replace")
        return "success"
    @filter.llm_tool(name="set_recent_memory")
    async def set_recent_memory(self, event: AstrMessageEvent, content: str):
        '''设置你的最近记忆，使近1天的对话都可以记住这个内容，文件名为yyyy-mm-dd.md会附加到system提示词中，使用它保证最近发生的事件记忆的持久化，追加更改
    
        Args:
            content(string): 内容，用markdown和英文，尽量简洁
        Returns:
            string: 设置成功
        ''' 
        file_name = f"recent_memory/{time.strftime('%Y-%m-%d')}.md"
        self.replace_or_append(file_name, content, False)
        return "success"
    def replace_or_append(self, file_path: str, content: str, replace: bool = True):
        
        file_path = os.path.join(self.plugin_data_path, file_path)
        if replace:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        elif not replace:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(content)
    def read_file(self, file_path: str):
        
        file_path = os.path.join(self.plugin_data_path, file_path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def create_prompt(self):
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
        return prompt


   
