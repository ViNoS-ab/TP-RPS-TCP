#!/bin/python3
import socket
import threading
import hashlib
import json
import ssl
from concurrent.futures import ThreadPoolExecutor
import random
import signal

class RPSGameServer:
    def __init__(self, host='127.0.0.1', port=12345):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Create SSL context
        # self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # self.ssl_context.load_cert_chain(certfile="server.crt", keyfile="server.key")
        
        # # Wrap the socket with SSL
        self.server_socket.bind((self.host, self.port))
        # self.server_socket = self.ssl_context.wrap_socket(
        #     self.server_socket, 
        #     server_side=True
        # )
        
        self.server_socket.listen(5)

        self.clients = {}
        self.players = self.load_players()
        self.rankings = self.load_rankings()
        self.tournaments = []
        self.waiting_queue = []
        self.running = True
        self.executor = ThreadPoolExecutor()
        self.threads = {}
        self.lock = threading.Lock()
        print(f"Secure server started on {self.host}:{self.port}")

    def send_message(self, conn, message, receive_message=False):
        try:
            if conn._closed:
                return
            if isinstance(message, str):
                if receive_message:
                    message = "{{expect_reply}}" + message
                message = message.encode(encoding="utf-8")
            conn.send(message)
        except Exception as e:
            print(f"Error sending message: {e}")


    def load_players(self):
        try:
            with open("players.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_players(self):
        with open("players.json", "w") as f:
            json.dump(self.players, f)

    def load_rankings(self):
        try:
            with open("rankings.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_rankings(self):
        with open("rankings.json", "w") as f:
            json.dump(self.rankings, f)

    def handle_client(self, conn, addr):
        try:
            if conn._closed:
                return
            self.send_message(conn, "Welcome! Login (1) or Register (2): ", True)
            choice = conn.recv(1024).decode().strip()
            
            if choice == "1":
                self.login(conn)
            elif choice == "2":
                self.register(conn)
            else:
                self.send_message(conn, "Invalid choice. Disconnecting...\n")
        except Exception as e:
            print(f"Error handling client {addr}: {e}")


    def login(self, conn):
        self.send_message(conn, "Enter username: ", True)
        username = conn.recv(1024).decode().strip()
        self.send_message(conn, "Enter password: ", True)
        password = conn.recv(1024).decode().strip()

        hashed_pw = hashlib.sha256(password.encode()).hexdigest()

        if username in self.players and self.players[username] == hashed_pw :
            self.send_message(conn, "Logged In successfully!.\n")
            self.clients[username] = conn
            self.wait_for_command(conn, username)
        else:
            self.send_message(conn, "Invalid credentials. Disconnecting...\n")
            conn.close()

    def register(self, conn):
        self.send_message(conn, "Enter a new username: ", True)
        username = conn.recv(1024).decode().strip()
        self.send_message(conn, "Enter a new password: ", True)
        password = conn.recv(1024).decode().strip()

        if username in self.players:
            self.send_message(conn, "Username already exists. Disconnecting...\n")
            conn.close()
        else:
            hashed_pw = hashlib.sha256(password.encode()).hexdigest()
            self.players[username] = hashed_pw
            self.save_players()
            self.send_message(conn, "Registration successful! You can now log in.\n")
            conn.close()
            
    def send_rankings(self, conn):
        if not self.rankings:
            conn.send("No rankings available yet.\n")
        else:
            rankings_list = "\n".join([f"{player}: {score}" for player, score in sorted(self.rankings.items(), key=lambda x: x[1], reverse=True)])
            conn.send(f"Player Rankings:\n{rankings_list}\n".encode())
        self.wait_for_command(conn)

    def match_player(self, username):
        self.waiting_queue.append(username)
        if len(self.waiting_queue) >= 2:
            self.start_game()
        

    def restart_connection_thread(self, conn2, username):
        # haka ndiro l connection f another thread w na7oo l 9dim so that we continue interactions with each connection with its own thread (kima m lwl)
        fileno = conn2.fileno()
        self.threads[fileno].cancel()
        self.threads[fileno] = self.executor.submit(self.wait_for_command, conn2, username )
        return fileno

    def start_game(self):
        
        player1, player2 = self.waiting_queue[0], self.waiting_queue[1]
        self.waiting_queue = self.waiting_queue[2:]
        conn1, conn2 = self.clients[player1], self.clients[player2]

        self.send_message( conn1,"Match found! Play your move: rock, paper, scissors\n", True)
        self.send_message(conn2,"Match found! Play your move: rock, paper, scissors\n", True)

        move1 = conn1.recv(1024).decode().strip()
        move2 = conn2.recv(1024).decode().strip()

        print(move1,move2)
        result = self.determine_winner(move1, move2, player1, player2)
        self.send_message(conn1, result)
        self.send_message(conn2, result)

        self.restart_connection_thread(conn2, player2)

        self.wait_for_command(conn1, player1)


    def determine_winner(self, move1, move2, player1, player2):
        if move1 not in ["rock", "paper", "scissors"] or move2 not in ["rock", "paper", "scissors"]:
            return "Invalid move. Game aborted."

        if move1 == move2:
            return f"Draw! Both chose {move1}."

        winner = player1 if (move1, move2) in [("rock", "scissors"), ("scissors", "paper"), ("paper", "rock")] else player2

        self.update_rankings(winner)
        return f"{winner} wins! {move1} beats {move2}."

    def update_rankings(self, winner, points=1):
        if winner not in self.rankings:
            self.rankings[winner] = 0
        self.rankings[winner] += points
        self.save_rankings()

    def create_tournament(self, conn, creator):
        self.send_message(conn, "Enter tournament name: ", True)
        name = conn.recv(1024).decode().strip()

        if any(t["name"] == name for t in self.tournaments):
            self.send_message(conn, "Tournament with this name already exists.\n")
            return

        self.tournaments.append({
            "name": name,
            "creator": creator,
            "players": [creator],
            "matches": [],
            "in_progress": False
        })
        self.send_message(conn, f"Tournament '{name}' created.\n")
        self.wait_for_command(conn, creator)

    def join_tournament(self, conn, username):
        if not self.tournaments:
            self.send_message(conn, "No tournaments available to join.\n")
            return

        # Send list of available tournaments
        tournament_list = "Available tournaments to join:\n"
        available_tournaments = [t for t in self.tournaments if not t["in_progress"]]
        for i, t in enumerate(available_tournaments, 1):
            tournament_list += f"{i}. {t['name']} (Creator: {t['creator']})\n"
        self.send_message(conn, tournament_list)
        
        # Send prompt for selection
        self.send_message(conn, "Enter tournament number to join (0 to cancel): ", True)
        
        try:
            choice = int(conn.recv(1024).decode().strip())
            if choice == 0:
                return
            if 1 <= choice <= len(available_tournaments):
                tournament = available_tournaments[choice - 1]
                if username in tournament["players"]:
                    self.send_message(conn, "You are already in this tournament.\n")
                elif tournament["in_progress"]:
                    self.send_message(conn, "This tournament has already started.\n")
                    self.wait_for_command(conn, username)
                else:
                    tournament["players"].append(username)
                    self.send_message(conn, f"Successfully joined tournament '{tournament['name']}'.\n")
            else:
                self.send_message(conn, "Invalid tournament number.\n")
                self.wait_for_command(conn, username)
        except ValueError:
            self.send_message(conn, "Invalid input. Please enter a number.\n")
            self.wait_for_command(conn, username)


    def start_tournament(self, conn, username):
        available_tournaments = [t for t in self.tournaments if t["creator"] == username and not t["in_progress"] and len(t["players"]) >= 2]
        
        if not available_tournaments:
            self.send_message(conn, "You have no tournaments ready to start (must have at least 2 players).\n")
            self.wait_for_command(conn, username)
            return

        # Send list of available tournaments
        tournament_list = "Available tournaments to start:\n"
        for i, t in enumerate(available_tournaments, 1):
            tournament_list += f"{i}. {t['name']} (Players: {len(t['players'])})\n"
        self.send_message(conn, tournament_list)
        
        # Send prompt for selection
        self.send_message(conn, "Enter tournament number to start (0 to cancel): ", True)
        
        try:
            choice = int(conn.recv(1024).decode().strip())
            if choice == 0:
                return
            if 1 <= choice <= len(available_tournaments):
                tournament = available_tournaments[choice - 1]
                tournament["in_progress"] = True
                self.generate_tournament_matches(tournament)
                self.run_tournament_round(tournament, conn)
                self.send_message(conn, f"Tournament '{tournament['name']}' started!\n")
            else:
                self.send_message(conn, "Invalid tournament number.\n")
        except ValueError:
            self.send_message(conn, "Invalid input. Please enter a number.\n")

    def generate_tournament_matches(self, tournament):
        players = tournament["players"]
        random.shuffle(players)  # Randomize player order
        for i in range(0, len(players), 2):
            if i + 1 < len(players):
                tournament["matches"].append((players[i], players[i + 1]))

    def shutdown(self):
        self.running = False
        # Close all client connections
        for username, conn in self.clients.items():
          self.close_connection(conn,username)
        # Close server socket
        if not self.server_socket._closed:
            self.server_socket.close()


    def wait_for_command(self, conn, username= None):
        
        commands = (
            "Available commands:\n"
            "1. Play Game\n"
            "2. View Rankings\n"
            "3. Create Tournament\n"
            "4. Join Tournament\n"
            "5. Start Tournament\n"
            "6. Quit\n"
        )
        print(f"Sent command to {username}")  # Debugging statement
        self.send_message(conn, commands, True)
        if not username:
            username = [k for k, v in self.clients.items() if v == conn][0]
        try:
            choice = conn.recv(1024).decode().strip()
            if choice == "1":
                self.match_player(username)
            elif choice == "2":
                self.send_rankings(conn)
            elif choice == "3":
                self.create_tournament(conn, username)
            elif choice == "4":
                self.join_tournament(conn, username)
            elif choice == "5":
                self.start_tournament(conn, username)
            elif choice == "6":
                self.send_message(conn, "Goodbye!\n")
                self.close_connection(conn, username)
            else:
                self.send_message(conn, "Invalid choice. Please try again.\n")
                self.wait_for_command(conn, username)
        except Exception as e:
            print(f"Error processing command: {e}")
            

    def run_tournament_round(self, tournament, conn):
        if not tournament["matches"]:
            self.announce_tournament_winner(tournament)
            return
        
        current_matches = tournament["matches"].copy()
        tournament["matches"] = []  # Clear for next round
        winners = []
        
        for player1, player2 in current_matches:
            try:
                # Get the connections for both players
                conn1 = self.clients.get(player1)
                conn2 = self.clients.get(player2)
                
                if not conn1 or not conn2:
                    print(f"Player disconnected from tournament: {player1 if not conn1 else player2}")
                    # Advance the connected player
                    winners.append(player2 if not conn1 else player1)
                    continue
                
                # Notify players of their match
                match_msg = f"Tournament match against {player2}\n"
                conn1.send(match_msg.encode())
                match_msg = f"Tournament match against {player1}\n"
                conn2.send(match_msg.encode())
                
                # Get moves from both players
                self.send_message(conn1, "Enter your move (rock/paper/scissors): ", True)
                self.send_message(conn2, "Enter your move (rock/paper/scissors): ", True)
                
                move1 = conn1.recv(1024).decode().strip().lower()
                move2 = conn2.recv(1024).decode().strip().lower()
                
                # Determine winner
                result = self.determine_tournament_winner(move1, move2, player1, player2)
                winner = result["winner"]
                result_msg = result["message"]
                
                # Send result to both players
                conn1.send(result_msg.encode())
                conn2.send(result_msg.encode())
                
                if winner:
                    winners.append(winner)
                
            except Exception as e:
                print(f"Error in tournament match: {e}")
                continue
        
        # Set up next round if there are winners
        if len(winners) > 1:
            # Pair up winners for next round
            for i in range(0, len(winners), 2):
                if i + 1 < len(winners):
                    tournament["matches"].append((winners[i], winners[i + 1]))
                else:
                    # If odd number of winners, give bye to last player
                    tournament["matches"].append((winners[i], winners[i]))
            
            # Start next round
            self.run_tournament_round(tournament, conn)
        else:
            # Tournament is complete
            self.announce_tournament_winner(tournament)

            for player in tournament["players"]:
                if player in self.clients and self.clients[player] != conn:
                    self.restart_connection_thread(self.clients[player], player)
            self.wait_for_command(conn)
            

    def determine_tournament_winner(self, move1, move2, player1, player2):
        if move1 not in ["rock", "paper", "scissors"] or move2 not in ["rock", "paper", "scissors"]:
            return {
                "winner": None,
                "message": "Invalid move. Match voided.\n"
            }
        
        if move1 == move2:
            # In tournament, no draws allowed - player1 advances
            return {
                "winner": player1,
                "message": f"Draw! {player1} advances by default.\n"
            }
        
        winning_moves = {
            "rock": "scissors",
            "paper": "rock",
            "scissors": "paper"
        }
        
        if winning_moves[move1] == move2:
            winner = player1
        else:
            winner = player2
        
        return {
            "winner": winner,
            "message": f"{winner} wins with {move1 if winner == player1 else move2}!\n"
        }

    def announce_tournament_winner(self, tournament):
        if not tournament["matches"] and len(tournament["players"]) > 0:
            winner = tournament["players"][0]
            winner_conn = self.clients.get(winner)
            
            # Award tournament points
            self.update_rankings(winner, points=5)  # More points for tournament win
            
            # Broadcast to all tournament players
            for player in tournament["players"]:
                if player in self.clients:
                    conn = self.clients[player]
                    conn.send(f"Tournament '{tournament['name']}' finished! Winner: {winner}\n".encode())
            
            # Remove tournament from active list
            self.tournaments.remove(tournament)
        else:
            print("Tournament ended without a clear winner")
        
    def run(self):
        print("Server is running...")
        signal.signal(signal.SIGINT, self.signal_handler)  # Catch Ctrl+C

        while self.running:
            try:
                conn, addr = self.server_socket.accept()
                self.threads[conn.fileno()] = self.executor.submit(self.handle_client, conn, addr)
            except Exception as e:
                if self.running:
                    print(f"Error accepting connection: {e}")

    def signal_handler(self, sig, frame):
        self.shutdown()
        sys.exit(0)
        
    def close_connection(self, conn, username=None):
        try:
            if not conn._closed:
                print(f"Closing connection for {username if username else 'unknown user'}")
                conn.close()
                if username:
                    del self.clients[username]
                    if username in self.waiting_queue:
                        self.waiting_queue.remove(username)
        except Exception as e:
            print(f"Error closing connection: {e}")


if __name__ == "__main__":
    server = RPSGameServer()
    server.run()
