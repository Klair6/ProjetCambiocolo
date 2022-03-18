from multiprocessing import shared_memory
from multiprocessing.connection import wait
import sysv_ipc
import time
import threading
import os
import signal
#import sys
 
MSG_GAME = 128
MSG_JOUEUR = 129
PID = os.getpid()
TYPE_TRANSPORT = ["airplane","boat","car","train","bike","skate","shoes"] #liste des transports
NB_TRANSPORT = len(TYPE_TRANSPORT)
MSG_JEJOUE = "JEJOUE"
MSG_ENDGAME = "ENDGAME"
#Creation SHM
# sera crée apres qu'on connait le nb de joueurs
# Joueur               1 2 3 ...
# Offre (1,2 ou 3)     _ _ _ ...
# Busy (0,1,2 ou 3)    _ _ _ ...
# Buzzer (no joueur)   _
# Busy: 0 - non busy
# Busy: 1 - Mon offre a ete accepté par un autre
# Busy: 2 - J'ai accepte l'offre d un autre
# Busy: 3 - Apres avoir accepté l offre d un autre, je passe a l echange des cartes
SHM_NAME = "shm_game"
NB_CARTE_PAR_JOUEUR = 5


 
MENU = ["Voir les Offres/Cartes","Faire une Offre","Accepter une Offre","Envoi Cartes (suite à Acceptation de mon offre)","Buzzer !"]
NoJoueur=0
NbJoueur=0
shmgame=[]
mes_cartes=[]
 
def AfficherOffres():
    offres = "Nombre de joueurs: " + str(NbJoueur) + "   Offres: "
    for i in range(0,NbJoueur):
        offres+= str(shmgame[i]) + " "
 
    print(offres)
 
def AfficherCartes(): #affiche transports
    cartes = "Cartes: "
    for i,c in enumerate(mes_cartes):
        if i < NB_CARTE_PAR_JOUEUR: #pour pas que le joueur voit les cartes qu'on lui a envoyée quand il n'a pas encore envoyé les siennes
            cartes += TYPE_TRANSPORT[c] + ' '
    print(cartes)
 
def FaireOffre():
    global shmgame
    print("")
    try:    
        nb = int(input("Nombre de cartes à echanger (0 pour supprimer l'offre en cours): "))
        if nb<0 or nb>3:
            print("Vous pouvez echanger 1, 2 ou 3 cartes maximum")
        else: 
            lock = threading.Lock()
            lock.acquire()
            shmgame[NoJoueur-1] = nb
            lock.release()
    except:
        print("Valeur non autorisée")
 
def AccepterOffre(autre_joueur):
    global shmgame
    #si shm moi et autre joueur pas busy
    lock1 = threading.Lock()
    lock1.acquire()
    moi_busy = shmgame[NbJoueur+NoJoueur-1]
    autre_busy = shmgame[NbJoueur+autre_joueur-1]
    lock1.release

    if moi_busy == 0 and autre_busy == 0:
        #Lock()
        lock2 = threading.Lock()
        lock2.acquire()
        shmgame[NbJoueur+NoJoueur-1] = 2
        shmgame[NbJoueur+autre_joueur-1] = 1
        lock2.release()
        return True
    else:
        return False
 
def EnvoiCartes(autre_joueur):
    global mqjoueur
    global mes_cartes


    cartes = ""

    indice_cartes = input("Entrez les indices (0-4) des cartes à echanger (ex: 023): ")
    for i in indice_cartes:
        cartes += str(mes_cartes[int(i)])
    msg = cartes.encode()
    mqjoueur.send(msg, type=autre_joueur +1)
    print('cartes envoyées au joueur n° :', autre_joueur,' ',cartes)
    tmp_mes_cartes = mes_cartes.copy()
    #print(mes_cartes)
    for i in indice_cartes:
        valeur_carte = tmp_mes_cartes[int(i)] #on parcourt la copie des cartes et on modifie les vraies cartes 
        #print('i=',i,' valeur_carte',valeur_carte)
        mes_cartes.remove(valeur_carte)
    #print(mes_cartes)


def EnvoiCartesFinales():
    global mqgame

    cartes = ""
    for i in mes_cartes:
        cartes += str(i)
    print("avant envoi cartes finales",cartes, " au joueur:",NoJoueur)
    msg = cartes.encode()
    mqgame.send(msg, type=1) #type=1 car il y a le thread qui attend msg autre type pour fin partie
    print("apres envoi cartes finales")
 
def ReceptionCartes(autre_joueur):
    global mqjoueur
    global mes_cartes

    message, t = mqjoueur.receive(type=NoJoueur+1)
    cartes = message.decode() #va contenir x (1<= x <=3) chiffres = cartes echangées
    #print("cartes recues: ", cartes)
    for c in cartes:
        mes_cartes.append(int(c)) #remplissage de la liste mes_cartes
    #AfficherCartes()
 
def Buzzer():
    global shmgame
    for i in range(0,len(mes_cartes)-1):
        if mes_cartes[i] != mes_cartes[i+1]:
            print("Epepep malautru, il vous faut 5 cartes identiques pour sonner la cloche")
            return False
   
    #Lock()
    lock = threading.Lock()
    lock.acquire()
    shmgame[NbJoueur*2] = NoJoueur
    lock.release()
    time.sleep(2) #pour que game ait le temps de voir le buzzer activé et donc d'ecouter
    EnvoiCartesFinales()

 
def display_menu():
    print("")
    print("      ***CAMBIECOLO***    Joueur : ", NoJoueur)
    print("")
    for i, val in enumerate(MENU):
        print("   ", i, "     ",val)
    print("   ", "Crlt+c", "      Quitter")
    print("")
 
def JeJoue():
    global mqgame
    global NoJoueur #on va modifier cette var globale ici
    global PID

    mqgame = sysv_ipc.MessageQueue(MSG_GAME)
    message = MSG_JEJOUE + str(PID)
    message.encode()
    mqgame.send(message)
    #print('msg du game envoyé')
    message2, t = mqgame.receive(type=12)
    msg = message2.decode()
    #print(msg)
    NoJoueur = int(msg)
 
def ReceptionCartesInitiales():
    global mqgame
    global NoJoueur
    #print(NoJoueur)
    message, t = mqgame.receive(type=NoJoueur+1) #car par defaut type = 1 donc joueur2 envoie a joueur1
    cartes = message.decode() #va contenir 5 chiffres = mes cartes
    #print('msg recu ',cartes)
    for c in cartes:
        mes_cartes.append(int(c)) #remplissage d'une liste

def TrouverJoueurQuiAccepteMonOffre():
    i = NbJoueur #pour pas compter les offres 
    while shmgame[i] != 2 and i<=NbJoueur*2: 
        i += 1
    autre_joueur = i - NbJoueur +1
    return autre_joueur

def CommunicationJoueur(): #thread qui att de recevoir une acceptation d'offre
    global mqjoueur
    global mes_cartes

    while True: #pr pas que le thread se termine apres 1 com entre joueur
        if shmgame[NbJoueur + NoJoueur -1] == 1: #pour que ca concerne que le joueur dont l'offre est accepté
            lock = threading.Lock()
            lock.acquire()
            shmgame[NbJoueur + NoJoueur -1] = 3 #pour ne pas que le thread ne passe ici plusieurs fois
            lock.release()
            autre_joueur = TrouverJoueurQuiAccepteMonOffre()
            print() #saut de ligne
            print (' Mon offre a été acceptée par joueur n° :', autre_joueur ,' , il régale ce boug')
            message, t = mqjoueur.receive(type = NoJoueur +1 )
            cartes = message.decode() #va contenir x (1<= x <=3) chiffres = cartes echangées
            #print('thread cartes recues ', cartes)
            for c in cartes:
                mes_cartes.append(int(c)) #remplissage de la liste mes_cartes
            #AfficherCartes()
            print("Cartes recues, selectionnez l'option 3 pour envoyer vos cartes")
             
        time.sleep(2)

 
def CommunicationGame(): #thread qui att de recevoir une fin de partie
    global mqgame
    global PID

    while True:
        message, t = mqgame.receive(type = NoJoueur+1)
        msg = message.decode() #va contenir fin de partie
        if MSG_ENDGAME in msg: #car MSG_ENDGAME est une chaine
            gagnant = msg[len(MSG_ENDGAME)] #on se place a l'indice du gagnant
            points_gagnant = msg[len(MSG_ENDGAME)+1:len(msg)]
            print()
            print("Dommage, quelqu'un viens de sonner la cloche")
            print("La partie est finie...")
            print("Le gagant est le joueur n° :", gagnant, " Son score est de :", points_gagnant , ' points')
            #sys.exit()
            
            shmgame.close()
            shmgame.unlink()
            mqjoueur.remove()
           
    
            
def handler(signum, frame):
    os.kill(PID,signal.SIGKILL)

             
 
def joueur():
    global NbJoueur
    global shmgame
    global mqgame
    global mqjoueur
    temps = 0
 
    JeJoue()
    print("Bravo ! Connection au serveur Game réussie... Joueur: ", NoJoueur)
 
    ReceptionCartesInitiales()
           
    shmgame = shared_memory.ShareableList(name=SHM_NAME)
    NbJoueur = len(shmgame)//2
    mqjoueur = sysv_ipc.MessageQueue(MSG_JOUEUR, sysv_ipc.IPC_CREAT)
 
    thread_joueur = threading.Thread(target=CommunicationJoueur)
    thread_joueur.start()
 
    thread_game = threading.Thread(target=CommunicationGame)
    thread_game.start()
    if (NoJoueur == 1):
        print()
        print("        Bienvenue Razmig")
    elif(NoJoueur == 2):
        print()
        print("        Bienvenue Romain")
    elif(NoJoueur == 3):
        print()
        print("        Bienvenue PFR")
    elif(NoJoueur == 4):
        print()
        print("        Bienvenue SFR")

    while True: #att input clavier
        #print('shm initiale: ',shmgame)
        display_menu()
        choix = input("Fais ton choix : ")
        #try:



        if choix=="" or choix=="0": #afficher offres
            AfficherOffres()
            AfficherCartes()

        elif choix == "1":
            FaireOffre()

        elif choix == "2":
            saisie = input("Entrez numero de l'autre joueur: ")
            try:
                autre_joueur = int(saisie)
                if (shmgame[autre_joueur-1]==0):
                    print("Ce joueur ne propose pas d'offre actuellement")
                else:
                    try : 
                        accept = AccepterOffre(autre_joueur)
                        if accept: #offre possible, les 2 joueurs ne sont pas busy
                            print("Offre acceptée: échange des cartes")
                        
                            EnvoiCartes(autre_joueur)

                            print("Attente reception cartes de l'autre joueur no:", autre_joueur)
                            ReceptionCartes(autre_joueur)

                            lock = threading.Lock()
                            lock.acquire()
                            shmgame[NbJoueur+NoJoueur-1] = 0 #remise a 0 etat busy des 2 joueurs
                            shmgame[NbJoueur+autre_joueur-1] = 0
                            shmgame[autre_joueur-1] = 0 #remise a 0 offre qu avait faite autre joueur
                            lock.release()
                        else:
                            print("Offre non acceptée car cette offre a déja été acceptée par un autre ou le joueur est busy")
                    except:
                        print("Hop hop hop, erreur de saisie")
            except:
                print("hop hop hop ",saisie, " n'est point un joueur")    
        
        elif choix == "3":
            autre_joueur = TrouverJoueurQuiAccepteMonOffre()
            EnvoiCartes(autre_joueur)
        
        elif choix == "4":
            Buzzer()
        
        else:
            print('Votre chat a-t-il marché sur le clavier ? Attention a ne mettre que des chiffres entre 0 et 4')
#shmgame.shm.close()                 # On close la shm a la fin
   
 
if __name__ == "__main__":
    
    signal.signal(signal.SIGTERM, handler)
    joueur()

