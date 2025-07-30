<img width="957" height="618" alt="image" src="https://github.com/user-attachments/assets/814a0710-3208-4ff2-9058-13779a20ca81" /># 说明书
这是一个利用lightrag来为ollama提供的大模型快速搭建知识图谱数据库的demo，并附有增加了gradio界面的版本。并附带了官方lightrag server的使用demo

想快速的运行本项目：

1.运行ollama.sh脚本，并根据提示进行（如图是一个完整运行的例子）

<img width="400" height="365" alt="image" src="https://github.com/user-attachments/assets/a31ded9a-519d-41a7-95cd-2856fa956c37" />

2.rag需要读取多个文件来构建知识图谱，因此请确保代码中的路径是真实存在的你的机器上的文件路径，这个需要手动改写按照你的需求

3.python main.py用于运行命令行级别的对话，python ui.py用于运行带有gradio界面的对话

<img width="999" height="710" alt="image" src="https://github.com/user-attachments/assets/fdc5dc37-d207-48b3-b136-8480a4b07894" />

（两种方法功能类似，都是多轮对话+rag，可以通过history_turn来修改记忆长度。稳定的调试建议基于main.py,因为实测gradio还有一定的兼容性问题例如有时候能识别文档有时候不能）

4.也可用官方UI，指令为lightrag-server。我在env配置里默认配置了完全依赖于Ollama本地模型做嵌入和LLM。启动之后可以选择想上传的文件，可以直接本地拖拽上传，并且可以可视化的查看知识图谱以及多轮问答。

<img width="1254" height="740" alt="image" src="https://github.com/user-attachments/assets/96afbf95-dd1c-40fd-a72f-f0e963699bfe" />
