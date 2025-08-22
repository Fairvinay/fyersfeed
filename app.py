from fyers_apiv3 import fyersModel as fyersV3
from fyers_apiv3.FyersWebsocket import data_ws
#from fyers_apiv3 import accessToken
#from fyers_apiv3.fyersModel import accessToken
#from fyers_api import accessToken as fyersV2
#from fyers_api.Websocket import ws
#from fyers_api import fyersModel

from flask import Flask, request, redirect, render_template ,  Response, render_template_string
from flask_cors import CORS
from flask import jsonify
from multiprocessing import Process
import requests
import threading
from threading import Thread
import webbrowser
import time , os , json
import sys , queue




# === Configuration ===P67RJAS1M6-100 4LXEKKMFUL
client_id = os.environ.get("client_id", "V8BNUWJ4WQ-100")
secret_key = os.environ.get("secret_key", "KOA61TZLP4")
redirec_base_url = os.environ.get("redirec_base_url", "https://successrate.netlify.app")
#redirect_uri = "https://fyersbook.netlify.app/.netlify/functions/netlifystockfyersbridge/api/fyersauthcodeverify"
redirect_uri = redirec_base_url.rstrip("/") +"/.netlify/functions/netlifystockfyersbridge/api/fyersauthcodeverify"
response_type = "code"
grant_type = "authorization_code"
state = "python_state"

auth_code_received = None
flask_process = None  # Will store reference to the running Process

# === Step 1: Flask server to receive auth_code ===
app = Flask(__name__)

#session = accessToken.SessionModel(
#    client_id=client_id,
#    secret_key=secret_key,
#    redirect_uri=redirect_uri,
#    response_type="code",
#    grant_type="authorization_code"
#)

# Store the token globally after login
global_access_token = None

# A queue to pass messages from websocket thread to SSE stream
message_queue = queue.Queue()


# Allow only your Next.js origin
#CORS(app, supports_credentials=True, resources={r"/stream*": {"origins": "https://fyersbook.netlify.app"}})
cors_url = redirec_base_url.rstrip("/")
CORS(app, supports_credentials=True, resources={r"/stream*": {"origins": cors_url}})


# Allowed origins
#ALLOWED_ORIGINS = [
#    "https://successrate.netlify.app",
#    "https://fyersbook.netlify.app",
#    "https://onedinaar.com",
#    "https://192.168.1.4:8888",
#]

# Read env variable and parse into list
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [origin.strip() for origin in allowed_origins.split(",") if origin.strip()]

if ALLOWED_ORIGINS:  # checks list is not empty
    print("Allowed origins found:", ALLOWED_ORIGINS)
else:
    ALLOWED_ORIGINS = [
        "https://successrate.netlify.app",
        "https://fyersbook.netlify.app",
        "https://onedinaar.com",
        "https://192.168.1.4:8888",
    ]
    print("Allowed origins configured from hard code")

headers	 = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": redirec_base_url.rstrip("/"),
            "Access-Control-Allow-Credentials": "true"
           }


@app.route("/healthz")
def healthz():
	
    return {"status": "ok", "client_id": client_id , "redirec_base_url" : redirec_base_url ,  "allowed_origins": ALLOWED_ORIGINS }, 200

@app.route('/')
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    session = fyersV3.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        state=state
    )
    auth_url = session.generate_authcode()
    print("auth_url:",auth_url)
    return redirect(auth_url)

#@app.route('/login')
#def login():
#    auth_url = session.generate_authcode()
#    return redirect(auth_url)


# 3. Handle Fyers redirect + trigger WebSocket
@app.route('/redirect')
def callback():
    auth_code = request.args.get('code')
    if not auth_code:
        return "❌ Authorization failed", 400

    try:
        session.set_token(auth_code)
        response = session.generate_token()
        access_token = response["access_token"]

        # Save token for later use
        with open("access_token.txt", "w") as f:
            f.write(access_token)

        # Trigger WebSocket
        threading.Thread(target=start_websocket, args=(access_token,)).start()

        return "✅ Authorization successful! WebSocket started. You can close this window."
    except Exception as e:
        return f"❌ Error: {str(e)}", 500


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response



@app.route("/redirect-start")
def redirect_handler_start():
    global global_access_token

    auth_code = request.args.get("auth_code")
    received_state = request.args.get("state")

    if not auth_code:
        return "❌ Error: No auth_code returned"

    session = fyersV3.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code"
    )
    session.set_token(auth_code)
    response = session.generate_token()

    if "access_token" in response:
        global_access_token = response["access_token"]
        #open_websocket(global_access_token)
        #return f"✅ Login successful! WebSocket started.<br><br>Access token:<br><code>{global_access_token}</code>"
        return render_template_string("""
                  <!DOCTYPE html>
                    <html>
                     <head>
                      <meta charset="UTF-8">
                       <title>Stream with Fyers</title>
                        <style>
                          body {
                           font-family: sans-serif;
                           text-align: center;
                           margin-top: 100px;
                          }
                          .ticker-span { 
                             background-color:#346ccf; color:#eaf1de; border-radius: 6px;font-size: 28px;
                             border-color: #1f8ef1;
                             border-style:groove;
                             margin-bottom: 43px;
                          }
                          .ticker-inner {
                           display: inline-flex;
                           align-items: center;
                            gap: 42px
                           /*padding: 4px 12px;*/
                           background: rgba(255, 255, 255, 0.1); /* translucent overlay */
                           /*border-radius: 4px;
                           border: 1px solid rgba(234, 241, 222, 0.5);*/
                          }
                          .ticker-symbol {
                            font-weight: bold;
                            font-size: 0.8em; /* slightly smaller than outer span's 28px */
                            letter-spacing: 0.2px;
                          }

                          .ticker-ltp {
                            font-weight: bold;
                            font-size: 0.8em;
                            background-color: rgba(0, 0, 0, 0.15);
                            padding: 2px 8px;
                            border-radius: 4px;
                            /*border: 1px solid rgba(234, 241, 222, 0.5);*/
                          }
                          .login-btn {
                            padding: 12px 24px;
                            font-size: 18px;
                            background-color: #1f8ef1;
                            color: white;
                            border: none;
                            border-radius: 6px;
                            cursor: pointer;
                            margin-top: 5px;
                          }
                          .login-btn:hover {
                            background-color: #0d6efd;
                          }
                        </style>
                     </head>
                      <body>
                       <div id="messages"></div>
                        <script>
                          
                           var accessToken = "{{ secret_value }}";
                           console.log("Server variable:", accessToken);
                           /*  document.getElementById('startSSE').addEventListener('click', function (event) {
                                //event.preventDefault(); // stop POST
                                 const es = new EventSource(`https://fyersmarketfeed.onrender.com/stream?accessToken=${accessToken}`);
                                es.onmessage = function(e) {
                                       console.log("SSE:", e.data);
                                    };
                           });

                           function post() { 
		            event.preventDefault();
                            const eventSource = new EventSource(`/stream?accessToken=${accessToken}`);
                            eventSource.onmessage = function(event) {
                               const msgDiv = document.getElementById("messages");
                               msgDiv.innerHTML += "<p>" + event.data + "</p>";
                            };
                           }*/

                        </script>

                        <form  method="POST">
                         <div id="ticker-container" class="flex space-x-4">
                         	<span id="sse" class="ticker-span">
                                 </span>
                          </div>
                        </form>
                         <button class="login-btn"  type="button" id="startSSE" >Stream with Fyers</button>
			  <button class="login-btn"  type="button" id="stopSSE" >STOP</button>
                          <script>
                             let es = null; // store reference
                             let tickParse =null; 
                                         let symbol = null;
                                         let ltp = null;
                             let tickBufferQueue  = [];
                             let actToken =  "{{ secret_value }}";
                             let prevTickParse = JSON.parse('{"ltp": "2288.2", "symbol": "NSE:ADANIENT-EQ", "type": "sf"}');
                               console.log(prevTickParse);
                              const container = document.getElementById("ticker-container");  
                             function addTicker(symbol, ltp , symbolId, ltpId) {
                              // Create outer span
                              const outer = document.createElement('span');
                              outer.className = 'ticker-span';

                               // Create inner container
                               const inner = document.createElement('span');
                                inner.className = 'ticker-inner';

                                // Symbol span
                                 const symbolSpan = document.createElement('span');
                                  symbolSpan.className = 'ticker-symbol';
                                   symbolSpan.id = symbolId;  // ✅ ID for symbol
                                 symbolSpan.textContent = symbol;

                                // LTP span
                                 const ltpSpan = document.createElement('span');
                                 ltpSpan.className = 'ticker-ltp';
                                   ltpSpan.id = ltpId;  // ✅ ID for LTP
                                 ltpSpan.textContent = ltp;

                                  // Append children
                                 inner.appendChild(symbolSpan);
                                 inner.appendChild(ltpSpan);
                                  outer.appendChild(inner);

                                 // Append to the target element
                                document.getElementById('sse').appendChild(outer);
                              }
                             // addTicker('NIFTY2581424400CE', 126, 'symbol1', 'ltp1');
                             // addTicker('BANKNIFTY2501012000PE', 352.5, 'symbol2', 'ltp2');    
                               function   addOtherIndices(ticker , index  ) {
                                 const tickerSpan = document.createElement("span");
                                tickerSpan.className = "ticker-span flex items-center space-x-2 bg-gray-100 p-2 rounded shadow";

                               const inner = document.createElement("span");
                                inner.className = "ticker-inner flex flex-col items-start";

                                const symbol = document.createElement("span");
                                 symbol.className = "ticker-symbol font-bold";
                                 symbol.id = `symbol${index + 2}`;
                                 symbol.textContent = ticker.symbol;

                                 const ltp = document.createElement("span");
                                 ltp.className = "ticker-ltp text-green-600";
                                 ltp.id = `ltp${index + 2}`;
                                 ltp.textContent = ticker.ltp;

                                 inner.appendChild(symbol);
                                 inner.appendChild(ltp);
                                 tickerSpan.appendChild(inner);
                                 container.appendChild(tickerSpan);
                               }
                            function updateTickers(data) {
                              // Remove all dynamically added tickers (keep first child)
                                  while (container.children.length > 1) {
                                    container.removeChild(container.lastChild);
                                   }
                             // Add new tickers
                                  data.forEach((ticker, index) => {
                                     const tickerSpan = document.createElement("span");
                                      tickerSpan.className = "ticker-span flex items-center space-x-2 bg-gray-100 p-2 rounded shadow";

                                     const inner = document.createElement("span");
                                      inner.className = "ticker-inner flex flex-col items-start";

                                      const symbol = document.createElement("span");
                                      symbol.className = "ticker-symbol font-bold";
                                        symbol.id = `symbol${index + 2}`;
                                      symbol.textContent = ticker.symbol;
                                      const ltp = document.createElement("span");
                                      ltp.className = "ticker-ltp text-green-600";
                                       ltp.id = `ltp${index + 2}`;
                                       ltp.textContent = ticker.ltp;

                                       inner.appendChild(symbol);
                                       inner.appendChild(ltp);
                                           tickerSpan.appendChild(inner);
                                         container.appendChild(tickerSpan);
                                    });
                                  }
                              


                             document.getElementById('startSSE').addEventListener('click', function (event) {
                                //event.preventDefault(); // stop POST
                                 if(es) { 
			              console.log("SSE alredy running ");
                                    return;
                                  }
                                   es = new EventSource(`https://fyersmarketfeed.onrender.com/stream?accessToken=${actToken }`);
                                   es.onmessage = function(e) {
                                       console.log("SSE:", e.data);
                                        
                                         try { 
                                            tickParse = JSON.parse(e.data);
                                            if(tickParse.symbol !== null && tickParse.symbol !==undefined &&
                                               tickParse.ltp !==null && tickParse.ltp !== undefined) { 
                                            symbol = tickParse.symbol;
                                            ltp = tickParse.ltp;
                                              tickBufferQueue.push(tickParse);
                                              setInterval( () => {
                                                 updateTickers( tickBufferQueue);
                                              }, 200)
                                                                                      
                                             }
                                         }
                                         catch(er){
                                            console.log("Ticker data not parseable ");
                                             tickParse =  prevTickParse;
                                             symbol = tickParse.symbol;
                                             ltp = tickParse.ltp; 
                                             if( Arrays.isArray(tickParse)) { 
                                               tickParse.forEach((ticker, index) => {
                                                 addOtherIndices(ticker, index);
                                                }); 
                                             }                                        
                                          }

                                        //document.getElementById('symbol1').textContent = symbol;
                                        // document.getElementById('ltp1').textContent = ltp;
                                    };
                                   es.onopen = function() {
                                       console.log("SSE: connection open " );
                                       // document.getElementById('sse').textContent = e.data;
                                    };
                                   es.onerror = function(e) {
                                       console.error("SSE:  error " );
                                       // document.getElementById('sse').textContent = e.data;
                                    };

  
                             });
                             document.getElementById('stopSSE').addEventListener('click', function (event) {
                                 if (es) {
                                   es.close();
                                   es = null;
                                    console.log("SSE connection stopped");
                                 } else {
                                   console.log("No SSE connection to stop");
                                 }

                             });

                           </script>

                         
                      </body>
                    </html>
        """,secret_value=global_access_token)
    else:
        return f"❌ Failed to generate token: {response}"

@app.route("/market-feed")
def stream():
    access_token = request.args.get("accessToken")

    # Start background websocket thread
    threading.Thread(target=start_websocket, args=(access_token,)).start()

    def event_stream():
        while True:
            msg = message_queue.get()
            if msg is None:
                break
            yield msg
    
    #def event_stream():
    #    while True:
    #        yield  f"data: hello at {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    #        time.sleep(1)
        
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/stream")
def market_feed():
	
	global headers
	
    # Option 1: If repeated params
    tickers = request.args.getlist("ticker")

    # Option 2: If JSON encoded
    # tickers = json.loads(request.args.get("tickers", "[]"))

    access_token = request.args.get("accessToken")
    print("Tickers:", tickers)
    print("Access Token:", access_token)
    
    if request.method == "OPTIONS":
        origin = request.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            headers = {
                 "Content-Type": "text/event-stream",
                 "Cache-Control": "no-cache",
                 "Connection": "keep-alive",
                 "Access-Control-Allow-Origin": origin,
                 "Access-Control-Allow-Credentials": "true"
            }
    
     # Start background websocket thread
    threading.Thread(target=start_websocket_ticker, args=(access_token,tickers)).start()

    def event_stream():
        while True:
            msg = message_queue.get()
            if msg is None:
                break
            yield msg
    """
    def event_stream():
        while True:
            # Example: send dummy data for each ticker
            for ticker in tickers:
                data = {
                    "symbol": ticker,
                    "ltp": round(1000 + time.time() % 100, 2)
                }
                yield f"data: {json.dumps(data)}\n\n"
            time.sleep(2)
    """
    return Response(event_stream(), mimetype="text/event-stream", headers=headers)


def open_websocket(token):
    def run_ws():
        symbols = ["NSE:SBIN-EQ", "NSE:HDFC-EQ"]
        """
        symbols = ["NSE:SBIN-EQ", "NSE:HDFC-EQ"]
        data_ws.FyersDataSocket(
            access_token=f"{client_id}:{token}",
            log_path="./logs",
            litemode=True,
            write_to_file=False,
            reconnect=True,
            on_message=custom_message
        ).subscribe(symbols=symbols, data_type="symbolData").keep_running()
        """
        data_socket = data_ws.FyersDataSocket(
             access_token=f"{client_id}:{token}",
             log_path="./logs",
             write_to_file=False,
             reconnect=True
        )
        
        def on_open():
             print("Socket opened.")
             data_socket.subscribe(symbols=symbols, data_type="symbolData")

        def on_message(message):
             print("Received:", message)
             message_queue.put(f"data: {message}\n\n")

        def on_error(message):
             print("Error:", message)

        def on_close(message):
             print("Socket closed:", message)

        data_socket.onopen = on_open
        data_socket.onmessage = on_message
        data_socket.onerror = on_error
        data_socket.onclose = on_close
        data_socket.connect()

    threading.Thread(target=run_ws, daemon=True).start()


@app.route('/redirect-old')
def redirect_handler():
    global auth_code_received
    auth_code_received = request.args.get("auth_code")
    if auth_code_received:
        return "✅ Auth Code received. You can close this tab now."
    return "❌ Auth Code not found."

@app.route('/shutdown', methods=['POST'])
def shutdown():
    def shutdown_server():
        print("🛑 Shutting down Flask server...")
        time.sleep(1)  # Give the response time to complete
        flask_process.terminate()
        flask_process.join()
        print("✅ Flask server terminated.")
        sys.exit(0)

    # Respond first, then shutdown
    Process(target=shutdown_server).start()
    return jsonify({'message': 'Shutdown initiated.'})


def start_flask_app():
    app.run(port=5000)

# === Step 2: Open Fyers login ===
def generate_auth_code():
    session = fyersV3.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type=response_type,
        state=state
    )

    url = session.generate_authcode()
    print("🌐 Opening browser for authentication...")
    webbrowser.open(url)

    print("⌛ Waiting for user to login and redirect back with auth code...")

    # Wait until auth_code is received
    while auth_code_received is None:
        time.sleep(1)

    print("✅ Auth code captured.")
    return auth_code_received

# === Step 3: Use fyers_api to generate access token ===
def generate_access_token(auth_code):
    appSession = fyersV3.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        grant_type=grant_type,
        redirect_uri=redirect_uri
    )
    appSession.set_token(auth_code)
    return appSession.generate_token().get("access_token")

# 4. WebSocket Connection Function
def start_websocket(access_token):
    def onmessage(message):
       	 """
       	 Callback function to handle incoming messages from the FyersDataSocket WebSocket.

      	  Parameters:
        	    message (dict): The received message from the WebSocket.

      	 """
         message_queue.put(f"data: {json.dumps(message)}\n\n")
       	 print("Response:", message)

    def onerror(message):
       	 """
       	  Callback function to handle WebSocket errors.

      	  Parameters:
        	    message (dict): The error message received from the WebSocket.
         """
         print("Error:", message)


    def onclose(message):
         """
           Callback function to handle WebSocket connection close events.
         """
         print("Connection closed:", message)


    def onopen():
         """
          C allback function to subscribe to data type and symbols upon WebSocket connection.

         """
         # Specify the data type and symbols you want to subscribe to
         data_type = "SymbolUpdate"

         # Subscribe to the specified symbols and data type
         symbols = ['NSE:SBIN-EQ', 'NSE:ADANIENT-EQ']
         fyers.subscribe(symbols=symbols, data_type=data_type)

         # Keep the socket running to receive real-time data
         fyers.keep_running()
    print("📡 Starting WebSocket with access_token...")
    # Replace the sample access token with your actual access token obtained from Fyers 
    access_token = access_token
    # Create a FyersDataSocket instance with the provided parameters
    fyers = data_ws.FyersDataSocket(
     access_token=access_token,       # Access token in the format "appid:accesstoken"
     log_path="",                     # Path to save logs. Leave empty to auto-create logs in the current directory.
     litemode=True,                  # Lite mode disabled. Set to True if you want a lite response.
     write_to_file=False,              # Save response in a log file instead of printing it.
     reconnect=True,                  # Enable auto-reconnection to WebSocket on disconnection.
     on_connect=onopen,               # Callback function to subscribe to data upon connection.
     on_close=onclose,                # Callback function to handle WebSocket connection close events.
     on_error=onerror,                # Callback function to handle WebSocket errors.
     on_message=onmessage             # Callback function to handle incoming messages from the WebSocket.
    )

    # Establish a connection to the Fyers WebSocket
    fyers.connect()
 
# 5. WebSocket Connection Function
def start_websocket_ticker(access_token,tickers):
    def onmessage(message):
         """
         Callback function to handle incoming messages from the FyersDataSocket WebSocket.

          Parameters:
                message (dict): The received message from the WebSocket.

         """
         message_queue.put(f"data: {json.dumps(message)}\n\n")
         print("Response:", message)

    def onerror(message):
         """
          Callback function to handle WebSocket errors.

          Parameters:
                message (dict): The error message received from the WebSocket.
         """
         print("Error:", message)


    def onclose(message):
         """
           Callback function to handle WebSocket connection close events.
         """
         print("Connection closed:", message)


    def onopen():
         """
          C allback function to subscribe to data type and symbols upon WebSocket connection.

         """
         # Specify the data type and symbols you want to subscribe to
         data_type = "SymbolUpdate"

         # Subscribe to the specified symbols and data type
         #symbols = ['NSE:SBIN-EQ', 'NSE:ADANIENT-EQ']
         # Validate: must be a list, non-empty, and all elements non-empty strings
         if isinstance(tickers, list) and len(tickers) > 0 and all(t.strip() for t in tickers):
            symbols = tickers
         else:
         # Default fallback
            symbols = [
              "BSE:SENSEX-INDEX",
              "NSE:NIFTY50-INDEX",
              "NSE:NIFTYBANK-INDEX"
            ]
         # symbols = tickers
         fyers.subscribe(symbols=symbols, data_type=data_type)

         # Keep the socket running to receive real-time data
         fyers.keep_running()
    print("📡 Starting WebSocket with access_token...")
    # Replace the sample access token with your actual access token obtained from Fyers 
    access_token = access_token
    # Create a FyersDataSocket instance with the provided parameters
    fyers = data_ws.FyersDataSocket(
     access_token=access_token,       # Access token in the format "appid:accesstoken"
     log_path="",                     # Path to save logs. Leave empty to auto-create logs in the current directory.
     litemode=True,                  # Lite mode disabled. Set to True if you want a lite response.
     write_to_file=False,              # Save response in a log file instead of printing it.
     reconnect=True,                  # Enable auto-reconnection to WebSocket on disconnection.
     on_connect=onopen,               # Callback function to subscribe to data upon connection.
     on_close=onclose,                # Callback function to handle WebSocket connection close events.
     on_error=onerror,                # Callback function to handle WebSocket errors.
     on_message=onmessage             # Callback function to handle incoming messages from the WebSocket.
    )

    # Establish a connection to the Fyers WebSocket
    fyers.connect()

# === WebSocket Setup ===
def custom_message(msg):
    print(f"WebSocket Msg: {msg}")
"""
def run_process_background_symbol_data(access_token_ws):
    data_type = "symbolData"
    symbols = ["NSE:NIFTY50-INDEX", "NSE:NIFTYBANK-INDEX", "NSE:SBIN-EQ"]
    fs = ws.FyersSocket(access_token=access_token_ws, run_background=True, log_path="./logs")
    fs.websocket_data = custom_message
    fs.subscribe(symbol=symbols, data_type=data_type)
    print("📡 Subscribed to Symbol Data WebSocket")
    print(fyers.get_profile())
    fs.keep_running()

def run_process_background_order_update(access_token_ws):
    fs = ws.FyersSocket(access_token=access_token_ws, run_background=True, log_path="./logs")
    fs.websocket_data = custom_message
    fs.subscribe(data_type="orderUpdate")
    print("📡 Subscribed to Order Update WebSocket")
    fs.keep_running()
"""

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
    


# === Main Orchestrator ===
#def main():
    # Start Flask server in background
    #flask_thread = threading.Thread(target=start_flask_app)
    #flask_thread.daemon = True
    #flask_thread.start()

    #time.sleep(1)
    #webbrowser.open("https://fyersmarketfeed.onrender.com/")

    # Trigger login and capture auth code
    #auth_code = generate_auth_code()
    #access_token = generate_access_token(auth_code)

    #global fyers
    #fyers = fyersModel.FyersModel(token=access_token, is_async=False, client_id=client_id)

    #access_token_ws = f"{client_id}:{access_token}"
    #run_process_background_symbol_data(access_token_ws)
    #run_process_background_order_update(access_token_ws)

if __name__ == '__main__':
    main()
