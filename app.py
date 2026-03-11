import os
import json
import sys , queue
import threading
from flask import Flask, Response, request
from flask_cors import CORS
from fyers_apiv3.FyersWebsocket import data_ws
from flask_cors import cross_origin
from werkzeug.exceptions import HTTPException
from multiprocessing import Process


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
@cross_origin(origins=ALLOWED_ORIGINS, supports_credentials=True)
def stream():
  try:
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
        import random
        import json

        # Initial values
        prices = {
        "BSE:SENSEX-INDEX": 76995,
        "NSE:NIFTY50-INDEX": 23950,
        "NSE:NIFTYBANK-INDEX": 55860
        }

        # Allowed ranges
        ranges = {
        "BSE:SENSEX-INDEX": (76990, 77000),
        "NSE:NIFTY50-INDEX": (23900, 24650),
        "NSE:NIFTYBANK-INDEX": (55800, 55920)
        }

        # Movement per tick
        movement = {
        "BSE:SENSEX-INDEX": (3.5, 8.5),
        "NSE:NIFTY50-INDEX": (1.5, 2.9),
        "NSE:NIFTYBANK-INDEX": (2.0, 3.9)
        }

        symbols = list(prices.keys())

        while True:
          try:
            msg = message_queue.get(timeout=15)

            yield f"data: {json.dumps(msg)}\n\n"

          except queue.Empty:
            symbol = random.choice(symbols)

            min_range, max_range = ranges[symbol]
            min_move, max_move = movement[symbol]

            # Random direction
            direction = random.choice([-1, 1])

            step = random.uniform(min_move, max_move)

            prices[symbol] += direction * step

            # Clamp inside range
            prices[symbol] = max(min_range, min(max_range, prices[symbol]))

            simulated_msg = {
                "ltp": round(prices[symbol], 2),
                "symbol": symbol,
                "type": "if"
            }

            yield f"data: {json.dumps(simulated_msg)}\n\n"

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
        print("event stream existed")
        
    return Response(event_stream(),mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"  })
  except Exception as e:
        print("STREAM ERROR:", e)
        return {"error": str(e)}, 500

def start_fyers_ws(access_token, tickers):

    print("📡 Starting Fyers websocket")

    def on_open():
        print("WS Connected")
        # Subscribe to the specified symbols and data type
        # Validate: must be a list, non-empty, and all elements non-empty strings
        if isinstance(tickers, list) and len(tickers) > 0 and all(t.strip() for t in tickers):
           symbols = tickers
        else:
           symbols = ["BSE:SENSEX-INDEX","NSE:NIFTY50-INDEX","NSE:NIFTYBANK-INDEX" ] 
        fyers.subscribe(symbols=symbols, data_type="SymbolUpdate")
        fyers.keep_running()

    def on_message(msg):
        message_queue.put(f"data: {json.dumps(msg)}\n\n")

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
    print("📡 connecting to fyers websocket")
    fyers.connect()


@app.errorhandler(Exception)
def handle_error(e):
    if isinstance(e, HTTPException):
        return e
    print("🔥 SERVER ERROR:", str(e))
    return {"error": str(e)}, 500

def run_flask():
    port = int(os.environ.get("PORT", 5000))  # Render sets PORT env variable
    app.run(host="0.0.0.0", port=port,debug=False, use_reloader=False)


#new running main 
def main():
    #flask_thread = Thread(target=run_flask)
    #flask_thread.start()
    flask_process = Process(target=run_flask)
    flask_process.start()

    print("✅ Flask server started.")



if __name__ == "__main__":
	main()
    #port = int(os.environ.get("PORT", 5000))
    #app.run(host="0.0.0.0", port=port)
