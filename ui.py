import os
import asyncio
import inspect
import logging
import logging.config
from lightrag import LightRAG, QueryParam
from lightrag.llm.ollama import ollama_model_complete, ollama_embed
from lightrag.utils import EmbeddingFunc, logger, set_verbose_debug
from lightrag.kg.shared_storage import initialize_pipeline_status
from docx import Document
from dotenv import load_dotenv

import gradio as gr

load_dotenv(dotenv_path=".env", override=False)

WORKING_DIR = "./dickens"
conversation_history = []
rag = None
initialization_complete = False  # 添加初始化状态标志


def configure_logging():
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "lightrag"]:
        logger_instance = logging.getLogger(logger_name)
        logger_instance.handlers = []
        logger_instance.filters = []

    log_dir = os.getenv("LOG_DIR", os.getcwd())
    log_file_path = os.path.abspath(os.path.join(log_dir, "lightrag_ollama_demo.log"))
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    log_max_bytes = int(os.getenv("LOG_MAX_BYTES", 10485760))
    log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", 5))

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {"format": "%(levelname)s: %(message)s"},
            "detailed": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"},
        },
        "handlers": {
            "console": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            "file": {
                "formatter": "detailed",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_file_path,
                "maxBytes": log_max_bytes,
                "backupCount": log_backup_count,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "lightrag": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },
        },
    })

    logger.setLevel(logging.INFO)
    set_verbose_debug(os.getenv("VERBOSE_DEBUG", "false").lower() == "true")


def load_docx(docx_path):
    doc = Document(docx_path)
    return "\n".join([para.text for para in doc.paragraphs])


async def load_multiple_docx(docx_paths):
    """批量加载多个docx文档"""
    texts = []
    for docx_path in docx_paths:
        try:
            text_content = load_docx(docx_path)
            texts.append(text_content)
            print(f"已加载文档: {docx_path}")
            print(f"文档内容长度: {len(text_content)} 字符")
        except Exception as e:
            print(f"加载文档 {docx_path} 时出错: {e}")
    return texts


async def initialize_rag():
    global rag
    
    # 清理旧文件
    files_to_delete = [
        "graph_chunk_entity_relation.graphml",
        "kv_store_doc_status.json",
        "kv_store_full_docs.json",
        "kv_store_text_chunks.json",
        "vdb_chunks.json",
        "vdb_entities.json",
        "vdb_relationships.json",
    ]
    if not os.path.exists(WORKING_DIR):
        os.mkdir(WORKING_DIR)
    for file in files_to_delete:
        file_path = os.path.join(WORKING_DIR, file)
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleting old file: {file_path}")

    rag = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=ollama_model_complete,
        llm_model_name=os.getenv("LLM_MODEL", "qwen2.5:7b"),
        llm_model_max_token_size=8192,
        llm_model_kwargs={
            "host": os.getenv("LLM_BINDING_HOST", "http://localhost:11434"),
            "options": {"num_ctx": 8192},
            "timeout": int(os.getenv("TIMEOUT", "300")),
        },
        embedding_func=EmbeddingFunc(
            embedding_dim=int(os.getenv("EMBEDDING_DIM", "1024")),
            max_token_size=int(os.getenv("MAX_EMBED_TOKENS", "8192")),
            func=lambda texts: ollama_embed(
                texts,
                embed_model=os.getenv("EMBEDDING_MODEL", "bge-m3:latest"),
                host=os.getenv("EMBEDDING_BINDING_HOST", "http://localhost:11434"),
            ),
        ),
        max_parallel_insert=4
    )
    await rag.initialize_storages()
    await initialize_pipeline_status()


async def load_documents():
    # 定义多个文档路径（相对路径）
    docx_paths = [
        "./财务文件/出差人员市内交通充值费用报销规定（试行）.docx",
        "./财务文件/东电股财[2014]1号1、报销票据要求.docx",
        "./财务文件/东电股财[2014]1号2、国内差旅费报销票据粘贴标准.docx",
        "./财务文件/东电股财[2014]1号3、海外差旅费报销票据粘贴标准.docx",
        "./财务文件/东电股财[2014]1号4、非差旅费报销票据粘贴标准.docx",
    ]

    # 批量加载文档
    print("\n=========== 开始批量加载文档 ===========")
    texts = await load_multiple_docx(docx_paths)
    
    # 批量插入文档
    if texts:
        print(f"\n开始批量插入 {len(texts)} 个文档...")
        await rag.ainsert(texts)
        print("批量插入完成！")
    else:
        print("❌ 没有成功加载任何文档")


async def hybrid_query(user_input: str, mode="hybrid", history_turns=30):
    global conversation_history, rag, initialization_complete
    
    if not initialization_complete:
        return "系统正在初始化中，请稍候..."
    
    if rag is None:
        return "系统未正确初始化，请刷新页面重试。"

    param = QueryParam(
        mode=mode,
        stream=True,
        conversation_history=conversation_history[-2 * history_turns :],
        history_turns=history_turns,
    )

    conversation_history.append({"role": "user", "content": user_input})
    resp = await rag.aquery(user_input, param=param)

    content = ""
    if inspect.isasyncgen(resp):
        async for chunk in resp:
            content += chunk
    else:
        content = str(resp)

    conversation_history.append({"role": "assistant", "content": content})
    return content


def launch_gradio():
    async def async_wrapper(message, history, mode):
        response = await hybrid_query(message, mode=mode)
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": response})
        return history, history

    async def on_start():
        """Gradio 启动时的异步初始化"""
        global initialization_complete
        try:
            print("🚀 开始初始化 LightRAG...")
            await initialize_rag()
            await load_documents()
            initialization_complete = True
            print("✅ 初始化完成！")
            return "系统初始化完成，可以开始对话了！"
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            return f"初始化失败: {str(e)}"

    with gr.Blocks() as demo:
        gr.Markdown("# 📄 LightRAG + Ollama 文档问答系统")
        gr.Markdown("### 已加载多个财务文档，支持多轮对话")
        
        # 添加状态显示
        status_text = gr.Textbox(
            value="正在初始化系统...",
            label="系统状态",
            interactive=False
        )

        chatbot = gr.Chatbot(label="对话历史", type="messages")

        with gr.Row():
            msg = gr.Textbox(
                label="请输入问题",
                placeholder="例如：这份文件的适用范围是什么？",
                lines=2,
                scale=4,
            )
            send_btn = gr.Button("发送", scale=1)

        with gr.Row():
            mode_dropdown = gr.Dropdown(
                choices=["naive", "local", "global", "hybrid"],
                value="hybrid",
                label="检索模式 (Query Mode)",
                interactive=True,
            )

        clear_btn = gr.Button("清除历史")

        def clear_history():
            global conversation_history
            conversation_history = []
            return [], []

        # 注册启动时的初始化
        demo.load(on_start, None, status_text)
        
        msg.submit(async_wrapper, [msg, chatbot, mode_dropdown], [chatbot, chatbot])
        send_btn.click(async_wrapper, [msg, chatbot, mode_dropdown], [chatbot, chatbot])
        clear_btn.click(fn=clear_history, outputs=[chatbot, chatbot])

    demo.launch(share=True)


if __name__ == "__main__":
    configure_logging()
    launch_gradio()
