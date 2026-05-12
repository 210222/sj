#!/usr/bin/env python3
"""一键启动 Coherence 教学系统."""
import os, sys, subprocess, time


def check_api_key():
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        print("[WARN] DEEPSEEK_API_KEY 未设置, LLM 不可用")
        print("       设置: set DEEPSEEK_API_KEY=sk-xxx")
        return False
    print(f"[OK] DEEPSEEK_API_KEY 已设置")
    return True


def main():
    root = os.path.dirname(os.path.abspath(__file__))

    check_api_key()

    # 启动后端
    print("[启动] 后端 API (port 8001)...")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app",
         "--host", "127.0.0.1", "--port", "8001"],
        cwd=root,
    )
    time.sleep(2)

    # 启动前端
    print("[启动] 前端 (port 5173)...")
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=os.path.join(root, "frontend"),
        shell=True,
    )

    print()
    print("=" * 50)
    print("  Coherence 教学系统已启动")
    print(f"  后端: http://127.0.0.1:8001")
    print(f"  API文档: http://127.0.0.1:8001/docs")
    print(f"  前端: http://localhost:5173")
    print("  按 Ctrl+C 停止")
    print("=" * 50)

    try:
        backend.wait()
    except KeyboardInterrupt:
        print("\n[停止] 正在关闭...")
        backend.terminate()
        frontend.terminate()
        print("已停止")


if __name__ == "__main__":
    main()
