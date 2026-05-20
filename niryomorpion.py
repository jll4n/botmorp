# !/usr/bin/env python3
from copy import *
from random import *
from pyniryo import *

robot = NiryoRobot("169.254.200.200")
robot.calibrate_auto()
workspace_name = "morpion"
robot.update_tool()

observation_pose = PoseObject(
    x=-2.926, y=0.595, z=-0.731,
    roll=-0.052, pitch=-1.235, yaw=0.809,
)

botpostable = [
    [
        [-2.9988, 0.6091, -0.837, -0.097, -0.413, 0.195],
        [-2.92, 0.6091, -0.869, -0.107, -0.371, 0.265],
        [-2.749, 0.6091, -0.873, -0.066, -0.341, 0.539]
    ],
    [
        [-2.9988, 0.6091, -0.681, 0.015, -0.431, 0.775],
        [-2.921, 0.6091, -0.719, -0.063, -0.431, 0.778],
        [-2.766, 0.6091, -0.702, 0.008, -0.446, 0.97]
    ],
    [
        [-2.998, 0.6091, -0.486, -0.067, -0.54, 1.126],
        [-2.921, 0.6091, -0.517, -0.046, -0.505, 1.121],
        [-2.786, 0.6091, -0.486, -0.02, -0.568, 0.451]
    ]
]

class Computer(Player):

    def play(self, game):
        return self.bestMove(game, game.table, game.size, self.sign)[0]

    # Selectionner la meilleure possibilitee de jeu
    def bestMove(self, game, table, size, sign):
        # On recupere le sign de l'adverse pour nos calculs
        other = ("X" if sign == "O" else "O")
        # On cree une liste vide pour y ajouter nos possibilitees avec leur score
        moves = list()

        # On parcours le tableau pour classer chaque possibilitee
        for x in range(size):
            for y in range(size):
                # Si la case est disponible
                if table[x][y] == "*":
                    # On fait une copie du tableau dans laquelle on joue
                    copy = deepcopy(table)
                    copy[x][y] = sign
                    # Et on recupere le resultat
                    win = game.win(copy)

                    # Si le tableau est plein et que personne ne gagne, on le grade 0
                    if win == "*" and game.full(copy):
                        score = 0
                    # Si il permet de gagner, on le grade 1
                    elif win == sign:
                        score = 1
                    # Sinon, on le grade avec l'oppose du score pour le joueur adverse
                    # pour son meilleur coup dans son jeu suivant
                    else:
                        score = 0 - self.bestMove(game, copy, size, other)[1]
                    result = ((x, y), score)

                    # Si le score est 1, on joue ce coup
                    if score == 1:
                        return result
                    # Sinon on l'ajout dans la liste avec les autres et on continue
                    moves.append(result)

        # Une fois tous les coups dans la liste, on les trie par score
        shuffle(moves)
        moves.sort(key=lambda move: move[1], reverse=True)
        # Et on joue le meilleur
        return moves[0]

class Game:

    # Initialisation du tableau de jeu
    def __init__(self, size, player1, player2):
        self.size = 3
        self.table = [["*" for x in range(3)] for y in range(3)]
        self.player1 = player1
        self.player2 = player2

    # Deroulement de la partie
    def start(self):
        robot.move_joints(*observation_joints)
        win = "*"
        while win == "*" and not self.full(self.table):
            for player in [self.player1, self.player2]:
                if not self.full(self.table) and win == "*":
                    self.show()
                    print("Au tour de "+player.sign+" de jouer !")
                    x = y = -1
                    while not self.play(x, y, player.sign):
                        (x, y) = player.play(self)
                    print(player.sign+" joue ligne "+str(y+1)+", colonne "+str(x+1))
                    win = self.win(self.table)
        self.show()
        if win == "*":
            print("Match nul !")
            return
        print(win+" remporte la partie !")

    # Affichage du tableau
    def show(self):
        print("")
        line = "  "
        for x in range(self.size):
            line += str(x+1)+" "
        print(line)
        for y in range(self.size):
            line = str(y+1)+" "
            for x in range(self.size):
                line += self.table[x][y]+" "
            print(line)
        print("")

    # Change la valeur d'une case si libre
    def play(self, x, y, player):
        if x >= 0 and x < self.size and y >= 0 and y < self.size and self.table[x][y] == "*":
            self.table[x][y] = player
            robot.move_joints(botpostable[x][y])
            return True
        return False

    # Regarde si un joueur a gagne
    def win(self, table):
        for i in range(self.size):
            line = self.line(table, i)
            if line != "*":
                return line
            col = self.col(table, i)
            if col != "*":
                return col
        for i in range(2):
            dia = self.dia(table, i)
            if dia != "*":
                return dia
        return "*"

    # Verifie une ligne
    def line(self, table, y):
        player = table[0][y]
        changed = False
        for x in range(self.size):
            if table[x][y] != player:
                changed = True
        if changed:
            return "*"
        return player

    # Verifie une colonne
    def col(self, table, x):
        player = table[x][0]
        changed = False
        for y in range(self.size):
            if table[x][y] != player:
                changed = True
        if changed:
            return "*"
        return player

    # Verifie une diagonale
    def dia(self, table, d):
        i = (0 if d == 0 else self.size-1)
        player = table[i][0]
        changed = False
        for x in range(self.size):
            i = (x if d == 0 else self.size-1-x)
            if table[i][x] != player:
                changed = True
        if changed:
            return "*"
        return player

    def full(self, table):
        for x in range(self.size):
            for y in range(self.size):
                if table[x][y] == "*":
                    return False
        return True

class Human(Player):

    def play(self, game):
        y = int(input("Entrer le numero de la ligne (1 a "+str(game.size)+") : "))
        x = int(input("Entrer le numero de la colonne (1 a "+str(game.size)+") : "))
        return (x-1, y-1)

class Player:

    def __init__(self, sign):
        self.sign = sign

    def play(self, game):
        return (0, 0)


Game(3, Human("X"), Computer("O")).start()