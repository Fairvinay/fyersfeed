import os
import json
import queue
import threading
from flask import Flask, Response, request
from flask_cors import CORS
from fyers_apiv3.FyersWebsocket import data_ws
from flask_cors import cross_origin
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

# Allowed origins
ALLOWED_ORIGINS = [
    "https://onedinaar.com",
    "https://successrate.netlify.app",
    "https://fyersbook.netlify.app"
]

CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

# Thread-safe queue for SSE
message_queue = queue.Queue()

# Prevent multiple websocket launches
ws_running = False

@app.route("/")
def home():
    return {"status": "running", "service": "fyers-stream"}, 200
    
@app.route("/healthz")
def health():
    return {"status": "ok"}, 200


@app.route("/stream", methods=["GET", "OPTIONS"])
@cross_origin(origins=ALLOWED_ORIGINS)
def stream():

    if request.method == "OPTIONS":
        
        response = app.make_default_options_response()
        
        return response

    access_token = request.args.get("accessToken")
    if not access_token:
        return {"error": "missing accessToken"}, 400

    tickers = request.args.getlist("ticker")

    if not tickers:
        tickers = [
            "NSE:NIFTY50-INDEX",
            "NSE:NIFTYBANK-INDEX",
            "BSE:SENSEX-INDEX"
        ]

    global ws_running

    if not ws_running:
        ws_running = True
        threading.Thread(
            target=start_fyers_ws,
            args=(access_token, tickers),
            daemon=True
        ).start()

    def event_stream():
        import time
        while True:
           try:
               msg = message_queue.get(timeout=15)
               yield f"data: {json.dumps(msg)}\n\n"
           except queue.Empty:
               yield ":\n\n"

        origin = request.headers.get("Origin")

        if origin not in ALLOWED_ORIGINS:
               origin = ALLOWED_ORIGINS[0]

        headers = {
               "Content-Type": "text/event-stream",
               "Cache-Control": "no-cache",
               "Connection": "keep-alive",
               "Access-Control-Allow-Origin": origin,
               "Access-Control-Allow-Headers": "Content-Type, Authorization",
               "Access-Control-Allow-Methods": "GET, OPTIONS",
        }

        return Response(event_stream(),mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive" })


def start_fyers_ws(access_token, tickers):

    print("📡 Starting Fyers websocket")

    def on_open():
        print("WS Connected")
        fyers.subscribe(symbols=tickers, data_type="SymbolUpdate")
        fyers.keep_running()

    def on_message(msg):
        message_queue.put(msg)

    def on_error(err):
        print("WS Error:", err)

    def on_close(msg):
        print("WS Closed:", msg)

    fyers = data_ws.FyersDataSocket(
        access_token=access_token,
        litemode=True,
        reconnect=True,
        write_to_file=False,
        on_connect=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    fyers.connect()


@app.errorhandler(Exception)
def handle_error(e):
    if isinstance(e, HTTPException):
        return e
    print("🔥 SERVER ERROR:", str(e))
    return {"error": str(e)}, 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
