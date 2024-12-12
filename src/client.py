#!/bin/python3
import socket
import ssl

class RPSGameClient:
    def __init__(self, host='127.0.0.1', port=12345):
        self.server_host = host
        self.server_port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Create SSL context
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        self.username = None
        self.in_tournament = False

    def connect_to_server(self):
        try:
            self.client_socket.connect((self.server_host, self.server_port))
            self.client_socket = self.ssl_context.wrap_socket(
                self.client_socket, 
                server_hostname=self.server_host
            )
            print("Connected to server.")
            self.game_loop()
        except Exception as e:
            print(f"Error connecting to server: {e}")
        finally:
            self.client_socket.close()
            print("Disconnected from server.")

    def send_message(self, message):
        try:
            self.client_socket.send(message.encode())
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False

    def receive_message(self):
        try:
            message = self.client_socket.recv(1024).decode()
            return message
        except Exception as e:
            print(f"Error receiving message: {e}")
            return None

    def handle_server_message(self, message):
        # Check if message expects a reply
        expects_reply = False
        if "{{expect_reply}}" in message:
            expects_reply = True
            message = message.replace("{{expect_reply}}", "")

        # Print the message
        print(message)

        # If reply is expected, get user input and send it
        if expects_reply:
            while True:
                user_input = input("Your input: ").strip()
                if user_input:
                    self.send_message(user_input)
                    break
            return True
        return False

    def game_loop(self):
        while True:
            try:
                # Receive server message
                server_message = self.receive_message()
                if not server_message:
                    print("Lost connection to server.")
                    break

                # Handle the message and check if we need to continue
                needs_response = self.handle_server_message(server_message)
                
                # Check for exit conditions
                if "Goodbye" in server_message:
                    print("Disconnecting from server...")
                    break

            except Exception as e:
                print(f"Error in game loop: {e}")
                break

if __name__ == "__main__":
    client = RPSGameClient()
    client.connect_to_server()
