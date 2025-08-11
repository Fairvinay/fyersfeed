from fyers_apiv3 import fyersModel as fyersV3
from fyers_apiv3.FyersWebsocket import data_ws
#from fyers_apiv3 import accessToken
#from fyers_apiv3.fyersModel import accessToken
#from fyers_api import accessToken as fyersV2
#from fyers_api.Websocket import ws
#from fyers_api import fyersModel

from flask import Flask, request, redirect, render_template ,  Response, render_template_string
from flask import jsonify
from multiprocessing import Process
import requests
import threading
from threading import Thread
import webbrowser
import time , os , json
import sys , queue




# === Configuration ===
client_id = "P67RJAS1M6-100"
secret_key = "4LXEKKMFUL"
redirect_uri = "https://fyersbook.netlify.app/.netlify/functions/netlifystockfyersbridge/api/fyersauthcodeverify"
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
                           const accessToken = "{{ secret_value }}";
                           console.log("Server variable:", accessToken);
                           /*  document.getElementById('startSSE').addEventListener('click', function (event) {
                                //event.preventDefault(); // stop POST
                                 const es = new EventSource(`http://localhost:5000/stream?accessToken=${accessToken}`);
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
                         	<span id="sse" class="ticker-span">
                                 </span>
                        </form>
                         <button class="login-btn"  type="button" id="startSSE" >Stream with Fyers</button>
			  <button class="login-btn"  type="button" id="stopSSE" >STOP</button>
                          <script>
                             let es = null; // store reference
                             document.getElementById('startSSE').addEventListener('click', function (event) {
                                //event.preventDefault(); // stop POST
                                 if(es) { 
			              console.log("SSE alredy running ");
                                    return;
                                  }
                                   es = new EventSource(`http://localhost:5000/stream?accessToken=${accessToken}`);
                                   es.onmessage = function(e) {
                                       console.log("SSE:", e.data);
                                        document.getElementById('sse').textContent = e.data;
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

@app.route("/stream")
def stream():
    access_token = request.args.get("accessToken")

    # Start background websocket thread
    threading.Thread(target=start_websocket, args=(access_token,)).start()

    # def event_stream():
    #    while True:
    #        msg = message_queue.get()
    #        if msg is None:
    #            break
    #        yield msg
    
    def event_stream():
        while True:
            yield  f"data: hello at {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            time.sleep(1)
        
    return Response(event_stream(), mimetype="text/event-stream")


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
    print("📡 Starting WebSocket with access_token...")
    socket = data_ws.FyersDataSocket(
        access_token=access_token,
        log_path=os.getcwd()
    )

    def on_message(msg):
        print("📥 Data:", json.dumps(msg))
        message_queue.put(f"data: {message}\n\n")

    def on_error(msg):
        print("❗Error:", msg)

    def on_close(msg):
        print("🔌 Closed:", msg)

    socket.on_connect = lambda: socket.subscribe(symbols=["NSE:RELIANCE-EQ"], data_type="symbolData")
    socket.on_message = on_message
    socket.on_error = on_error
    socket.on_close = on_close

    socket.connect()


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
    #webbrowser.open("http://localhost:5000/")

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
