import socket

PORT = 3002

# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind to port PORT on all interfaces
sock.bind(('0.0.0.0', PORT))

print(f"Listening on UDP port {PORT}...")

while True:
    data, addr = sock.recvfrom(4096)  # buffer size 1024 bytes
    print(f"Received from {addr}: {data.decode(errors='ignore')}")
