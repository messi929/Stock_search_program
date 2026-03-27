"""Stock Screener Pro — 데스크톱 앱.

RUN_MODE에 따라 동작:
  - "client": 원격 서버 URL에 pywebview로 접속 (기본값, 배포용)
  - "server": 로컬 FastAPI 서버 실행 + pywebview (개발/테스트용)
"""

import os
import sys
import time
import json
import threading
import socket

os.environ["PYTHONUTF8"] = "1"

# PyInstaller 번들 경로 처리
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    INTERNAL_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    INTERNAL_DIR = BASE_DIR

APP_TITLE = "Stock Screener Pro"
HOST = "127.0.0.1"


def _get_config():
    """설정 로드."""
    # 환경변수 우선, 없으면 client_config.json
    run_mode = os.environ.get("RUN_MODE")
    server_url = os.environ.get("SERVER_URL")

    if not run_mode or not server_url:
        for d in [BASE_DIR, INTERNAL_DIR]:
            cfg_path = os.path.join(d, "client_config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, encoding="utf-8") as f:
                    cfg = json.load(f)
                    run_mode = run_mode or cfg.get("run_mode", "client")
                    server_url = server_url or cfg.get("server_url", "http://localhost:8501")
                break

    return run_mode or "client", server_url or "http://localhost:8501"


def wait_for_remote(url, timeout=15):
    """원격 서버 접속 가능 여부 확인."""
    import urllib.request
    status_url = f"{url.rstrip('/')}/api/status"
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = urllib.request.urlopen(status_url, timeout=3)
            data = json.loads(resp.read())
            if data.get("status") in ("ready", "loading"):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def find_free_port(start=8501, end=8520):
    """사용 가능한 포트 찾기."""
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((HOST, port))
                return port
        except OSError:
            continue
    return start


def wait_for_local(port, timeout=60):
    """로컬 서버가 데이터 로드까지 완료할 때까지 대기."""
    import urllib.request
    url = f"http://{HOST}:{port}/api/status"
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = urllib.request.urlopen(url, timeout=2)
            data = json.loads(resp.read())
            if data.get("loading_phase", 0) >= 1 and data.get("total_stocks", 0) > 0:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def start_server(port):
    """FastAPI 서버 시작 (server 모드 전용)."""
    os.environ["RUN_MODE"] = "server"
    import uvicorn
    uvicorn.run(
        "screener.main:app",
        host=HOST,
        port=port,
        log_level="info",
    )


def create_tray_icon(window):
    """시스템 트레이 아이콘."""
    try:
        import pystray
        from PIL import Image, ImageDraw

        icon_path = os.path.join(INTERNAL_DIR, "assets", "icon.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(BASE_DIR, "assets", "icon.png")

        if os.path.exists(icon_path):
            image = Image.open(icon_path).resize((64, 64))
        else:
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill=(49, 130, 246))
            draw.text((20, 12), "S", fill="white")

        def on_show(icon, item):
            window.show()
            window.restore()

        def on_quit(icon, item):
            icon.stop()
            window.destroy()

        menu = pystray.Menu(
            pystray.MenuItem("열기", on_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("종료", on_quit),
        )
        icon = pystray.Icon(APP_TITLE, image, APP_TITLE, menu)
        icon.run()
    except ImportError:
        pass


def main():
    import webview

    run_mode, server_url = _get_config()
    print(f"\n  {APP_TITLE}")
    print(f"  모드: {run_mode}")

    if run_mode == "client":
        # ── Client 모드: 원격 서버에 접속만 ──
        print(f"  서버: {server_url}")
        print(f"  연결 확인 중...")
        if not wait_for_remote(server_url, timeout=10):
            # 서버 연결 실패 시 안내 메시지
            import webview as wv
            err_html = f"""
            <html><body style="background:#0b0e14;color:#e2e8f0;font-family:sans-serif;
            display:flex;justify-content:center;align-items:center;height:100vh;text-align:center">
            <div><h2>서버에 연결할 수 없습니다</h2>
            <p style="color:#94a3b8;margin-top:12px">{server_url}</p>
            <p style="color:#94a3b8;font-size:14px;margin-top:8px">네트워크 연결을 확인하고 다시 시도해주세요.</p>
            </div></body></html>
            """
            w = wv.create_window(APP_TITLE, html=err_html, width=500, height=300)
            wv.start()
            return

        url = server_url
        print(f"  연결 성공!")

    else:
        # ── Server 모드: 로컬 서버 실행 (개발용) ──
        port = find_free_port()
        url = f"http://{HOST}:{port}"
        print(f"  로컬 서버: {url}")

        server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
        server_thread.start()

        print(f"  서버 시작 대기 중...")
        if not wait_for_local(port):
            print("  서버 시작 실패!")
            sys.exit(1)
        print(f"  서버 준비 완료!")

    # pywebview 네이티브 창
    window = webview.create_window(
        APP_TITLE,
        url,
        width=1400,
        height=900,
        min_size=(1024, 700),
        confirm_close=False,
        text_select=True,
    )

    tray_thread = threading.Thread(target=create_tray_icon, args=(window,), daemon=True)
    tray_thread.start()

    webview.start(gui="edgechromium", debug=False)
    print(f"\n  {APP_TITLE} 종료.")


if __name__ == "__main__":
    main()
