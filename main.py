import asyncio
import os
import inspect
import logging
import logging.config
from lightrag import LightRAG, QueryParam
from lightrag.llm.ollama import ollama_model_complete, ollama_embed
from lightrag.utils import EmbeddingFunc, logger, set_verbose_debug
from lightrag.kg.shared_storage import initialize_pipeline_status
from docx import Document
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env", override=False)
WORKING_DIR = "./dickens"

# 多轮对话历史（全局）
conversation_history = []

def configure_logging():
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "lightrag"]:
        logger_instance = logging.getLogger(logger_name)
        logger_instance.handlers = []
        logger_instance.filters = []

    log_dir = os.getenv("LOG_DIR", os.getcwd())
    log_file_path = os.path.abspath(os.path.join(log_dir, "lightrag_ollama_demo.log"))
    print(f"\nLightRAG compatible demo log file: {log_file_path}\n")
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    log_max_bytes = int(os.getenv("LOG_MAX_BYTES", 10485760))
    log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", 5))

    logging.config.dictConfig(
        {
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
        }
    )

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

async def ask_question(rag, question):
    global conversation_history

    # 默认多轮对话，保持最近15轮历史
    history_turns = 15
    param = QueryParam(mode="hybrid", stream=True)
    param.conversation_history = conversation_history[-(2 * history_turns):]
    param.history_turns = history_turns

    conversation_history.append({"role": "user", "content": question})
    resp = await rag.aquery(question, param=param)

    if inspect.isasyncgen(resp):
        print("Assistant: ", end="", flush=True)
        content = ""
        async for chunk in resp:
            print(chunk, end="", flush=True)
            content += chunk
        print()
    else:
        print(f"Assistant: {resp}")
        content = str(resp)

    conversation_history.append({"role": "assistant", "content": content})

async def main():
    global conversation_history

    try:
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

        # 初始化 LightRAG
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

        # 测试嵌入功能
        test_text = ["This is a test string for embedding."]
        embedding = await rag.embedding_func(test_text)
        print("\nTest embedding function:")
        print(f"Test dict: {test_text}")
        print(f"Embedding dim: {embedding.shape[1]}")

        # 定义多个文档路径（相对路径）
        docx_paths = [
            "./财务文件/出差人员市内交通充值费用报销规定（试行）.docx",
            "./财务文件/东电股财[2014]1号1、报销票据要求.docx",
            "./财务文件/东电股财[2014]1号2、国内差旅费报销票据粘贴标准.docx",
            "./财务文件/东电股财[2014]1号3、海外差旅费报销票据粘贴标准.docx",
            "./财务文件/东电股财[2014]1号4、非差旅费报销票据粘贴标准.docx",
        ]

        # 批量加载和插入文档
        print("\n=========== 开始批量加载文档 ===========")
        texts = await load_multiple_docx(docx_paths)
        
        if texts:
            print(f"\n开始批量插入 {len(texts)} 个文档...")
            await rag.ainsert(texts)
            print("批量插入完成！")

        print("\n=========== 进入多轮对话模式 ===========")
        print("输入你的问题，输入 'exit' 或 'quit' 可退出")
        print("系统会自动保持最近3轮对话的上下文\n")

        while True:
            user_input = input("User: ").strip()
            if user_input.lower() in ("exit", "quit"):
                print("对话结束。")
                break
            await ask_question(rag, user_input)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'rag' in locals():
            await rag.llm_response_cache.index_done_callback()
            await rag.finalize_storages()

if __name__ == "__main__":
    configure_logging()
    asyncio.run(main())
    print("\nDone!")
