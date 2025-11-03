import socket, threading, struct, time, random

# ------ CODES -------
OK = 200
CLIENT_ERROR = 400
STRING_SEPARATOR = "###"
END_MARKER = "@@@"

# ------ CONST -------
SERVER_PORT = 1234
SERVER_IP = 'localhost'

# ------ RESOURCES -----
files_mutex = threading.Lock()
files: dict[str, list[int]] = {} #name : [client_ports]
clients: dict[int, socket] = {}

# --------- HELPERS -----------
def validate_client_port(client):
    while True:
        # read port
        client_port = client.recv(4)
        client_port = struct.unpack('!I', client_port)[0]

        # check if it's already in use
        if client_port in clients.keys() or client_port == SERVER_PORT:
            client.send(struct.pack('!I', CLIENT_ERROR))
            pass
        else:
            client.send(struct.pack('!I', OK))
            break
    return client_port
def receive_files(sock: socket.socket, port_number: int):
    allfiles = ""
    while True:
        buffer = sock.recv(1024).decode()
        if not buffer:
            break
        allfiles += buffer
        if END_MARKER in buffer:
            break

    allfiles = allfiles.split(END_MARKER)
    allfiles = allfiles[0].split(STRING_SEPARATOR)
    allfiles.pop(-1)

    for file in allfiles:
        files_mutex.acquire()
        if file in files.keys():
            files[file].append(port_number)
        else:
            files[file] = [port_number]
        files_mutex.release()
def terminate_connection(sock: socket.socket, port_number: int):
    clients.pop(port_number)
    sock.close()

    # client is no longer reachable so it cannot send files to peers
    to_remove = []
    files_mutex.acquire()
    for file_name, files_list in files.items():
        if port_number in files_list:
            files_list.remove(port_number)
        if len(files_list) == 0:
            to_remove.append(file_name)

    for file_name in to_remove:
        files.pop(file_name)
    files_mutex.release()
    print(f'{port_number} is removed')

# -------- THREAD HANDLERS --------
def handle_client(sock: socket.socket,port_number: int):
    random.seed(time.time())
    # read all files from client
    receive_files(sock, port_number)

    # answer to requests and stuff
    while True:
        requested = sock.recv(1024).decode()
        if not requested:
            terminate_connection(sock, port_number)
            break # connection to client terminated

        if requested == 'all':
            sock.send(struct.pack('!I', CLIENT_ERROR)) #can't be bothered rn
        elif requested in files:
            sock.send(struct.pack('!I', OK))
            # select random peer
            chosen_peer = files[requested][random.randint(0, len(files[requested])-1)]
            sock.send(struct.pack('!I', chosen_peer))
            # check if the client managed to connect to its peer
            code = sock.recv(4)
            code = struct.unpack('!I', code)[0]
            if code == OK:
                print(f'Client {port_number} connected to peer {chosen_peer}')
            else:
                print('An error has occurred while trying to connect client to peer')
                continue

            # wait for client to say acknowledge they received the file
            code = sock.recv(4)
            code = struct.unpack('!I', code)[0]
            if code != OK:
                print(f'Client {port_number} failed to receive data from peer {chosen_peer}')
                continue

            print(f'Client {port_number} received data successfully')
            files[requested].append(port_number)

        else:
            sock.send(struct.pack('!I', CLIENT_ERROR))


# ------- MAIN ----------
def main():
    global files, clients
    rdv_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    rdv_s.bind((SERVER_IP, SERVER_PORT))

    client_threads = []

    print("Listening...")
    rdv_s.listen(5)
    try:
        while True:
            client, address = rdv_s.accept()
            print(f'Accepted connection from {address}')

            # create new client
            client_port = validate_client_port(client)
            clients[client_port] = client

            # create new client thread
            client_thread = threading.Thread(target=handle_client, args=(client,client_port))
            client_thread.start()
            client_threads.append(client_thread)

    except KeyboardInterrupt:
        print("\nShutting down")
    finally:
        rdv_s.close()
        # just in case a thread is not terminated correctly
        for client_socket in clients.values():
            client_socket.close()

        for thread in client_threads:
            thread.join()

if __name__ == '__main__':
    main()