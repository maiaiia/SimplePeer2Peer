import os
import socket, struct, threading
import subprocess

# ------ CODES -------
OK = 200
CLIENT_ERROR = 400
STRING_SEPARATOR = "###"
END_MARKER = "@@@"

# ------ CONST -------
SERVER_PORT = 1234
SERVER_IP = 'localhost'
CLIENT_PORT = None
CLIENT_DIR_PATH = os.path.dirname(os.path.realpath(__file__))

# ------- RESOURCES -------
files = []
server_socket = socket.socket()
stop_event = threading.Event()

# -------- HELPERS ----------
def select_port():
    global CLIENT_PORT, CLIENT_DIR_PATH
    while True:
        CLIENT_PORT = int(input("Enter a port number: "))
        server_socket.send(struct.pack('!I', CLIENT_PORT))
        code = server_socket.recv(4)
        code = struct.unpack('!I', code)[0]
        if code == OK:
            break
        print("Port is already in use by a different client")

    CLIENT_DIR_PATH += "/" + str(CLIENT_PORT) + "/"
    subprocess.run(f'mkdir {CLIENT_DIR_PATH}', shell=True, executable="/bin/bash", capture_output=True)
def add_dummy_files():
    for i in range(5):
        filename = str(CLIENT_PORT) + "file" + str(i) + ".txt"
        files.append(filename)
        subprocess.run(f'touch {CLIENT_DIR_PATH + filename}',shell = True, executable = "/bin/bash")
        subprocess.run(f'echo this is file {i} belonging to client {CLIENT_PORT} >> {CLIENT_DIR_PATH + filename}',shell = True, executable = "/bin/bash")

def send_files_to_server():
    for file_name in files:
        server_socket.sendall((file_name + STRING_SEPARATOR).encode())
    server_socket.sendall(END_MARKER.encode())

def send_file_to_peer(requested_file: str, client_socket: socket.socket):
    file = open(CLIENT_DIR_PATH + requested_file, 'rb')
    for line in file:
        client_socket.sendall(line)
    file.close()
def receive_file_from_peer(request: str, peer_socket: socket.socket):
    file = open(CLIENT_DIR_PATH + request, 'wb')
    while True:
        received = peer_socket.recv(1024)
        if not received:
            break
        file.write(received)
    file.close()

# -------- THREAD HANDLERS ----------
def request_file_handler():
    # send file name to the server
    # receive port of client who has said file
    # download file from client

    while not stop_event.is_set():
        request = input("Enter\n\t`all` to see all files available\n\t`filename` to request it\n\t`X` to close the program\n>").strip()
        if request == "X":
            stop_event.set()
            break
        elif request in files:
            print(f'{request} is already available')
            continue

        server_socket.sendall(request.encode()) #no need for separator i think
        code = server_socket.recv(4)
        code = struct.unpack('!I', code)[0]
        if code == CLIENT_ERROR:
            print("File not found. Try again.")
            continue
        elif code != OK:
            print("An error occurred. Try again.")
            continue


        # read peer number
        peer_port = server_socket.recv(4)
        peer_port = struct.unpack('!I', peer_port)[0]

        # connect to peer
        try:
            peer_socket = socket.create_connection(('localhost', peer_port))
        except Exception as e:
            print(f'Failed to connect to peer socket: {e}')
            server_socket.send(struct.pack('!I', CLIENT_ERROR))
            continue

        server_socket.send(struct.pack('!I', OK))
        print(f'Connected to peer {peer_port}')

        peer_socket.sendall(request.encode())
        peer_code = peer_socket.recv(4)
        peer_code = struct.unpack('!I', peer_code)[0]
        if peer_code != OK:
            print("Peer could not provide file")
            peer_socket.close()
            continue

        print("Beginning download...")

        receive_file_from_peer(request, peer_socket) # TODO no validations for now
        peer_socket.close()

        files.append(request)
        # acknowledgement to server
        server_socket.sendall(struct.pack('!I', OK))
        print("File downloaded successfully!")
def send_file_handler():
    # send files to other clients
    rdv_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rdv_s.bind(('0.0.0.0', CLIENT_PORT))
    rdv_s.listen(5)
    rdv_s.settimeout(1.0) #add timeout to check stop_event periodically

    while not stop_event.is_set(): #this'll be sequential cause i can't handle any more threads my god
        try:
            client_socket, address = rdv_s.accept()
            print(f"\nAccepted connection from {address}\n>")
            # read requested file name -- no validation because i m lazy -- and send it
            requested_file = client_socket.recv(1024).decode()
            if requested_file in files:
                client_socket.send(struct.pack('!I', OK))
            else:
                client_socket.send(struct.pack('!I', CLIENT_ERROR))
                client_socket.close()
                continue

            send_file_to_peer(requested_file, client_socket)
            client_socket.close()
        except socket.timeout:
            continue
        except Exception as e:
            if not stop_event.is_set():
                print(f'\nError in send_file thread: {e}\n>')
            break
    rdv_s.close()

# ------- MAIN --------
def main():
    global CLIENT_PORT, files, server_socket
    # connect to server
    try:
        server_socket = socket.create_connection( (SERVER_IP,SERVER_PORT))
    except socket.error as msg:
        print("Error: ",msg.strerror)
        exit(-1)

    select_port()
    print(f'Selected port: {CLIENT_PORT}')

    add_dummy_files()

    # update server db with files owned by client
    send_files_to_server()

    # create threads
    req_file_t = threading.Thread(target=request_file_handler)
    req_file_t.start()
    send_file_t = threading.Thread(target=send_file_handler)
    send_file_t.start()

    # join them
    req_file_t.join()
    send_file_t.join()

    server_socket.close()

    subprocess.run(f'rm -r {CLIENT_DIR_PATH}', shell=True, executable="/bin/bash", capture_output=True)
    print("Terminated connection")

if __name__ == '__main__':
    main()