# !/usr/bin/env python3
from copy import *
import time
from random import *
from pyniryo import *
from pyniryo.vision import (
    uncompress_image, undistort_image, extract_img_workspace,
    threshold_hsv, ColorHSV, morphological_transformations,
    MorphoType, KernelType, biggest_contours_finder, get_contour_barycenter
)

robot = NiryoRobot("169.254.200.200")
robot.calibrate_auto()
workspace_name = "morpion"
robot.update_tool()

observation_pose = JointsPosition(0.19, -0.012, 0.281, -1.491, 1.384, -2.77)
# observation_pose = JointsPosition(-2.926, 0.595, -0.731, -0.052, -1.235, 0.809)

GRIPPER_DELAY = 0.5

botpostable = [
    [
        JointsPosition(-2.9988, 0.6091, -0.837, -0.097, -0.413, 0.195),
        JointsPosition(-2.92, 0.6091, -0.869, -0.107, -0.371, 0.265),
        JointsPosition(-2.749, 0.6091, -0.873, -0.066, -0.341, 0.539)
    ],
    [
        JointsPosition(-2.9988, 0.6091, -0.681, 0.015, -0.431, 0.775),
        JointsPosition(-2.921, 0.6091, -0.719, -0.063, -0.431, 0.778),
        JointsPosition(-2.766, 0.6091, -0.702, 0.008, -0.446, 0.97)
    ],
    [
        JointsPosition(-2.998, 0.6091, -0.486, -0.067, -0.54, 1.126),
        JointsPosition(-2.921, 0.6091, -0.517, -0.046, -0.505, 1.121),
        JointsPosition(-2.786, 0.6091, -0.486, -0.02, -0.568, 0.451)
    ]
]

mtx, dist = robot.get_camera_intrinsics()

def _pixel_to_cell(cx, cy, img_w, img_h):
    col = min(int(cx / img_w * 3), 2)
    row = min(int(cy / img_h * 3), 2)
    return row, col

def _detect_pieces_in_workspace(img_workspace, color_hsv):
    h, w = img_workspace.shape[:2]

    # 1. Seuillage couleur (intégré pyniryo)
    img_thresh = threshold_hsv(img_workspace, *color_hsv.value)

    # 2. Nettoyage morphologique
    img_thresh = morphological_transformations(
        img_thresh,
        morpho_type=MorphoType.OPEN,
        kernel_shape=(7, 7),
        kernel_type=KernelType.ELLIPSE
    )

    # 3. Trouver jusqu'à 9 contours (max de cases sur le plateau)
    contours = biggest_contours_finder(img_thresh, 9)

    cells = []
    for cnt in contours:
        cx, cy = get_contour_barycenter(cnt)
        row, col = _pixel_to_cell(cx, cy, w, h)
        cells.append((row, col))
    return cells

def read_board_from_camera():
    robot.move(observation_pose)
    robot.wait(0.3)

    # Capture + décompression
    img_compressed = robot.get_img_compressed()
    img = uncompress_image(img_compressed)

    # Correction distorsion lentille
    img = undistort_image(img, mtx, dist)

    # Extraction du workspace via les marqueurs ArUco
    workspace_found, img_workspace = extract_img_workspace(img, workspace_ratio=1.0)
    if not workspace_found:
        print("[Vision] Workspace non détecté — vérifier les marqueurs")
        return None

    board = [["*"] * 3 for _ in range(3)]

    # Pièces humaines : carrés bleus → 'X'
    for (row, col) in _detect_pieces_in_workspace(img_workspace, ColorHSV.BLUE):
        board[row][col] = "X"

    # Pièces robot : ronds rouges → 'O'
    for (row, col) in _detect_pieces_in_workspace(img_workspace, ColorHSV.RED):
        board[row][col] = "O"

    return board

class Player:

    def __init__(self, sign):
        self.sign = sign

    def play(self, game):
        return (0, 0)
        
class Human(Player):

    def play(self, game):
        y = int(input("Entrer le numero de la ligne (1 a "+str(game.size)+") : "))
        x = int(input("Entrer le numero de la colonne (1 a "+str(game.size)+") : "))
        return (x-1, y-1)    

class Computer(Player):

    def play(self, game):
        (x, y), _ = self._best_move(game, game.table, game.size, self.sign)
        self._robot_place_piece(x, y)
        return (x, y)

    # Selectionner la meilleure possibilitee de jeu
    def _best_move(self, game, table, size, sign):
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
                        score = 0 - self._best_move(game, copy, size, other)[1]
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

    def _robot_place_piece(self, x, y):
        try:
            robot.move(observation_pose)
            robot.open_gripper()
            time.sleep(GRIPPER_DELAY)

            robot.move(botpostable[x][y])  # va sur la case choisie
            robot.close_gripper()                  # prend la pièce
            time.sleep(GRIPPER_DELAY)

            robot.move(observation_pose)  # retour observation
        except NiryoRobotException as e:
            print(f"  [ERREUR NIRYO] {e}")

class Game:

    # Initialisation du tableau de jeu
    def __init__(self, size, player1, player2):
        self.size = 3
        self.table = [["*" for x in range(3)] for y in range(3)]
        self.player1 = player1
        self.player2 = player2

    # Deroulement de la partie
    def start(self):
        robot.move(observation_pose)
        win = "*"

        while win == "*" and not self.full(self.table):
            # Tour de l'humain
            self.show()
            print("À vous de jouer ! Posez votre pièce sur le plateau.")
            input("Appuyez sur Entrée une fois votre pièce posée...")

            # Lecture du plateau par caméra
            board_seen = read_board_from_camera()
            if board_seen:
                self.table = board_seen
            win = self.win(self.table)
            if win != "*" or self.full(self.table):
                break

            # Tour du robot
            self.show()
            print("Au tour du robot !")
            x, y = self.player2.play(self)
            self.table[x][y] = "O"
            win = self.win(self.table)

        self.show()
        print("Match nul !" if win == "*" else f"{win} remporte la partie !")

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
            robot.move(botpostable[x][y])
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




Game(3, Human("X"), Computer("O")).start()