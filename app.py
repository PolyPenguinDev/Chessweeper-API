from flask import Flask, request, jsonify, Response, stream_with_context, render_template
from flask_cors import CORS
import time
import random

app = Flask(__name__)
CORS(app)
global chessweeper

class Server:
    class Player:
        def __init__(self, server: 'Server', username, userid, profilepicture, skin):
            self.username = username
            self.userid = userid
            self.profilepicture = profilepicture
            self.skin = skin
            self.server = server
            self.disconnected = False  # New attribute to signal disconnection
            server.userlistbyids[userid] = self
            server.userids.append(userid)
            self.game = None
            self.opponent = None
            self.recievedmessage = None

        def foundmatch(self, match: 'Server.Player'):
            game = self.server.Game(self.server, self, match, self.server.newGame())
            self.opponent = match
            self.game = game
            match.game = game

        def matchmake(self):
            if len(self.server.lookingformatch) > 0:
                opponent = self.server.lookingformatch.pop(0)
                opponent.foundmatch(self)
                self.opponent = opponent
            else:
                self.server.lookingformatch.append(self)
                while self.game is None and not self.disconnected:
                    time.sleep(1)
                if self.disconnected:
                    print("loop ended via disconnection")
                    return None  # Exit if disconnected
            return self.opponent

        def makeprivategame(self):
            game = self.server.Game(self.server, self, None, self.server.newGame())
            self.game = game
            self.server.privategames[game.gameid] = game
            return game.gameid

        def privategamegetopponent(self):
            while self.game.rightplayer is None and not self.disconnected:
                time.sleep(1)
            if self.disconnected:
                print("loop ended via disconnection")
                return None  # Exit if disconnected
            return {"username": self.game.rightplayer.username, "profilepicture": self.game.rightplayer.profilepicture, "skin": self.game.rightplayer.skin}

        def joinprivategame(self, gameid):
            if gameid in self.server.privategames.keys():
                game = self.server.privategames[gameid]
                del self.server.privategames[gameid]
                self.game = game
                game.rightplayer = self
                return {"username": self.game.leftplayer.username, "profilepicture": self.game.leftplayer.profilepicture, "skin": self.game.leftplayer.skin}

        def makeMove(self, newBoard, claims):
            self.game.makeMove(self, newBoard, claims)

        def message(self, message):
            self.game.message(self, message)

        def getNextOpponentMove(self):
            if self.game:
                return self.game.getNextOpponentMove(self)
            else:
                return {"error": "No active game found"}

        def setStartingBoard(self, board):
            return self.game.setStartingBoard(self, board)

        def messageRecieved(self, message):
            self.recievedmessage = message

        def endGame(self, reason):
            self.game.endGame(reason)

        def getMessages(self):
            while not self.disconnected:
                if self.recievedmessage:
                    yield self.recievedmessage
                    self.recievedmessage = None
            print("loop ended via disconnection")

        def disconnect(self):
            self.disconnected = True  # Set the flag to end loops
            del self.server.userlistbyids[self.userid]
            self.server.userids.remove(self.userid)

    class Game:
        def __init__(self, server: 'Server', leftplayer: 'Server.Player', rightplayer: 'Server.Player', gameid):
            self.gameid = gameid
            self.leftplayer = leftplayer
            self.rightplayer = rightplayer
            self.server = server
            self.boardleft = []
            self.boardright = []
            self.capturedleft = []
            self.claims = [i % 16 < 8 for i in range(128)]
            self.lastMover = None
            self.leftplayermessages = []
            self.rightplayermessages = []
            server.gamelist[gameid] = self
            server.gameids.append(gameid)
            self.gameover = None

        def makeMove(self, player, newBoard, claims):
            if player == self.leftplayer:
                self.boardleft = newBoard
                for i in claims:
                    self.claims[i] = True
                for i in self.boardleft:
                    self.boardright = [piece for piece in self.boardright if piece["pos"] != i["pos"]]
                self.lastMover = 'left'

            elif player == self.rightplayer:
                self.boardright = newBoard
                for i in claims:
                    self.claims[i] = False
                for i in self.boardright:
                    self.boardleft = [piece for piece in self.boardleft if piece["pos"] != i["pos"]]
                self.lastMover = 'right'

        def message(self, player, message):
            if player == self.leftplayer:
                self.leftplayermessages.append(message)
                self.rightplayer.messageRecieved(message)
            elif player == self.rightplayer:
                self.rightplayermessages.append(message)
                self.leftplayer.messageRecieved(message)

        def endGame(self, reason):
            self.gameover = reason

        def getNextOpponentMove(self, player):
            if player == self.leftplayer:
                while self.lastMover != 'right' and not self.leftplayer.disconnected:
                    time.sleep(1)
                if self.leftplayer.disconnected:
                    print("loop ended via disconnection")
                    return {"error": "Player disconnected"}
                if self.gameover:
                    del self.server.gamelist[self.gameid]
                    self.server.gameids.remove(self.gameid)
                    self.rightplayer.game = None
                    self.leftplayer.game = None
                    self.rightplayer.opponent = None
                    self.leftplayer.opponent = None
                    return {"result": "game over", "reason": self.gameover, "board": self.boardright, "claims": self.claims, "you": self.boardleft}
                return {"result": "move", "board": self.boardright, "claims": self.claims, "you": self.boardleft}
            elif player == self.rightplayer:
                while self.lastMover != 'left' and not self.rightplayer.disconnected:
                    time.sleep(1)
                if self.rightplayer.disconnected:
                    print("loop ended via disconnection")
                    return {"error": "Player disconnected"}
                if self.gameover:
                    del self.server.gamelist[self.gameid]
                    self.server.gameids.remove(self.gameid)
                    self.rightplayer.game = None
                    self.leftplayer.game = None
                    self.rightplayer.opponent = None
                    self.leftplayer.opponent = None
                    return {"result": "game over", "reason": self.gameover, "board": self.boardleft, "claims": [not i for i in self.claims], "you": self.boardright}
                return {"result": "move", "board": self.boardleft, "claims": [not i for i in self.claims], "you": self.boardright}

        def setStartingBoard(self, player, board):
            if player == self.leftplayer:
                self.boardleft = board
                while self.boardright == [] and not self.leftplayer.disconnected:
                    time.sleep(1)
                if self.leftplayer.disconnected:
                    print("loop ended via disconnection")
                    return {"error": "Player disconnected"}
                return self.boardright
            elif player == self.rightplayer:
                self.boardright = board
                while self.boardleft == [] and not self.rightplayer.disconnected:
                    time.sleep(1)
                if self.rightplayer.disconnected:
                    print("loop ended via disconnection")
                    return {"error": "Player disconnected"}
                return self.boardleft

    def __init__(self):
        self.privategames = {}
        self.userlistbyids = {}
        self.gamelist = {}
        self.userids = []
        self.gameids = []
        self.lookingformatch = []

    def newPlayer(self):
        userid = str(random.randint(0, 9)) + str(random.randint(0, 9)) + str(random.randint(0, 9)) + str(random.randint(0, 9)) + str(random.randint(0, 9)) + str(random.randint(0, 9))
        if userid in self.userids:
            return self.newPlayer()
        else:
            return userid

    def newGame(self):
        gameid = str(random.randint(0, 9)) + str(random.randint(0, 9)) + str(random.randint(0, 9)) + str(random.randint(0, 9)) + str(random.randint(0, 9)) + str(random.randint(0, 9))
        if gameid in self.gameids:
            return self.newGame()
        else:
            return gameid

    def login(self, username, profilepicture, skin):
        player = self.newPlayer()
        user = self.Player(self, username, player, profilepicture, skin)
        return user.userid


chessweeper = Server()


@app.post('/api/login')
def login():
    try:
        data = request.get_json()
        id = chessweeper.login(data['username'], data['profilepicture'], data['skin'])
        return jsonify({"session": id})
    except:
        return jsonify({
            "error": "Conflict",
            "message": "Username is already in use. Please choose another."
        }), 409


@app.get('/api/findmatch')
def findmatch():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split()[1]
        user: "Server.Player" = chessweeper.userlistbyids[token]

        match = user.matchmake()
        if match is None:
            return jsonify({"error": "Disconnected"})
        return jsonify({"opponent": {"username": match.username, "profilepicture": match.profilepicture, "skin": match.skin}, "gameid": user.game.gameid, "color": user == user.game.leftplayer})
    else:
        return {"error": "Unauthorized"}, 401


@app.post('/api/host')
def host():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split()[1]
        user: "Server.Player" = chessweeper.userlistbyids[token]

        gameid = user.makeprivategame()
        return jsonify({"gameid": gameid})
    else:
        return {"error": "Unauthorized"}, 401


@app.post('/api/join')
def join():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split()[1]
        user: "Server.Player" = chessweeper.userlistbyids[token]

        data = request.get_json()
        op = user.joinprivategame(data["gameid"])
        return jsonify({"opponent": op, "gameid": data["gameid"]})
    else:
        return {"error": "Unauthorized"}, 401


@app.get('/api/getjoining')
def getjoining():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split()[1]
        user: "Server.Player" = chessweeper.userlistbyids[token]

        op = user.privategamegetopponent()
        if op is None:
            return jsonify({"error": "Disconnected"})
        return jsonify({"opponent": op})
    else:
        return {"error": "Unauthorized"}, 401


@app.post('/api/setstartposition')
def setStart():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split()[1]
        user: "Server.Player" = chessweeper.userlistbyids[token]

        data = request.get_json()
        return jsonify({"opponentboard": user.setStartingBoard(data['board'])})
    else:
        return {"error": "Unauthorized"}, 401


@app.post('/api/makemove')
def makeMove():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split()[1]
        user: "Server.Player" = chessweeper.userlistbyids[token]

        data = request.get_json()
        user.makeMove(data['board'], data['claims'])
        return jsonify({"success": True})
    else:
        return {"error": "Unauthorized"}, 401


@app.get('/api/getnextopponentmove')
def getNextOpponentMove():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split()[1]
        user: "Server.Player" = chessweeper.userlistbyids[token]

        result = user.getNextOpponentMove()
        if result.get("error"):
            return jsonify(result)
        return jsonify(result)
    else:
        return {"error": "Unauthorized"}, 401


@app.route('/api/getmessages')
def getMessages():
    def messageStream(user: 'Server.Player'):
        for message in user.getMessages():
            yield f'{message}\n'

    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split()[1]
        user: "Server.Player" = chessweeper.userlistbyids[token]

        return Response(stream_with_context(messageStream(user)), content_type='text/event-stream')


@app.post('/api/sendmessage')
def sendMessage():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split()[1]
        user: "Server.Player" = chessweeper.userlistbyids[token]

        data = request.get_json()
        user.message(data['message'])
    else:
        return {"error": "Unauthorized"}, 401


@app.post('/api/endgame')
def endGame():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split()[1]
        user: "Server.Player" = chessweeper.userlistbyids[token]
        data = request.get_json()
        user.endGame(data['reason'])
        return jsonify({"success": True})
    else:
        return {"error": "Unauthorized"}, 401


@app.post('/api/disconnect')
def disconnect():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split()[1]
        user: "Server.Player" = chessweeper.userlistbyids[token]
        user.disconnect()
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Unauthorized"}), 401
@app.route('/')
def home():
    return render_template('game.html')

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
