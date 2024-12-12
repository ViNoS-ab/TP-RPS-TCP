# RPS Game Server

## Description
A secure Rock-Paper-Scissors (RPS) game server and client using Python. The server supports individual games and tournaments, allowing multiple players to connect, play, and view rankings.

## Table of Contents
- [Installation](#installation)
- [Usage](#usage)
- [Features](#features)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Installation
1. **Clone the repository:**
    ```sh
    git clone https://github.com/ViNoS-ab/TP-RPS-TCP
    cd TP-RPS-TCP
    ```

2. **Create and activate a virtual environment:**
    ```sh
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. **Generate SSL certificates (if not provided):**
    ```sh
    openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes
    ```

## Usage
### Running the Server
1. **Navigate to the `src` directory:**
    ```sh
    cd src
    ```

2. **Start the server:**
    ```sh
    python server.py
    ```

### Running the Client
1. **Navigate to the `src` directory:**
    ```sh
    cd src
    ```

2. **Start the client:**
    ```sh
    python client.py
    ```

## Features
- **Login and Registration**
- **Play Game**
- **View Rankings**
- **Create Tournament**
- **Join Tournament**
- **Start Tournament**



