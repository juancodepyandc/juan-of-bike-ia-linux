import socket, json
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('127.0.0.1', 3002))
s.sendall(json.dumps({"action": "subscribe"}) + b"\n")
s.close()
