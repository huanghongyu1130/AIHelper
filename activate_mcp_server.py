import asyncio
import os
import sys
from time import time

envs = os.environ.copy()

servers = [
    #   工具名稱,    執行程式(空=python),   檔案位置記得加.py,   PORT號
    ("web_search", "", "Tool/websearch_mcp.py", 8002),
    ("web_extract", "", "Tool/web_extractV2.py", 8003),
    ("knowledge", "", "Tool/knowledge_mcp.py", 8022),  # 知識庫查詢工具
    ("vector_search", "", "Tool/vector_search_mcp.py", 8023),  # 向量語義搜尋工具
]

async def run_server(name,exc, script_or_args, port):
    if exc:
        if isinstance(script_or_args, list):
            # 如果是列表，則將 exc 作為第一個元素，其餘展開
            proc = await asyncio.create_subprocess_exec(
                exc, *script_or_args,  # 使用 * 展開列表作為獨立參數
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=envs,
                limit = 20 * 1024  *1024
            )
        else:  # 原本的字串情況 (雖然對於 uvx 可能不適用，但保留彈性)
            proc = await asyncio.create_subprocess_exec(
                exc, script_or_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=envs,
                limit=20 * 1024 *1024
            )
    else:
        # Python 腳本的執行方式 (通常 script_or_args 是腳本路徑)
        proc = await asyncio.create_subprocess_exec(
            sys.executable, script_or_args,  # 假設 script_or_args 是 script 路徑
            "--port", str(port),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=envs,
            limit=20 * 1024  *1024
        )
    print(f"[{name}] started (PID={proc.pid})")
    buffer = b""

    try:
        # 使用 read(4KB) + 手动拆行 的方式，避免单行太长导致 LimitOverrunError
        while True:
            chunk = await proc.stdout.read(4096)
            if not chunk:
                break
            buffer += chunk

            # 如果 buffer 中已有换行，就拆出来打印
            while b"\n" in buffer:
                line, _, buffer = buffer.partition(b"\n")
                text = line.decode("utf-8", errors="ignore").rstrip()
                print(f"[{name:^{24}}] ||{time()}|| {text}")

        # buffer 中可能剩下没有换行的最后一部分
        if buffer:
            text = buffer.decode("utf-8", errors="ignore").rstrip()
            print(f"[{name:^{24}}] ||{time()}|| {text}")

        await proc.wait()

    except Exception:
        # 若子行程讀取途中有例外，先嘗試 kill 子行程
        try:
            proc.kill()
        except Exception:
            pass
        raise

    finally:
        # 確保關閉 stdout/stderr，並等待子行程結束，避免 Event loop 已關閉的錯誤
        try:
            await proc.wait()
        except Exception:
            pass
    print(f"[{name}] exited with code {proc.returncode}")


async def main():
    tasks = [run_server(name,exc, script, port) for name,exc ,script, port in servers]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
