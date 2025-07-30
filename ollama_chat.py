import requests
import json

class OllamaChat:
    def __init__(self, model="qwen2.5-coder:7b", host="http://localhost:11434"):
        self.model = model
        self.host = host
        self.history = []  # 存储上下文历史

    def chat(self, message):
        """发送消息并获取模型回复"""
        self.history.append({"role": "user", "content": message})  # 加入用户提问

        try:
            response = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": self.history
                },
                timeout=60,
                stream=True  # 启用流式传输
            )

            if response.status_code == 200:
                full_reply = ""
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line.decode("utf-8"))
                        if "message" in data and "content" in data["message"]:
                            full_reply += data["message"]["content"]

                self.history.append({"role": "assistant", "content": full_reply})  # 保存模型回复
                return full_reply.strip()
            else:
                return f"错误: {response.status_code} - {response.text}"

        except requests.exceptions.RequestException as e:
            return f"网络错误: {e}"
        except Exception as e:
            return f"未知错误: {e}"

def check_ollama_status(host="http://localhost:11434"):
    """检查 Ollama 服务状态"""
    try:
        response = requests.get(f"{host}/api/tags")
        return response.status_code == 200
    except Exception as e:
        print(f"无法连接到 Ollama 服务: {e}")
        return False

def main():
    print("🤖 Ollama 多轮对话系统")
    print("=" * 50)

    if not check_ollama_status():
        print("请确保 Ollama 服务已启动: ollama serve")
        return

    chat = OllamaChat()

    while True:
        user_input = input("你: ").strip()
        if user_input.lower() in ["exit", "quit", "退出"]:
            print("👋 已退出对话")
            break

        reply = chat.chat(user_input)
        print(f"🤖 助手: {reply}")
        print("-" * 50)

if __name__ == "__main__":
    main()
