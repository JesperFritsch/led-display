import socket

class SocketClient:
    def __init__(self, socket_file) -> None:
        self.socket_file = socket_file
        self.connected = False
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    def connect(self):
        try:
            self.socket.connect(self.socket_file)
        except socket.error as e:
            print(f'socket connection error: {e}')
            self.connected = False
        else:
            self.connected = True

    def send(self, msg):
        if not self.connected:
            self.connect()
        try:
            self.socket.sendall(msg.encode('utf-8'))
        except socket.error as e:
            print(f'Error sending: {e}')
